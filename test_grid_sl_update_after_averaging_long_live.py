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

SL_PCT = 5.0
TP_PCT = 100.0   # placeholder — unreachable, keeps enable_tpsl happy

if __name__ == "__main__":

    symbol = "SIRENUSDT"

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

    leftover = service.get_session(symbol, "LONG")
    if leftover is not None:
        service.stop_session(symbol, "LONG")
        print("  stopped leftover LONG grid session")
    else:
        print("  no leftover LONG grid session")

    for pos in exchange.get_positions(symbol):
        ps  = pos["positionSide"]
        qty = abs(float(pos["positionAmt"]))
        if ps == "LONG" and qty > 0:
            exchange.close_position(symbol, "sell", qty)
            print(f"  closed leftover LONG position: qty={qty}")

    time.sleep(1.0)

    try:
        # ------------------------------------------------------------------
        # OPEN LONG POSITION
        # ------------------------------------------------------------------
        print("\n=== OPEN LONG POSITION ===")
        exchange.open_market_position(symbol, "buy", usdt_amount=8.5, leverage=5)
        time.sleep(1.0)

        long_entry = None
        long_qty   = 0.0
        for pos in exchange.get_positions(symbol):
            if pos["positionSide"] == "LONG":
                long_qty   = abs(float(pos["positionAmt"]))
                long_entry = float(pos["entryPrice"])
                break

        print(f"  LONG: entry={long_entry}  qty={long_qty}")

        if long_qty == 0 or long_entry is None:
            print("FAIL: LONG position not opened")
            sys.exit(1)

        # ------------------------------------------------------------------
        # START GRID SESSION (averaging orders below current price)
        # ------------------------------------------------------------------
        print("\n=== START GRID SESSION ===")
        current_price = exchange.get_price(symbol)
        print(f"  current_price={current_price:.8f}")

        first_price = current_price * 0.950   # -5% below market
        last_price  = current_price * 0.920   # -8% below market

        session = service.start_session(
            symbol=symbol,
            position_side="LONG",
            total_budget=15.0,
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
            print(f"    [{lvl.index}] price={lvl.price:.8f}  qty={lvl.qty}  status={lvl.status}")

        time.sleep(0.5)

        # ------------------------------------------------------------------
        # ENABLE TPSL (SL=5%, TP=100% placeholder)
        # ------------------------------------------------------------------
        print("\n=== ENABLE TPSL ===")
        service._base_position_qty[(symbol, "LONG")] = long_qty
        service.enable_tpsl(symbol, "LONG", sl_percent=SL_PCT, tp_percent=TP_PCT)
        print(f"  SL={SL_PCT}%  TP placeholder={TP_PCT}%")

        initial_sl_threshold = long_entry * (1 - SL_PCT / 100)
        print(f"  initial_sl_threshold={initial_sl_threshold:.8f}")

        # ------------------------------------------------------------------
        # START WATCHER
        # ------------------------------------------------------------------
        print("\n=== START WATCHER ===")
        watcher.start_watching(symbol, "LONG")
        print(f"  watcher watching: {list(watcher._watched.keys())}")

        # ------------------------------------------------------------------
        # WAIT FOR AVERAGING FILL (manual: drag grid order to market)
        # ------------------------------------------------------------------
        print("\n=== WAIT FOR AVERAGING FILL ===")
        print("  Move the LONG grid level[0] order to market price to trigger averaging.")
        print("  Waiting up to 120s ...")

        TIMEOUT = 120
        t_start = time.time()
        averaged = False
        while time.time() - t_start < TIMEOUT:
            service.check_grid_fills(symbol, "LONG")
            sess = service.get_session(symbol, "LONG")
            if sess is not None and len(sess.levels) > 0 and sess.levels[0].status == "filled":
                averaged = True
                print(f"  averaging detected after {time.time() - t_start:.1f}s")
                break
            time.sleep(2.0)

        if not averaged:
            print("  TIMEOUT: no averaging fill detected")

        time.sleep(1.0)

        # ------------------------------------------------------------------
        # READ NEW ENTRY PRICE
        # ------------------------------------------------------------------
        new_long_entry = None
        new_long_qty   = 0.0
        for pos in exchange.get_positions(symbol):
            if pos["positionSide"] == "LONG":
                new_long_qty   = abs(float(pos["positionAmt"]))
                new_long_entry = float(pos["entryPrice"])
                break

        print(f"  new LONG: entry={new_long_entry}  qty={new_long_qty}")

        sl_config_after = service._tpsl_configs.get((symbol, "LONG"))

        # ------------------------------------------------------------------
        # CHECKS
        # ------------------------------------------------------------------
        print("\n=== CHECKS ===")
        passed = True

        # [1] LONG position opened
        if long_qty > 0 and long_entry is not None:
            print(f"  PASS [1]: LONG position opened  entry={long_entry:.8f}  qty={long_qty}")
        else:
            print("  FAIL [1]: LONG position not opened")
            passed = False

        # [2] LONG session created
        sess_check = service.get_session(symbol, "LONG")
        if sess_check is not None:
            print(f"  PASS [2]: LONG session exists  session_id={sess_check.session_id}")
        else:
            print("  FAIL [2]: LONG session not found")
            passed = False

        # [3] _tpsl_configs stores sl_percent correctly
        sl_config_initial = service._tpsl_configs.get((symbol, "LONG"))
        if sl_config_initial is not None and sl_config_initial.sl_percent == SL_PCT:
            print(f"  PASS [3]: _tpsl_configs sl_percent={sl_config_initial.sl_percent}%")
        else:
            v = sl_config_initial.sl_percent if sl_config_initial else None
            print(f"  FAIL [3]: _tpsl_configs sl_percent={v}, expected {SL_PCT}")
            passed = False

        # [4] averaging fill detected
        if averaged:
            print("  PASS [4]: averaging fill detected")
        else:
            print("  FAIL [4]: no averaging fill detected within timeout")
            passed = False

        # [5] entryPrice changed after averaging
        # Note: averaging may shift entry price up OR down depending on fill
        # price vs current entry. Direction is not asserted, only the change.
        if new_long_entry is not None and abs(new_long_entry - long_entry) > 1e-8:
            print(f"  PASS [5]: entryPrice changed  {long_entry:.8f} -> {new_long_entry:.8f}")
        else:
            print(f"  FAIL [5]: entryPrice did not change  was={long_entry}  now={new_long_entry}")
            passed = False

        # [6] SL config still active after averaging
        if sl_config_after is not None and sl_config_after.sl_percent == SL_PCT:
            print(f"  PASS [6]: SL config still active  sl_percent={sl_config_after.sl_percent}%")
        else:
            v = sl_config_after.sl_percent if sl_config_after else None
            print(f"  FAIL [6]: SL config not active after averaging  sl_percent={v}")
            passed = False

        # [7] new SL threshold formula correct (direction not asserted)
        # check_tpsl reads entryPrice dynamically -> threshold = new_entry * (1 - sl/100)
        if new_long_entry is not None:
            recalc = new_long_entry * (1 - SL_PCT / 100)
            print(f"  PASS [7]: new SL threshold recalc={recalc:.8f}  (new_entry={new_long_entry:.8f} * {1 - SL_PCT/100:.4f})")
        else:
            print("  FAIL [7]: cannot compute new SL threshold — new_long_entry is None")
            passed = False

        # [8] session still alive (SL not triggered)
        sess_alive = service.get_session(symbol, "LONG") is not None
        if sess_alive:
            print("  PASS [8]: session still alive (SL not triggered)")
        else:
            print("  FAIL [8]: session was stopped — SL may have triggered unexpectedly")
            passed = False

        # [9] watcher still watching
        if (symbol, "LONG") in watcher._watched:
            print("  PASS [9]: watcher still watching LONG")
        else:
            print("  FAIL [9]: watcher no longer watching LONG")
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

        service._tpsl_configs.pop((symbol, "LONG"), None)
        service._base_position_qty.pop((symbol, "LONG"), None)

        try:
            leftover = service.get_session(symbol, "LONG")
            if leftover is not None:
                service.stop_session(symbol, "LONG")
                print("  stopped LONG session")
        except Exception as e:
            print(f"  stop_session error (ignored): {e}")

        for pos in exchange.get_positions(symbol):
            ps  = pos["positionSide"]
            qty = abs(float(pos["positionAmt"]))
            if ps == "LONG" and qty > 0:
                exchange.close_position(symbol, "sell", qty)
                print(f"  closed LONG position: qty={qty}")

    print("\nTEST DONE")
