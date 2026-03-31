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
    # PRE-CLEANUP: убрать хвосты от предыдущих запусков
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
        # OPEN SMALL MARKET LONG POSITION (~5 SIREN / ~8.5 USDT)
        # open_market_position: usdt-based, сам считает qty + округляет
        # ------------------------------------------------------------------
        print("\n=== OPEN MARKET LONG (~8.5 USDT) ===")
        exchange.open_market_position(symbol, "buy", usdt_amount=8.5, leverage=1)
        time.sleep(1.0)

        # читаем entryPrice из биржи
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

        tp_threshold = entry_price * (1 + 0.1 / 100)
        print(f"  entry_price={entry_price}  qty={opened_qty}")
        print(f"  TP threshold: {tp_threshold:.8f}  (+0.1% от entry)")

        # ------------------------------------------------------------------
        # START LONG GRID SESSION
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
        # ENABLE TPSL
        # tp=0.1% — срабатывает почти сразу при любом движении вверх
        # sl=5.0% — далеко, не мешает тесту
        # ------------------------------------------------------------------
        print("\n=== ENABLE TPSL (tp=0.1%, sl=5.0%) ===")
        service.enable_tpsl(symbol, position_side, tp_percent=0.1, sl_percent=5.0)
        tpsl_cfg = service._tpsl_configs.get((symbol, position_side))
        print(f"  tpsl registered: tp={tpsl_cfg.tp_percent}%  sl={tpsl_cfg.sl_percent}%")

        # ------------------------------------------------------------------
        # START WATCHER
        # ------------------------------------------------------------------
        watcher.start_watching(symbol, position_side)
        print(f"\n=== WATCHER STARTED ===")
        print(f"  ждём до 30s — TP должен сработать на первых тиках выше {tp_threshold:.8f}")

        # ------------------------------------------------------------------
        # WAIT: TP triggered = session gone + tpsl config gone
        # ------------------------------------------------------------------
        deadline  = time.time() + 60
        triggered = False

        while time.time() < deadline:
            session_alive = service.get_session(symbol, position_side) is not None
            tpsl_alive    = service._tpsl_configs.get((symbol, position_side)) is not None
            if not session_alive and not tpsl_alive:
                triggered = True
                break
            current = exchange.get_price(symbol)
            print(f"  price={current:.8f}  tp_threshold={tp_threshold:.8f}  diff={current - tp_threshold:+.8f}")
            time.sleep(2.0)

        # ------------------------------------------------------------------
        # CHECKS
        # ------------------------------------------------------------------
        print("\n=== CHECKS ===")
        passed = True

        if triggered:
            print("  PASS: TP triggered — session stopped + tpsl config removed")
        else:
            print("  FAIL: TP не сработал за 30s")
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
