import sys
import time

from exchange.binance_exchange import BinanceExchange
from trading_core.grid.grid_builder import GridBuilder
from trading_core.grid.grid_runner import GridRunner
from trading_core.grid.grid_registry import GridRegistry
from trading_core.grid.grid_sizer import GridSizer
from trading_core.grid.grid_service import GridService
from trading_core.market_data.market_data_service import MarketDataService
from trading_core.watchers.grid_trailing_watcher import GridTrailingWatcher

if __name__ == "__main__":

    symbol        = "SIRENUSDT"
    position_side = "LONG"

    exchange    = BinanceExchange()
    builder     = GridBuilder()
    runner      = GridRunner(exchange)
    registry    = GridRegistry()
    sizer       = GridSizer()
    service     = GridService(builder, runner, registry, exchange, sizer)
    market_data = MarketDataService(exchange.client)
    watcher     = GridTrailingWatcher(service, market_data, cooldown_sec=2.0)

    # ------------------------------------------------------------------
    # PRE-CLEANUP
    # ------------------------------------------------------------------
    print("\n=== PRE-CLEANUP ===")

    leftover = service.get_session(symbol, position_side)
    if leftover is not None:
        service.stop_session(symbol, position_side)
        print("  stopped leftover grid session")
    else:
        print("  no leftover grid session")

    for pos in exchange.get_positions(symbol):
        if pos["positionSide"] == position_side:
            qty = abs(float(pos["positionAmt"]))
            if qty > 0:
                exchange.close_position(symbol, "sell", qty)
                print(f"  closed leftover LONG position: qty={qty}")
            else:
                print("  no open LONG position")
            break

    time.sleep(1.0)

    try:
        # ------------------------------------------------------------------
        # OPEN MARKET LONG (~8.5 USDT)
        # ------------------------------------------------------------------
        print("\n=== OPEN MARKET LONG (~8.5 USDT) ===")
        exchange.open_market_position(symbol, "buy", usdt_amount=8.5, leverage=1)
        time.sleep(1.0)

        entry_price = None
        opened_qty  = 0.0
        for pos in exchange.get_positions(symbol):
            if pos["positionSide"] == position_side:
                entry_price = float(pos["entryPrice"])
                opened_qty  = abs(float(pos["positionAmt"]))
                break

        if opened_qty == 0 or entry_price is None:
            print("FAIL: LONG position not opened")
            sys.exit(1)

        print(f"  entry_price={entry_price}  qty={opened_qty}")

        # ------------------------------------------------------------------
        # MULTI-TP CONFIG
        # ближайший уровень 0.1% — срабатывает почти сразу при движении вверх
        # sl=5.0% — далеко, не мешает тесту
        # ------------------------------------------------------------------
        take_profits = [
            {"tp_percent": 0.1},
            {"tp_percent": 0.2},
            {"tp_percent": 0.3},
        ]
        sl_percent = 5.0

        # thresholds для отображения в логе (sorted ascending — как хранится в TpSlConfig)
        tp_thresholds = [
            (tp["tp_percent"], entry_price * (1 + tp["tp_percent"] / 100))
            for tp in sorted(take_profits, key=lambda x: x["tp_percent"])
        ]

        print("\n  TP levels (sorted):")
        for pct, threshold in tp_thresholds:
            print(f"    tp_percent={pct}%  threshold={threshold:.8f}")
        print(f"  SL: sl_percent={sl_percent}%  threshold={entry_price * (1 - sl_percent / 100):.8f}")

        # ------------------------------------------------------------------
        # START GRID SESSION
        # ------------------------------------------------------------------
        print("\n=== START LONG GRID SESSION ===")
        session = service.start_session(
            symbol=symbol,
            position_side=position_side,
            total_budget=24.0,
            levels_count=3,
            step_percent=1.0,
            qty_mode="fixed",
            orders_count=3,
            first_offset_percent=2.0,
            last_offset_percent=4.0,
            distribution_mode="step",
            distribution_value=1.0,
        )
        print(f"  session_id: {session.session_id}")
        for lvl in session.levels:
            print(f"  [{lvl.index}] price={lvl.price}  qty={lvl.qty}  status={lvl.status}")

        # ------------------------------------------------------------------
        # ENABLE MULTI-TP TPSL
        # ------------------------------------------------------------------
        print("\n=== ENABLE MULTI-TP TPSL ===")
        service.enable_tpsl(
            symbol,
            position_side,
            sl_percent=sl_percent,
            take_profits=take_profits,
        )
        tpsl_cfg = service._tpsl_configs.get((symbol, position_side))
        if tpsl_cfg is None:
            print("  FAIL: tpsl config not registered")
            sys.exit(1)
        print(f"  tpsl registered:")
        print(f"    take_profits (stored order): {tpsl_cfg.take_profits}")
        print(f"    sl_percent={tpsl_cfg.sl_percent}%")

        # ------------------------------------------------------------------
        # START WATCHER
        # ------------------------------------------------------------------
        watcher.start_watching(symbol, position_side)
        print(f"\n=== WATCHER STARTED ===")
        print(f"  ждём до 60s — TP[0] должен сработать при цене >= {tp_thresholds[0][1]:.8f}")

        start_price = exchange.get_price(symbol)
        dist_to_tp0 = tp_thresholds[0][1] - start_price
        print(f"  start price: {start_price:.8f}  distance to TP[0]: {dist_to_tp0:+.8f}")

        # ------------------------------------------------------------------
        # WAIT: любой TP hit = session gone + tpsl gone
        # ------------------------------------------------------------------
        deadline      = time.time() + 60
        triggered     = False
        first_hit_pct = None  # первый TP уровень, который засечём в polling loop

        while time.time() < deadline:
            session_alive = service.get_session(symbol, position_side) is not None
            tpsl_alive    = service._tpsl_configs.get((symbol, position_side)) is not None

            if not session_alive and not tpsl_alive:
                triggered = True
                break

            current = exchange.get_price(symbol)

            # фиксируем первый пересечённый TP уровень в polling loop
            if first_hit_pct is None:
                for pct, threshold in tp_thresholds:
                    if current >= threshold:
                        first_hit_pct = pct
                        break

            diff_to_nearest = current - tp_thresholds[0][1]
            print(
                f"  price={current:.8f}"
                f"  tp[0]={tp_thresholds[0][1]:.8f}"
                f"  diff={diff_to_nearest:+.8f}"
            )
            time.sleep(2.0)

        # ------------------------------------------------------------------
        # CHECKS
        # ------------------------------------------------------------------
        print("\n=== CHECKS ===")
        passed = True

        if triggered:
            print("  PASS: TP triggered — session stopped + tpsl config removed")
            if first_hit_pct is not None:
                print(f"  first TP level detected in polling: tp_percent={first_hit_pct}%")
            else:
                print("  note: TP fired between poll ticks (price not captured in loop)")
        else:
            print("  FAIL: TP не сработал за 60s")
            passed = False

        # проверяем что session удалена из registry
        if service.get_session(symbol, position_side) is None:
            print("  PASS: session removed from registry")
        else:
            print("  FAIL: session still in registry")
            passed = False

        # проверяем что tpsl конфиг удалён
        if service._tpsl_configs.get((symbol, position_side)) is None:
            print("  PASS: tpsl config removed")
        else:
            print("  FAIL: tpsl config still present")
            passed = False

        # проверяем что позиция закрыта
        time.sleep(1.0)
        remaining_qty = 0.0
        for pos in exchange.get_positions(symbol):
            if pos["positionSide"] == position_side:
                remaining_qty = abs(float(pos["positionAmt"]))
                break

        if remaining_qty == 0:
            print("  PASS: LONG position закрыта")
        else:
            print(f"  FAIL: LONG position ещё открыта: qty={remaining_qty}")
            passed = False

        if not passed:
            sys.exit(1)

    except Exception as e:
        print(f"\nERROR: {e}")
        raise

    finally:
        watcher.stop_all()
        market_data.stop()

        print("\n=== FINAL CLEANUP ===")
        leftover = service.get_session(symbol, position_side)
        if leftover is not None:
            service.stop_session(symbol, position_side)
            print("  stopped session in final cleanup")

        for pos in exchange.get_positions(symbol):
            if pos["positionSide"] == position_side:
                qty = abs(float(pos["positionAmt"]))
                if qty > 0:
                    exchange.close_position(symbol, "sell", qty)
                    print(f"  closed position in final cleanup: qty={qty}")
                break

    print("\nTEST DONE")
