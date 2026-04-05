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
        # GRID SESSION: Level 1 ВЫШЕ рынка → fill немедленно
        #
        # Стратегия: для LONG, Level 1 = first_price.
        # Ставим first_price на 0.3% ВЫШЕ текущей цены.
        # BUY limit выше market ask исполняется биржей немедленно.
        # Level 2 = last_price на 2% НИЖЕ рынка → остаётся pending.
        #
        # Результат: check_grid_fills() должен поймать Level 1 как filled.
        # ------------------------------------------------------------------
        current_price = exchange.get_price(symbol)
        first_price   = current_price * 1.003   # 0.3% выше → немедленный fill
        last_price    = current_price * 0.980   # 2% ниже → pending

        print(f"\n=== START LONG GRID SESSION ===")
        print(f"  current_price={current_price:.8f}")
        print(f"  level[1] first_price={first_price:.8f}  (+0.3% above market -> expect immediate fill)")
        print(f"  level[2] last_price={last_price:.8f}   (-2.0% below market -> stays pending)")

        session = service.start_session(
            symbol=symbol,
            position_side=position_side,
            total_budget=20.0,
            levels_count=2,
            step_percent=1.0,
            orders_count=2,
            first_price=first_price,
            last_price=last_price,
            distribution_mode="step",
            distribution_value=1.0,
        )
        print(f"  session_id: {session.session_id}")
        for lvl in session.levels:
            print(f"  [{lvl.index}] price={lvl.price}  qty={lvl.qty}  status={lvl.status}")

        print("\n  initial exchange order statuses:")
        for lvl in session.levels:
            if lvl.order_id:
                try:
                    order = exchange.get_order(symbol, int(lvl.order_id))
                    print(f"    level[{lvl.index}] order_id={lvl.order_id}  exchange_status={order.get('status')}")
                except Exception as e:
                    print(f"    level[{lvl.index}] order_id={lvl.order_id}  get_order error: {e}")

        # ------------------------------------------------------------------
        # START WATCHER
        # нет tpsl, нет trailing — только fill detection
        # ------------------------------------------------------------------
        watcher.start_watching(symbol, position_side)
        print(f"\n=== WATCHER STARTED ===")
        print(f"  cooldown=2.0s — check_grid_fills() будет срабатывать каждые ~2s")
        print(f"  ждём до 30s — ожидаем [GridFills] лог для level[1]")

        # ------------------------------------------------------------------
        # WAIT: ждём пока level[1].status станет "filled"
        # ------------------------------------------------------------------
        deadline      = time.time() + 30
        fill_detected = False

        while time.time() < deadline:
            current_session = service.get_session(symbol, position_side)
            if current_session is None:
                break

            filled = [lvl for lvl in current_session.levels if lvl.status == "filled"]
            if filled:
                fill_detected = True
                break

            current = exchange.get_price(symbol)
            statuses = {lvl.index: lvl.status for lvl in current_session.levels}
            print(f"  price={current:.8f}  levels={statuses}")
            time.sleep(2.0)

        # ------------------------------------------------------------------
        # CHECKS
        # ------------------------------------------------------------------
        print("\n=== CHECKS ===")
        passed = True

        current_session = service.get_session(symbol, position_side)

        if fill_detected and current_session is not None:
            filled_levels = [lvl for lvl in current_session.levels if lvl.status == "filled"]
            print(f"  PASS: fill detected — {len(filled_levels)} level(s) marked as filled")
            for lvl in filled_levels:
                print(f"    level[{lvl.index}] price={lvl.price}  status={lvl.status}")
        else:
            print("  FAIL: no fill detected within 30s")
            passed = False

        # level[2] должен остаться placed
        if current_session is not None:
            pending = [lvl for lvl in current_session.levels if lvl.status == "placed"]
            if pending:
                print(f"  PASS: {len(pending)} level(s) still placed (pending)")
                for lvl in pending:
                    print(f"    level[{lvl.index}] price={lvl.price}  status={lvl.status}")
            else:
                print("  note: no pending levels remaining")

        # session должна быть живой (fill не останавливает grid в v1)
        if current_session is not None:
            print(f"  PASS: session still alive after fill (session_id={current_session.session_id})")
        else:
            print("  FAIL: session gone after fill — grid should remain alive")
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
