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

    for side in ("LONG", "SHORT"):
        leftover = service.get_session(symbol, side)
        if leftover is not None:
            service.stop_session(symbol, side)
            print(f"  stopped leftover {side} grid session")
        else:
            print(f"  no leftover {side} grid session")

    close_side_map = {"LONG": "sell", "SHORT": "buy"}
    for pos in exchange.get_positions(symbol):
        ps  = pos["positionSide"]
        qty = abs(float(pos["positionAmt"]))
        if ps in ("LONG", "SHORT") and qty > 0:
            exchange.close_position(symbol, close_side_map[ps], qty)
            print(f"  closed leftover {ps} position: qty={qty}")

    time.sleep(1.0)

    try:
        # ------------------------------------------------------------------
        # OPEN LONG + SHORT POSITIONS
        # ------------------------------------------------------------------
        print("\n=== OPEN LONG + SHORT POSITIONS ===")
        t0 = time.time()

        exchange.open_market_position(symbol, "buy",  usdt_amount=8.5, leverage=5)
        exchange.open_market_position(symbol, "sell", usdt_amount=8.5, leverage=5)
        time.sleep(1.0)

        t_positions_opened = time.time()
        print(f"  [TIMING] positions opened in {t_positions_opened - t0:.2f}s")

        long_entry  = None
        long_qty    = 0.0
        short_entry = None
        short_qty   = 0.0

        for pos in exchange.get_positions(symbol):
            ps  = pos["positionSide"]
            qty = abs(float(pos["positionAmt"]))
            if ps == "LONG" and qty > 0:
                long_entry = float(pos["entryPrice"])
                long_qty   = qty
            elif pos["positionSide"] == "SHORT" and abs(float(pos["positionAmt"])) > 0:
                short_entry = float(pos["entryPrice"])
                short_qty   = abs(float(pos["positionAmt"]))

        print(f"  LONG:  entry={long_entry}  qty={long_qty}")
        print(f"  SHORT: entry={short_entry}  qty={short_qty}")

        if long_qty == 0 or long_entry is None:
            print("FAIL: LONG position not opened")
            sys.exit(1)
        if short_qty == 0 or short_entry is None:
            print("FAIL: SHORT position not opened")
            sys.exit(1)

        # ------------------------------------------------------------------
        # START GRID SESSIONS
        # ------------------------------------------------------------------
        print("\n=== START GRID SESSIONS ===")
        current_price = exchange.get_price(symbol)
        print(f"  current_price={current_price:.8f}")

        long_first  = current_price * 0.950
        long_last   = current_price * 0.920
        short_first = current_price * 1.050
        short_last  = current_price * 1.080

        t_sessions_start = time.time()

        long_session = service.start_session(
            symbol=symbol,
            position_side="LONG",
            total_budget=20.0,
            levels_count=2,
            step_percent=1.0,
            orders_count=2,
            first_price=long_first,
            last_price=long_last,
            distribution_mode="step",
            distribution_value=1.0,
        )

        short_session = service.start_session(
            symbol=symbol,
            position_side="SHORT",
            total_budget=20.0,
            levels_count=2,
            step_percent=1.0,
            orders_count=2,
            first_price=short_first,
            last_price=short_last,
            distribution_mode="step",
            distribution_value=1.0,
        )

        t_sessions_started = time.time()
        print(f"  [TIMING] sessions started in {t_sessions_started - t_sessions_start:.2f}s")

        print(f"\n  LONG  session_id: {long_session.session_id}")
        for lvl in long_session.levels:
            print(f"    [{lvl.index}] order_id={lvl.order_id}  price={lvl.price:.8f}  qty={lvl.qty}  status={lvl.status}")

        print(f"\n  SHORT session_id: {short_session.session_id}")
        for lvl in short_session.levels:
            print(f"    [{lvl.index}] order_id={lvl.order_id}  price={lvl.price:.8f}  qty={lvl.qty}  status={lvl.status}")

        time.sleep(0.5)

        # ------------------------------------------------------------------
        # SET REPRICE MODE FOR BOTH SIDES
        # LONG:  remaining TP price = new_entry * (1 + tp_pct/100)
        # SHORT: remaining TP price = new_entry * (1 - tp_pct/100)
        # ------------------------------------------------------------------
        service.set_tp_update_mode(symbol, "LONG",  "reprice")
        service.set_tp_update_mode(symbol, "SHORT", "reprice")
        print(f"\n  LONG  tp_update_mode = 'reprice'")
        print(f"  SHORT tp_update_mode = 'reprice'")

        # ------------------------------------------------------------------
        # PLACE TP ORDERS FOR BOTH SIDES
        #
        # LONG:
        #   TP1 at +0.3%  — close, fills naturally when market rises slightly
        #   TP2 at +8.0%  — far,   stays pending, recalculated after averaging
        #
        # SHORT:
        #   TP1 at -0.3%  — close, fills naturally when market drops slightly
        #   TP2 at -8.0%  — far,   stays pending, recalculated after averaging
        #
        # TP price formulas:
        #   LONG  TP: entry * (1 + tp_pct/100)
        #   SHORT TP: entry * (1 - tp_pct/100)
        # ------------------------------------------------------------------
        print("\n=== PLACE TP ORDERS ===")

        long_take_profits = [
            {"tp_percent": 0.3, "close_percent": 50},
            {"tp_percent": 8.0, "close_percent": 50},
        ]
        short_take_profits = [
            {"tp_percent": 0.3, "close_percent": 50},
            {"tp_percent": 8.0, "close_percent": 50},
        ]

        t_tp_start = time.time()

        long_placed = service.place_grid_tp_orders(
            symbol=symbol,
            position_side="LONG",
            take_profits=long_take_profits,
        )
        short_placed = service.place_grid_tp_orders(
            symbol=symbol,
            position_side="SHORT",
            take_profits=short_take_profits,
        )

        t_tp_placed = time.time()
        print(f"  [TIMING] TP placed in {t_tp_placed - t_tp_start:.2f}s")

        # Snapshots of initial state
        initial_tps = {
            "LONG":  list(service._grid_tp_orders.get((symbol, "LONG"),  [])),
            "SHORT": list(service._grid_tp_orders.get((symbol, "SHORT"), [])),
        }
        tp1_initial_id = {
            "LONG":  initial_tps["LONG"][0]["order_id"],
            "SHORT": initial_tps["SHORT"][0]["order_id"],
        }
        tp2_initial_id = {
            "LONG":  initial_tps["LONG"][1]["order_id"],
            "SHORT": initial_tps["SHORT"][1]["order_id"],
        }

        print(f"\n  === INITIAL STATE ===")
        for side in ("LONG", "SHORT"):
            tps    = initial_tps[side]
            entry  = long_entry if side == "LONG" else short_entry
            sign   = 1 if side == "LONG" else -1
            op     = "+" if sign > 0 else "-"
            prices = [f"{tp['price']:.8f}" for tp in tps]
            print(f"  {side} TP ids:    {[tp['order_id'] for tp in tps]}")
            print(f"  {side} TP prices: {prices}")
            print(f"    TP1 expected: {entry:.8f} * (1 {op} 0.003) = {entry * (1 + sign * 0.003):.8f}")
            print(f"    TP2 expected: {entry:.8f} * (1 {op} 0.08)  = {entry * (1 + sign * 0.08):.8f}")
            print(f"  {side} TP qtys:   {[tp['qty'] for tp in tps]}")

        # ------------------------------------------------------------------
        # START WATCHER FOR BOTH SIDES
        # ------------------------------------------------------------------
        print("\n=== START WATCHER ===")
        watcher.start_watching(symbol, "LONG")
        watcher.start_watching(symbol, "SHORT")
        print(f"  watcher watching: {list(watcher._watched.keys())}")

        # Averaging grid level references for manual instruction display
        avg_level = {
            "LONG":  long_session.levels[0],
            "SHORT": short_session.levels[0],
        }

        # ------------------------------------------------------------------
        # UNIFIED WAIT LOOP  (order-agnostic, up to 180s)
        #
        # State machine per side:
        #   "waiting_tp1"  -> TP1 fills (count 2->1)       -> "tp1_filled"
        #   "tp1_filled"   -> averaging fill (id changes)   -> "done"
        #
        # Instructions for each averaging are printed dynamically
        # when TP1 is detected on that side.
        # ------------------------------------------------------------------
        print(f"\n=== WAIT LOOP (order-agnostic) ===")
        print(f"  Both sides monitored simultaneously.")
        print(f"  Instructions will appear when TP1 fills on each side.")

        side_state = {
            side: {
                "phase":                  "waiting_tp1",
                "after_tp1_snap":         None,
                "after_tp1_remaining_id": None,
                "pos_after_tp1":          None,
                "tp1_fill_time":          None,
                "after_avg_snap":         None,
                "new_entry":              None,
                "new_qty":                None,
                "expected_tp2_price":     None,
                "avg_time":               None,
            }
            for side in ("LONG", "SHORT")
        }

        order_of_tp1 = []   # sides in the order their TP1 was detected
        order_of_avg = []   # sides in the order their averaging was detected

        t_loop_start   = time.time()
        loop_completed = False

        for tick in range(180):
            for side in ("LONG", "SHORT"):
                st          = side_state[side]
                current_tps = list(service._grid_tp_orders.get((symbol, side), []))

                # ---- STAGE 1: waiting for TP1 fill ----
                if st["phase"] == "waiting_tp1":
                    if len(current_tps) == 1:
                        st["phase"]                  = "tp1_filled"
                        st["after_tp1_snap"]         = current_tps
                        st["after_tp1_remaining_id"] = current_tps[0]["order_id"]
                        st["tp1_fill_time"]          = time.time()
                        order_of_tp1.append(side)

                        pos_after = 0.0
                        for pos in exchange.get_positions(symbol):
                            if pos["positionSide"] == side:
                                pos_after = abs(float(pos["positionAmt"]))
                                break
                        st["pos_after_tp1"] = pos_after

                        tp1_lag = st["tp1_fill_time"] - t_loop_start
                        rem     = current_tps[0]
                        print(f"\n  [{side}] TP1 FILL DETECTED at +{tp1_lag:.1f}s")
                        print(f"  [{side}] _grid_tp_orders count: 2 -> 1")
                        print(f"  [{side}] remaining TP:  id={rem['order_id']}  tp_percent={rem['tp_percent']}%  price={rem['price']:.8f}  qty={rem['qty']}")
                        print(f"  [{side}] position qty after partial close: {pos_after}")
                        print(f"  [{side}] _base_position_qty: {service._base_position_qty.get((symbol, side))}")
                        lvl = avg_level[side]
                        print(f"\n  *** ACTION REQUIRED: Average {side} position ***")
                        print(f"  Drag {side} level[1] order_id={lvl.order_id}  price={lvl.price:.8f}")
                        print(f"  to near current price ~{exchange.get_price(symbol):.8f}")

                # ---- STAGE 2: waiting for averaging fill ----
                elif st["phase"] == "tp1_filled":
                    remaining_id = st["after_tp1_remaining_id"]
                    if (
                        len(current_tps) == 1
                        and current_tps[0]["order_id"] != remaining_id
                    ):
                        st["phase"]          = "done"
                        st["after_avg_snap"] = current_tps
                        st["avg_time"]       = time.time()
                        order_of_avg.append(side)

                        for pos in exchange.get_positions(symbol):
                            if pos["positionSide"] == side:
                                st["new_entry"] = float(pos["entryPrice"])
                                st["new_qty"]   = abs(float(pos["positionAmt"]))
                                break

                        rem    = current_tps[0]
                        tp_pct = rem["tp_percent"]
                        if st["new_entry"]:
                            if side == "LONG":
                                st["expected_tp2_price"] = st["new_entry"] * (1 + tp_pct / 100)
                            else:
                                st["expected_tp2_price"] = st["new_entry"] * (1 - tp_pct / 100)

                        avg_lag = st["avg_time"] - st["tp1_fill_time"]
                        sign_str = "+ " if side == "LONG" else "- "
                        formula  = f"{st['new_entry']:.8f} * (1 {sign_str}{tp_pct}/100)" if st["new_entry"] else "N/A"
                        print(f"\n  [{side}] AVERAGING FILL DETECTED at +{avg_lag:.1f}s after TP1 fill")
                        print(f"  [{side}] === STATE AFTER AVERAGING ===")
                        if st["new_entry"]:
                            print(f"  [{side}] new avg entry:      {st['new_entry']:.8f}")
                        print(f"  [{side}] new position qty:   {st['new_qty']}")
                        print(f"  [{side}] remaining TP order_id: {rem['order_id']}  (was {remaining_id})")
                        print(f"  [{side}] remaining TP tp_percent: {rem['tp_percent']}%")
                        print(f"  [{side}] remaining TP actual price:   {rem['price']:.8f}")
                        if st["expected_tp2_price"]:
                            print(f"  [{side}] remaining TP expected price: {st['expected_tp2_price']:.8f}  ({formula})")
                        print(f"  [{side}] remaining TP qty: {rem['qty']}  (expected: full position ~{st['new_qty']})")

            done_count = sum(1 for s in ("LONG", "SHORT") if side_state[s]["phase"] == "done")
            if done_count == 2:
                loop_completed = True
                t_both_done = time.time()
                print(f"\n  Both sides completed lifecycle at +{t_both_done - t_loop_start:.1f}s from loop start")
                break

            time.sleep(1.0)

        if not loop_completed:
            incomplete = [s for s in ("LONG", "SHORT") if side_state[s]["phase"] != "done"]
            print(f"\nFAIL: timeout at 180s -- incomplete sides: {incomplete}")
            for s in incomplete:
                print(f"  [{s}] phase={side_state[s]['phase']}")
            sys.exit(1)

        # ------------------------------------------------------------------
        # TIMING SUMMARY
        # ------------------------------------------------------------------
        print(f"\n=== TIMING SUMMARY ===")
        print(f"  positions opened:     +{t_positions_opened - t0:.2f}s from test start")
        print(f"  sessions started:     +{t_sessions_started - t0:.2f}s from test start")
        print(f"  TP placed:            +{t_tp_placed - t0:.2f}s from test start")
        print(f"  order of TP1 fills:   {order_of_tp1}")
        print(f"  order of avg recalcs: {order_of_avg}")
        for i, side in enumerate(order_of_tp1):
            st      = side_state[side]
            tp1_lag = st["tp1_fill_time"] - t_loop_start
            avg_lag = st["avg_time"] - st["tp1_fill_time"]
            label   = "1st" if i == 0 else "2nd"
            print(f"  {label} TP1 fill   ({side}): +{tp1_lag:.1f}s from loop start")
            print(f"  {label} avg recalc  ({side}): +{avg_lag:.1f}s after TP1 fill")

        # ------------------------------------------------------------------
        # CHECKS
        # ------------------------------------------------------------------
        print("\n=== CHECKS ===")
        passed = True

        # [1] LONG position opened
        if long_qty > 0 and long_entry is not None:
            print(f"  PASS: LONG position opened  entry={long_entry:.8f}  qty={long_qty}")
        else:
            print("  FAIL: LONG position not opened")
            passed = False

        # [2] SHORT position opened
        if short_qty > 0 and short_entry is not None:
            print(f"  PASS: SHORT position opened  entry={short_entry:.8f}  qty={short_qty}")
        else:
            print("  FAIL: SHORT position not opened")
            passed = False

        # [3] LONG session alive
        long_s = service.get_session(symbol, "LONG")
        if long_s is not None:
            print(f"  PASS: LONG session alive  session_id={long_s.session_id}")
        else:
            print("  FAIL: LONG session not found")
            passed = False

        # [4] SHORT session alive
        short_s = service.get_session(symbol, "SHORT")
        if short_s is not None:
            print(f"  PASS: SHORT session alive  session_id={short_s.session_id}")
        else:
            print("  FAIL: SHORT session not found")
            passed = False

        # [5] LONG initial TP count = 2
        if len(initial_tps["LONG"]) == 2:
            print(f"  PASS: LONG initial TP count = 2")
        else:
            print(f"  FAIL: LONG initial TP count = {len(initial_tps['LONG'])}, expected 2")
            passed = False

        # [6] SHORT initial TP count = 2
        if len(initial_tps["SHORT"]) == 2:
            print(f"  PASS: SHORT initial TP count = 2")
        else:
            print(f"  FAIL: SHORT initial TP count = {len(initial_tps['SHORT'])}, expected 2")
            passed = False

        # [7] both sides completed full lifecycle
        if loop_completed:
            print(f"  PASS: both sides completed TP1-fill -> averaging lifecycle  order={order_of_tp1}")
        else:
            print("  FAIL: not both sides completed lifecycle")
            passed = False

        # Per-side checks [8..19]
        for side in ("LONG", "SHORT"):
            st            = side_state[side]
            after_tp1_rem = st["after_tp1_snap"][0] if st["after_tp1_snap"] else None
            after_avg_rem = st["after_avg_snap"][0]  if st["after_avg_snap"] else None

            # [8/14] TP1 fill detected
            if st["tp1_fill_time"] is not None:
                tp1_lag = st["tp1_fill_time"] - t_loop_start
                print(f"  PASS: {side} TP1 fill detected  (count 2 -> 1 at +{tp1_lag:.1f}s)")
            else:
                print(f"  FAIL: {side} TP1 fill not detected")
                passed = False

            # [9/15] TP1 removed — remaining id = original TP2
            if after_tp1_rem is not None:
                if after_tp1_rem["order_id"] == tp2_initial_id[side]:
                    print(f"  PASS: {side} TP1 removed  remaining=TP2 (id={after_tp1_rem['order_id']})")
                else:
                    print(f"  FAIL: {side} remaining id={after_tp1_rem['order_id']}  expected TP2 id={tp2_initial_id[side]}")
                    passed = False
            else:
                print(f"  FAIL: {side} after_tp1_snap missing")
                passed = False

            # [10/16] remaining TP has correct tp_percent (8.0)
            if after_tp1_rem is not None:
                if after_tp1_rem["tp_percent"] == 8.0:
                    print(f"  PASS: {side} remaining TP is TP2  tp_percent=8.0%")
                else:
                    print(f"  FAIL: {side} remaining tp_percent={after_tp1_rem['tp_percent']}%, expected 8.0")
                    passed = False

            # [11/17] averaging fill detected
            if st["avg_time"] is not None:
                avg_lag = st["avg_time"] - st["tp1_fill_time"]
                print(f"  PASS: {side} averaging fill detected  (TP2 id changed at +{avg_lag:.1f}s after TP1 fill)")
            else:
                print(f"  FAIL: {side} averaging fill not detected")
                passed = False

            # [12/18] remaining TP2 qty = full new position
            if after_avg_rem is not None and st["new_qty"] is not None:
                actual_qty   = after_avg_rem["qty"]
                expected_qty = st["new_qty"]
                if abs(actual_qty - expected_qty) < 1.0:
                    print(f"  PASS: {side} remaining TP2 qty covers full position  qty={actual_qty}  position={expected_qty}")
                else:
                    print(f"  FAIL: {side} remaining TP2 qty={actual_qty}  expected ~{expected_qty}")
                    passed = False
            else:
                print(f"  FAIL: {side} after_avg_snap or new_qty missing")
                passed = False

            # [13/19] remaining TP2 price correct (reprice mode)
            if after_avg_rem is not None and st["expected_tp2_price"] is not None:
                actual_price   = after_avg_rem["price"]
                expected_price = st["expected_tp2_price"]
                price_ok = abs(actual_price - expected_price) / expected_price < 0.001
                if price_ok:
                    print(f"  PASS: {side} remaining TP2 price correct (reprice)"
                          f"  actual={actual_price:.8f}  expected={expected_price:.8f}")
                else:
                    print(f"  FAIL: {side} remaining TP2 price={actual_price:.8f}"
                          f"  expected={expected_price:.8f}"
                          f"  (new_entry={st['new_entry']:.8f})")
                    passed = False
            else:
                print(f"  FAIL: {side} cannot verify TP2 price -- missing data")
                passed = False

        # [20] both sessions still alive
        long_alive  = service.get_session(symbol, "LONG")  is not None
        short_alive = service.get_session(symbol, "SHORT") is not None
        if long_alive and short_alive:
            print(f"  PASS: both sessions still alive")
        else:
            print(f"  FAIL: sessions not alive  LONG={long_alive}  SHORT={short_alive}")
            passed = False

        # [21] watcher watching both sides
        watches_long  = (symbol, "LONG")  in watcher._watched
        watches_short = (symbol, "SHORT") in watcher._watched
        if watches_long and watches_short:
            print(f"  PASS: watcher watching both sides")
        else:
            print(f"  FAIL: watcher not watching both  LONG={watches_long}  SHORT={watches_short}")
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

        for side in ("LONG", "SHORT"):
            tp_state = service._grid_tp_orders.get((symbol, side), [])
            for tp in tp_state:
                try:
                    exchange.cancel_order(symbol, tp["order_id"])
                    print(f"  cancelled {side} TP order_id={tp['order_id']}")
                except Exception as e:
                    print(f"  cancel {side} TP order_id={tp['order_id']} error: {e}")
            service._grid_tp_orders.pop((symbol, side), None)
            service._tp_update_mode.pop((symbol, side), None)

            leftover = service.get_session(symbol, side)
            if leftover is not None:
                service.stop_session(symbol, side)
                print(f"  stopped {side} session")

        close_side_map = {"LONG": "sell", "SHORT": "buy"}
        for pos in exchange.get_positions(symbol):
            ps  = pos["positionSide"]
            qty = abs(float(pos["positionAmt"]))
            if ps in ("LONG", "SHORT") and qty > 0:
                exchange.close_position(symbol, close_side_map[ps], qty)
                print(f"  closed {ps} position: qty={qty}")

    print("\nTEST DONE")
