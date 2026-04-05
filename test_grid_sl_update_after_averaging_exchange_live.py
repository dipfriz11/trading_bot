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
TP_PCT = 100.0   # placeholder

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

    def get_open_algos(sym: str) -> list:
        resp = exchange.client.futures_get_open_algo_orders(symbol=sym)
        if isinstance(resp, list):
            return resp
        return resp.get("openAlgoOrders", [])

    def find_algo(algo_id: int) -> dict | None:
        for o in get_open_algos(symbol):
            if o.get("algoId") == algo_id:
                return o
        return None

    # ------------------------------------------------------------------
    # PRE-CLEANUP
    # ------------------------------------------------------------------
    print("\n=== PRE-CLEANUP ===")

    leftover = service.get_session(symbol, position_side)
    if leftover is not None:
        service.stop_session(symbol, position_side)
        print("  stopped leftover LONG session")
    else:
        print("  no leftover LONG session")

    try:
        for o in get_open_algos(symbol):
            if o.get("positionSide") == position_side:
                exchange.cancel_algo_order(o["algoId"])
                print(f"  cancelled leftover algo algoId={o['algoId']}")
    except Exception as e:
        print(f"  algo cleanup skipped: {e}")

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
        # OPEN LONG POSITION
        # ------------------------------------------------------------------
        print("\n=== OPEN LONG POSITION ===")
        t0 = time.time()
        exchange.open_market_position(symbol, "buy", usdt_amount=8.5, leverage=5)
        time.sleep(1.0)

        entry_price = None
        long_qty    = 0.0
        for pos in exchange.get_positions(symbol):
            if pos["positionSide"] == position_side:
                long_qty    = abs(float(pos["positionAmt"]))
                entry_price = float(pos["entryPrice"])
                break

        print(f"  entry={entry_price:.8f}  qty={long_qty}")
        print(f"  [TIMING] position opened in {time.time() - t0:.2f}s")

        if long_qty == 0 or entry_price is None:
            print("FAIL: LONG position not opened")
            sys.exit(1)

        # ------------------------------------------------------------------
        # START GRID SESSION
        # ------------------------------------------------------------------
        print("\n=== START GRID SESSION ===")
        t1 = time.time()
        current_price = exchange.get_price(symbol)
        print(f"  current_price={current_price:.8f}")

        session = service.start_session(
            symbol=symbol,
            position_side=position_side,
            total_budget=15.0,
            levels_count=2,
            step_percent=1.0,
            orders_count=2,
            first_price=current_price * 0.950,
            last_price=current_price * 0.920,
            distribution_mode="step",
            distribution_value=1.0,
        )
        print(f"  session_id={session.session_id}")
        for lvl in session.levels:
            print(f"    [{lvl.index}] price={lvl.price:.8f}  qty={lvl.qty}  status={lvl.status}")
        print(f"  [TIMING] session started in {time.time() - t1:.2f}s")

        # ------------------------------------------------------------------
        # ENABLE TPSL → initial SL placed on exchange
        # ------------------------------------------------------------------
        print("\n=== ENABLE TPSL (initial SL) ===")
        t2 = time.time()
        service._base_position_qty[(symbol, position_side)] = long_qty
        service.enable_tpsl(symbol, position_side, sl_percent=SL_PCT, tp_percent=TP_PCT)
        print(f"  [TIMING] tpsl enabled in {time.time() - t2:.2f}s")

        initial_algo_id = service._sl_orders.get((symbol, position_side))
        initial_sl_obj  = find_algo(initial_algo_id)
        initial_trigger = float(initial_sl_obj.get("triggerPrice", 0)) if initial_sl_obj else None

        print(f"  initial algoId={initial_algo_id}")
        print(f"  initial triggerPrice={initial_trigger}")

        if initial_algo_id is None or initial_sl_obj is None:
            print("FAIL: initial SL not placed on exchange")
            sys.exit(1)

        # ------------------------------------------------------------------
        # START WATCHER
        # ------------------------------------------------------------------
        print("\n=== START WATCHER ===")
        watcher.start_watching(symbol, position_side)
        print(f"  watching: {list(watcher._watched.keys())}")

        # ------------------------------------------------------------------
        # WAIT FOR AVERAGING FILL
        # ------------------------------------------------------------------
        print("\n=== WAIT FOR AVERAGING FILL ===")
        print("  Drag grid level[0] order to market to trigger averaging.")
        print("  Waiting up to 120s ...")

        TIMEOUT = 120
        t_wait  = time.time()
        averaged = False
        while time.time() - t_wait < TIMEOUT:
            sess = service.get_session(symbol, position_side)
            if sess is not None and any(lvl.status == "filled" for lvl in sess.levels):
                averaged = True
                print(f"  averaging detected after {time.time() - t_wait:.1f}s")
                break
            time.sleep(2.0)

        if not averaged:
            print("  TIMEOUT: no averaging fill detected")

        time.sleep(2.0)  # let watcher tick + Binance API propagate

        # ------------------------------------------------------------------
        # READ STATE AFTER AVERAGING
        # ------------------------------------------------------------------
        new_algo_id = service._sl_orders.get((symbol, position_side))

        # retry once — Binance algo API may have brief propagation lag
        new_sl_obj = None
        if new_algo_id is not None:
            new_sl_obj = find_algo(new_algo_id)
            if new_sl_obj is None:
                time.sleep(1.5)
                new_sl_obj = find_algo(new_algo_id)

        new_trigger = float(new_sl_obj.get("triggerPrice", 0)) if new_sl_obj else None

        new_entry = None
        for attempt in range(3):
            for pos in exchange.get_positions(symbol):
                if pos["positionSide"] == position_side:
                    ep = float(pos["entryPrice"])
                    if ep > 0:
                        new_entry = ep
                    break
            if new_entry is not None:
                break
            time.sleep(1.0)

        expected_new_trigger = new_entry * (1 - SL_PCT / 100) if new_entry else None

        print(f"\n  new_entry={new_entry}")
        print(f"  new algoId={new_algo_id}")
        print(f"  new triggerPrice={new_trigger}")
        print(f"  expected triggerPrice={expected_new_trigger:.8f}" if expected_new_trigger else "  expected triggerPrice=N/A")

        # ------------------------------------------------------------------
        # CHECKS
        # ------------------------------------------------------------------
        print("\n=== CHECKS ===")
        passed = True

        # [1] averaging detected
        if averaged:
            print("  PASS [1]: averaging fill detected")
        else:
            print("  FAIL [1]: no averaging fill within timeout")
            passed = False

        # [2] old SL gone from exchange
        old_still_open = find_algo(initial_algo_id) is not None
        if not old_still_open:
            print(f"  PASS [2]: old SL removed from exchange  algoId={initial_algo_id}")
        else:
            print(f"  FAIL [2]: old SL still visible on exchange  algoId={initial_algo_id}")
            passed = False

        # [3] new algoId is different
        if new_algo_id is not None and new_algo_id != initial_algo_id:
            print(f"  PASS [3]: new algoId={new_algo_id}  (different from old {initial_algo_id})")
        else:
            print(f"  FAIL [3]: new algoId={new_algo_id}  initial={initial_algo_id}")
            passed = False

        # [4] new SL visible on exchange
        if new_sl_obj is not None:
            print(f"  PASS [4]: new SL visible on exchange  algoId={new_algo_id}")
        else:
            print(f"  FAIL [4]: new SL not visible on exchange  algoId={new_algo_id}")
            passed = False

        # [5] new triggerPrice matches formula
        if new_trigger is not None and expected_new_trigger is not None:
            tolerance = new_entry * 0.0005
            if abs(new_trigger - expected_new_trigger) <= tolerance:
                print(
                    f"  PASS [5]: triggerPrice={new_trigger:.8f}"
                    f"  expected={expected_new_trigger:.8f}"
                    f"  diff={abs(new_trigger - expected_new_trigger):.8f}"
                )
            else:
                print(
                    f"  FAIL [5]: triggerPrice={new_trigger:.8f}"
                    f"  expected={expected_new_trigger:.8f}"
                    f"  diff={abs(new_trigger - expected_new_trigger):.8f}"
                )
                passed = False
        else:
            print(f"  FAIL [5]: cannot check triggerPrice  new_trigger={new_trigger}  expected={expected_new_trigger}")
            passed = False

        # [6] new triggerPrice differs from initial (entry changed)
        if new_trigger is not None and initial_trigger is not None and abs(new_trigger - initial_trigger) > 1e-8:
            print(f"  PASS [6]: triggerPrice shifted  {initial_trigger:.8f} -> {new_trigger:.8f}")
        else:
            print(f"  FAIL [6]: triggerPrice did not change  initial={initial_trigger}  new={new_trigger}")
            passed = False

        # [7] session still alive
        if service.get_session(symbol, position_side) is not None:
            print("  PASS [7]: session still alive")
        else:
            print("  FAIL [7]: session was stopped unexpectedly")
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

        try:
            for o in get_open_algos(symbol):
                if o.get("positionSide") == position_side:
                    try:
                        exchange.cancel_algo_order(o["algoId"])
                        print(f"  cancelled algo algoId={o['algoId']}")
                    except Exception as e:
                        print(f"  cancel algo error: {e}")
        except Exception as e:
            print(f"  algo cleanup error: {e}")

        try:
            leftover = service.get_session(symbol, position_side)
            if leftover is not None:
                service.stop_session(symbol, position_side)
                print("  stopped LONG session")
        except Exception as e:
            print(f"  stop_session error (ignored): {e}")

        for pos in exchange.get_positions(symbol):
            if pos["positionSide"] == position_side:
                qty = abs(float(pos["positionAmt"]))
                if qty > 0:
                    exchange.close_position(symbol, "sell", qty)
                    print(f"  closed LONG position: qty={qty}")
                break

    print("\nTEST DONE")
