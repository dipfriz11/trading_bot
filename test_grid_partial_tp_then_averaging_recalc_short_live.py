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
            elif ps == "SHORT" and qty > 0:
                short_entry = float(pos["entryPrice"])
                short_qty   = qty

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

        long_first  = current_price * 0.950   # -5% below market
        long_last   = current_price * 0.920   # -8% below market
        short_first = current_price * 1.050   # +5% above market
        short_last  = current_price * 1.080   # +8% above market

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
        # SET REPRICE MODE FOR SHORT
        # After averaging fill the remaining TP price will be recalculated
        # from the new average entry: price = new_entry * (1 - tp_pct/100)
        # ------------------------------------------------------------------
        service.set_tp_update_mode(symbol, "SHORT", "reprice")
        print(f"\n  SHORT tp_update_mode = 'reprice'")

        # ------------------------------------------------------------------
        # PLACE TP ORDERS
        #
        # SHORT:
        #   TP1 at -0.3%  — close, will fill naturally with small market move DOWN
        #   TP2 at -8.0%  — far,   stays pending, recalculated after averaging
        #   close_percent: 50/50  (sum = 100)
        #
        # LONG:
        #   TP1 at +5.0%  — far, not touched during this test
        #   TP2 at +10.0% — far, not touched during this test
        #
        # SHORT TP price formula:
        #   TP1: entry * (1 - 0.3/100)  = entry * 0.997
        #   TP2: entry * (1 - 8.0/100)  = entry * 0.920
        #
        # TP1 SHORT fills -> _grid_tp_orders SHORT goes 2 -> 1
        # Averaging SHORT -> remaining TP2: new order_id, qty = full position,
        #                    price = new_avg_entry * (1 - 8.0/100)
        # ------------------------------------------------------------------
        print("\n=== PLACE TP ORDERS ===")

        short_take_profits = [
            {"tp_percent": 0.3, "close_percent": 50},
            {"tp_percent": 8.0, "close_percent": 50},
        ]
        long_take_profits = [
            {"tp_percent": 5.0,  "close_percent": 50},
            {"tp_percent": 10.0, "close_percent": 50},
        ]

        t_tp_start = time.time()

        short_placed = service.place_grid_tp_orders(
            symbol=symbol,
            position_side="SHORT",
            take_profits=short_take_profits,
        )

        long_placed = service.place_grid_tp_orders(
            symbol=symbol,
            position_side="LONG",
            take_profits=long_take_profits,
        )

        t_tp_placed = time.time()
        print(f"  [TIMING] TP placed in {t_tp_placed - t_tp_start:.2f}s")

        # Snapshots of initial state
        initial_short_tps = list(service._grid_tp_orders.get((symbol, "SHORT"), []))
        initial_long_tps  = list(service._grid_tp_orders.get((symbol, "LONG"),  []))

        initial_short_ids    = {tp["order_id"] for tp in initial_short_tps}
        initial_short_prices = [f"{tp['price']:.8f}" for tp in initial_short_tps]
        initial_short_qtys   = [tp["qty"] for tp in initial_short_tps]

        initial_long_ids    = {tp["order_id"] for tp in initial_long_tps}
        initial_long_prices = [f"{tp['price']:.8f}" for tp in initial_long_tps]
        initial_long_qtys   = [tp["qty"] for tp in initial_long_tps]

        # TP1 is index 0 (sorted by tp_percent asc), TP2 is index 1
        tp1_initial_id = initial_short_tps[0]["order_id"]
        tp2_initial_id = initial_short_tps[1]["order_id"]

        print(f"\n  === INITIAL STATE ===")
        print(f"  SHORT TP ids:    {initial_short_ids}")
        print(f"  SHORT TP prices: {initial_short_prices}")
        print(f"    TP1 expected: entry*0.997 = {short_entry * 0.997:.8f}")
        print(f"    TP2 expected: entry*0.920 = {short_entry * 0.920:.8f}")
        print(f"  SHORT TP qtys:   {initial_short_qtys}")
        print(f"  LONG  TP ids:    {initial_long_ids}")
        print(f"  LONG  TP prices: {initial_long_prices}")
        print(f"  LONG  TP qtys:   {initial_long_qtys}")

        # ------------------------------------------------------------------
        # START WATCHER FOR BOTH SIDES
        # ------------------------------------------------------------------
        print("\n=== START WATCHER ===")
        watcher.start_watching(symbol, "LONG")
        watcher.start_watching(symbol, "SHORT")
        print(f"  watcher watching: {list(watcher._watched.keys())}")

        # ------------------------------------------------------------------
        # PHASE 1: WAIT FOR SHORT TP1 TO FILL NATURALLY
        # TP1 is at -0.3% from entry -- small market move downward fills it.
        # watcher detects fill via check_tp_fills():
        #   _grid_tp_orders SHORT: 2 -> 1
        #   _base_position_qty: ~15 -> ~7  (position after partial close)
        # ------------------------------------------------------------------
        print(f"\n=== PHASE 1: WAITING FOR SHORT TP1 FILL (natural) ===")
        print(f"  SHORT TP1 price = {short_placed[0]['price']:.8f}  (-0.3% from entry={short_entry:.8f})")
        print(f"  Waiting up to 60s for market to drop to TP1...")

        t_loop_start      = time.time()
        tp1_fill_detected = False
        tp1_fill_time     = None
        after_tp1_snap    = None

        for _ in range(60):
            current_tps = service._grid_tp_orders.get((symbol, "SHORT"), [])
            if len(current_tps) == 1:
                tp1_fill_detected = True
                tp1_fill_time     = time.time()
                after_tp1_snap    = list(current_tps)
                break
            time.sleep(1.0)

        if not tp1_fill_detected:
            print("FAIL: SHORT TP1 not filled within 60s -- aborting")
            sys.exit(1)

        tp1_lag = tp1_fill_time - t_loop_start
        print(f"  [TIMING] SHORT TP1 fill detected at +{tp1_lag:.1f}s from loop start")

        after_tp1_remaining_tp = after_tp1_snap[0]
        after_tp1_remaining_id = after_tp1_remaining_tp["order_id"]

        # Read position qty after TP1 partial close
        pos_after_tp1_qty = 0.0
        for pos in exchange.get_positions(symbol):
            if pos["positionSide"] == "SHORT":
                pos_after_tp1_qty = abs(float(pos["positionAmt"]))
                break

        print(f"\n  === STATE AFTER SHORT TP1 FILL ===")
        print(f"  _grid_tp_orders SHORT count: 2 -> 1")
        print(f"  remaining TP order_id: {after_tp1_remaining_id}")
        print(f"  remaining TP tp_percent: {after_tp1_remaining_tp['tp_percent']}%")
        print(f"  remaining TP price:      {after_tp1_remaining_tp['price']:.8f}")
        print(f"  remaining TP qty:        {after_tp1_remaining_tp['qty']}")
        print(f"  SHORT position qty after partial close: {pos_after_tp1_qty}")
        print(f"  _base_position_qty now:  {service._base_position_qty.get((symbol, 'SHORT'))}")

        # Snapshot LONG for isolation baseline
        long_snap_after_tp1   = list(service._grid_tp_orders.get((symbol, "LONG"), []))
        long_ids_after_tp1    = {tp["order_id"] for tp in long_snap_after_tp1}
        long_qtys_after_tp1   = [tp["qty"]      for tp in long_snap_after_tp1]
        long_prices_after_tp1 = [f"{tp['price']:.8f}" for tp in long_snap_after_tp1]

        # ------------------------------------------------------------------
        # PHASE 2: MANUAL AVERAGING -- drag SHORT grid level[1] near market
        # SHORT grid levels are ABOVE market (+5%/+8%).
        # Drag level[1] DOWN near current price to trigger fill.
        # After averaging fill watcher runs:
        #   check_grid_fills() -> level[1] filled (position delta)
        #   update_grid_tp_orders_reprice():
        #     existing = [TP2]   (only remaining after TP1 fill)
        #     tp_qty   = full new SHORT position (last/only entry -> uses remainder)
        #     tp_price = new_avg_entry * (1 - 8.0/100)
        # Detection: remaining TP id changes (same count=1, new order_id)
        # ------------------------------------------------------------------
        print(f"\n=== PHASE 2: MANUAL ACTION -- AVERAGE SHORT POSITION ===")
        print(f"  Drag this order near current price to trigger averaging fill:")
        print(f"  SHORT level[1] order_id={short_session.levels[0].order_id}  price={short_session.levels[0].price:.8f}")
        print(f"  current price ~{exchange.get_price(symbol):.8f}")
        print(f"  After fill watcher will: cancel old TP2, place new TP2 with full qty + repriced")
        print(f"  Waiting up to 60s...")

        averaging_detected   = False
        averaging_time       = None
        after_averaging_snap = None

        for _ in range(60):
            current_tps = service._grid_tp_orders.get((symbol, "SHORT"), [])
            # averaging update: count stays 1, but order_id changes
            if (
                len(current_tps) == 1
                and current_tps[0]["order_id"] != after_tp1_remaining_id
            ):
                averaging_detected   = True
                averaging_time       = time.time()
                after_averaging_snap = list(current_tps)
                break
            time.sleep(1.0)

        if not averaging_detected:
            print("FAIL: SHORT averaging fill not detected within 60s -- aborting")
            sys.exit(1)

        averaging_lag = averaging_time - tp1_fill_time
        print(f"  [TIMING] SHORT averaging fill detected at +{averaging_lag:.1f}s after TP1 fill")

        # Read new avg entry and qty from exchange
        new_short_entry = None
        new_short_qty   = 0.0
        for pos in exchange.get_positions(symbol):
            if pos["positionSide"] == "SHORT":
                new_short_entry = float(pos["entryPrice"])
                new_short_qty   = abs(float(pos["positionAmt"]))
                break

        remaining_tp2 = after_averaging_snap[0]

        # Expected TP2 price in reprice mode for SHORT:
        #   price = new_avg_entry * (1 - tp_percent/100)
        expected_tp2_price = (new_short_entry * (1 - remaining_tp2["tp_percent"] / 100)
                              if new_short_entry else None)

        print(f"\n  === STATE AFTER SHORT AVERAGING FILL ===")
        if new_short_entry:
            print(f"  new SHORT avg entry:     {new_short_entry:.8f}")
        else:
            print(f"  new SHORT avg entry: N/A")
        print(f"  new SHORT position qty:  {new_short_qty}")
        print(f"  remaining TP order_id:   {remaining_tp2['order_id']}  (was {after_tp1_remaining_id})")
        print(f"  remaining TP tp_percent: {remaining_tp2['tp_percent']}%")
        print(f"  remaining TP actual price:   {remaining_tp2['price']:.8f}")
        if expected_tp2_price:
            print(f"  remaining TP expected price: {expected_tp2_price:.8f}"
                  f"  (formula: {new_short_entry:.8f} * (1 - {remaining_tp2['tp_percent']}/100))")
        print(f"  remaining TP qty:        {remaining_tp2['qty']}  (expected: full position ~{new_short_qty})")

        # Snapshot LONG after averaging for isolation check
        long_snap_after_avg   = list(service._grid_tp_orders.get((symbol, "LONG"), []))
        long_ids_after_avg    = {tp["order_id"] for tp in long_snap_after_avg}
        long_qtys_after_avg   = [tp["qty"]      for tp in long_snap_after_avg]
        long_prices_after_avg = [f"{tp['price']:.8f}" for tp in long_snap_after_avg]

        # ------------------------------------------------------------------
        # TIMING SUMMARY
        # ------------------------------------------------------------------
        print(f"\n=== TIMING SUMMARY ===")
        print(f"  positions opened:         +{t_positions_opened - t0:.2f}s from test start")
        print(f"  sessions started:         +{t_sessions_started - t0:.2f}s from test start")
        print(f"  TP placed:                +{t_tp_placed - t0:.2f}s from test start")
        print(f"  SHORT TP1 fill detected:  +{tp1_lag:.1f}s from loop start")
        print(f"  SHORT averaging detected: +{averaging_lag:.1f}s after TP1 fill")

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

        # [5] initial SHORT TP count = 2
        if len(initial_short_tps) == 2:
            print(f"  PASS: SHORT initial TP count = 2")
        else:
            print(f"  FAIL: SHORT initial TP count = {len(initial_short_tps)}, expected 2")
            passed = False

        # [6] initial LONG TP count = 2
        if len(initial_long_tps) == 2:
            print(f"  PASS: LONG initial TP count = 2")
        else:
            print(f"  FAIL: LONG initial TP count = {len(initial_long_tps)}, expected 2")
            passed = False

        # [7] TP1 SHORT fill detected -- count 2 -> 1
        if tp1_fill_detected:
            print(f"  PASS: SHORT TP1 fill detected  (count 2 -> 1 at +{tp1_lag:.1f}s)")
        else:
            print("  FAIL: SHORT TP1 fill not detected within 60s")
            passed = False

        # [8] TP1 removed -- remaining id matches original TP2, not TP1
        if after_tp1_remaining_id == tp2_initial_id:
            print(f"  PASS: TP1 removed from _grid_tp_orders SHORT  remaining=TP2 (id={after_tp1_remaining_id})")
        else:
            print(f"  FAIL: remaining id={after_tp1_remaining_id}  expected TP2 id={tp2_initial_id}")
            passed = False

        # [9] remaining SHORT TP is TP2 (tp_percent=8.0)
        if after_tp1_remaining_tp["tp_percent"] == 8.0:
            print(f"  PASS: remaining SHORT TP is TP2  tp_percent={after_tp1_remaining_tp['tp_percent']}%")
        else:
            print(f"  FAIL: remaining tp_percent={after_tp1_remaining_tp['tp_percent']}%, expected 8.0")
            passed = False

        # [10] averaging fill detected -- remaining TP id changed
        if averaging_detected:
            print(f"  PASS: SHORT averaging fill detected  (TP2 id changed at +{averaging_lag:.1f}s after TP1 fill)")
        else:
            print("  FAIL: SHORT averaging fill not detected within 60s")
            passed = False

        # [11] remaining SHORT TP2 qty = full new position
        actual_qty   = remaining_tp2["qty"]
        expected_qty = new_short_qty
        if abs(actual_qty - expected_qty) < 1.0:
            print(f"  PASS: remaining SHORT TP2 qty covers full position  qty={actual_qty}  position={expected_qty}")
        else:
            print(f"  FAIL: remaining SHORT TP2 qty={actual_qty}  expected ~{expected_qty}  (full new position)")
            passed = False

        # [12] remaining SHORT TP2 price repriced from new avg entry (reprice mode)
        #      formula: new_avg_entry * (1 - tp_percent/100)
        actual_price = remaining_tp2["price"]
        if expected_tp2_price is not None:
            price_ok = abs(actual_price - expected_tp2_price) / expected_tp2_price < 0.001
            if price_ok:
                print(f"  PASS: remaining SHORT TP2 price correct (reprice mode)"
                      f"  actual={actual_price:.8f}  expected={expected_tp2_price:.8f}")
            else:
                print(f"  FAIL: remaining SHORT TP2 price={actual_price:.8f}"
                      f"  expected={expected_tp2_price:.8f}"
                      f"  (new_entry={new_short_entry:.8f} * 0.92)")
                passed = False
        else:
            print("  FAIL: could not read new SHORT entry price to verify TP2 reprice")
            passed = False

        # [13] LONG TP ids unchanged throughout
        if long_ids_after_avg == initial_long_ids:
            print(f"  PASS: LONG TP ids unchanged throughout")
        else:
            print(f"  FAIL: LONG TP ids changed  initial={initial_long_ids}  after={long_ids_after_avg}")
            passed = False

        # [14] LONG TP qty unchanged throughout
        if long_qtys_after_avg == initial_long_qtys:
            print(f"  PASS: LONG TP qty unchanged throughout")
        else:
            print(f"  FAIL: LONG TP qty changed  initial={initial_long_qtys}  after={long_qtys_after_avg}")
            passed = False

        # [15] LONG TP prices unchanged throughout
        if long_prices_after_avg == initial_long_prices:
            print(f"  PASS: LONG TP prices unchanged throughout")
        else:
            print(f"  FAIL: LONG TP prices changed  initial={initial_long_prices}  after={long_prices_after_avg}")
            passed = False

        # [16] both sessions still alive
        long_alive  = service.get_session(symbol, "LONG")  is not None
        short_alive = service.get_session(symbol, "SHORT") is not None
        if long_alive and short_alive:
            print(f"  PASS: both sessions still alive")
        else:
            print(f"  FAIL: sessions not alive  LONG={long_alive}  SHORT={short_alive}")
            passed = False

        # [17] watcher watching both sides
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
