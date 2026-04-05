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
        # OPEN BOTH POSITIONS
        # ------------------------------------------------------------------
        print("\n=== OPEN LONG + SHORT POSITIONS ===")
        t0 = time.time()

        exchange.open_market_position(symbol, "buy",  usdt_amount=8.5, leverage=5)
        exchange.open_market_position(symbol, "sell", usdt_amount=8.5, leverage=5)
        time.sleep(1.0)

        t_positions_opened = time.time()
        print(f"  [TIMING] both positions opened in {t_positions_opened - t0:.2f}s")

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
        sessions_map = {"LONG": long_session, "SHORT": short_session}

        print(f"  [TIMING] both sessions started in {t_sessions_started - t_sessions_start:.2f}s")

        print(f"\n  LONG  session_id: {long_session.session_id}")
        for lvl in long_session.levels:
            print(f"    [{lvl.index}] order_id={lvl.order_id}  price={lvl.price:.8f}  qty={lvl.qty}  status={lvl.status}")

        print(f"\n  SHORT session_id: {short_session.session_id}")
        for lvl in short_session.levels:
            print(f"    [{lvl.index}] order_id={lvl.order_id}  price={lvl.price:.8f}  qty={lvl.qty}  status={lvl.status}")

        time.sleep(0.5)

        # ------------------------------------------------------------------
        # PLACE TP ORDERS FOR BOTH SIDES
        # TP далеко от рынка чтобы не заполнились сами
        # ------------------------------------------------------------------
        print("\n=== PLACE TP ORDERS ===")

        take_profits = [
            {"tp_percent": 5.0,  "close_percent": 50},
            {"tp_percent": 10.0, "close_percent": 50},
        ]

        t_tp_start = time.time()

        long_placed = service.place_grid_tp_orders(
            symbol=symbol,
            position_side="LONG",
            take_profits=take_profits,
        )

        short_placed = service.place_grid_tp_orders(
            symbol=symbol,
            position_side="SHORT",
            take_profits=take_profits,
        )

        t_tp_placed = time.time()
        print(f"  [TIMING] both TP sets placed in {t_tp_placed - t_tp_start:.2f}s")

        # -- initial snapshots --
        initial = {
            "LONG": {
                "ids":    {tp["order_id"] for tp in long_placed},
                "prices": [tp["price"] for tp in long_placed],
                "qtys":   [tp["qty"]   for tp in long_placed],
            },
            "SHORT": {
                "ids":    {tp["order_id"] for tp in short_placed},
                "prices": [tp["price"] for tp in short_placed],
                "qtys":   [tp["qty"]   for tp in short_placed],
            },
        }

        for side in ("LONG", "SHORT"):
            print(f"\n  {side} initial TP ids:    {initial[side]['ids']}")
            print(f"  {side} initial TP prices: {[f'{p:.8f}' for p in initial[side]['prices']]}")
            print(f"  {side} initial TP qtys:   {initial[side]['qtys']}")

        # ------------------------------------------------------------------
        # START WATCHER FOR BOTH SIDES
        # ------------------------------------------------------------------
        print("\n=== START WATCHER FOR BOTH SIDES ===")
        watcher.start_watching(symbol, "LONG")
        watcher.start_watching(symbol, "SHORT")
        print(f"  watcher watching: {list(watcher._watched.keys())}")

        # ------------------------------------------------------------------
        # MANUAL ACTION INSTRUCTIONS — любой порядок
        # ------------------------------------------------------------------
        print(f"\n=== MANUAL ACTION REQUIRED — любой порядок ===")
        print(f"  LONG  level[1] order_id={long_session.levels[0].order_id}  price={long_session.levels[0].price:.8f}")
        print(f"    -> перетащи ВВЕРХ выше текущей цены для averaging fill")
        print(f"  SHORT level[1] order_id={short_session.levels[0].order_id}  price={short_session.levels[0].price:.8f}")
        print(f"    -> перетащи ВНИЗ ниже текущей цены для averaging fill")
        print(f"  Текущая цена ~{exchange.get_price(symbol):.8f}")
        print(f"  Порядок любой. Ожидание до 60s для обеих сторон.")

        # ------------------------------------------------------------------
        # UNIFIED WAIT LOOP — обе стороны одновременно
        # ------------------------------------------------------------------
        print(f"\n=== WATCHER STARTED ===")
        t_loop_start = time.time()
        deadline     = t_loop_start + 60

        pending_sides = {"LONG", "SHORT"}
        update_order  = []          # порядок в котором пришли updates
        snapshots     = {}          # side -> state at time of its update
        cross_snap    = {}          # side -> other side's state at moment of this side's update
        t_fills       = {}          # side -> time fill first detected (level.status)
        t_updates     = {}          # side -> time TP ids changed

        while time.time() < deadline and pending_sides:
            for side in list(pending_sides):
                other = "SHORT" if side == "LONG" else "LONG"

                current_tp  = service._grid_tp_orders.get((symbol, side), [])
                current_ids = {tp["order_id"] for tp in current_tp}

                # track fill timing via level status
                filled_count = sum(
                    1 for lvl in sessions_map[side].levels if lvl.status == "filled"
                )
                if filled_count > 0 and side not in t_fills:
                    t_fills[side] = time.time()
                    print(f"  [TIMING] {side} fill detected at +{t_fills[side] - t_loop_start:.1f}s")

                # detect averaging fill update (full replacement: same count, new ids)
                # TP fill would reduce count — excluded by len check
                if len(current_ids) == len(initial[side]["ids"]) and current_ids != initial[side]["ids"]:
                    t_updates[side] = time.time()

                    snapshots[side] = {
                        "ids":    current_ids,
                        "prices": [tp["price"] for tp in current_tp],
                        "qtys":   [tp["qty"]   for tp in current_tp],
                        "tp":     current_tp,
                    }

                    other_tp = service._grid_tp_orders.get((symbol, other), [])
                    cross_snap[side] = {
                        "ids":    {tp["order_id"] for tp in other_tp},
                        "prices": [tp["price"] for tp in other_tp],
                        "qtys":   [tp["qty"]   for tp in other_tp],
                    }

                    update_order.append(side)
                    pending_sides.discard(side)
                    seq = "FIRST" if len(update_order) == 1 else "SECOND"
                    print(f"  [{seq}] {side} TP update detected  new_ids={current_ids}")
                    if side in t_fills:
                        print(f"  [TIMING] {side} update lag: {t_updates[side] - t_fills[side]:.2f}s")

            if pending_sides:
                status_parts = []
                for side in ("LONG", "SHORT"):
                    cur     = service._grid_tp_orders.get((symbol, side), [])
                    cur_ids = {tp["order_id"] for tp in cur}
                    filled  = sum(1 for lvl in sessions_map[side].levels if lvl.status == "filled")
                    marker  = "DONE" if side not in pending_sides else "wait"
                    status_parts.append(f"{side}[{marker}] tp_ids={cur_ids} filled={filled}")
                print(f"  {' | '.join(status_parts)}")
                time.sleep(2.0)

        # ------------------------------------------------------------------
        # TIMING SUMMARY
        # ------------------------------------------------------------------
        print(f"\n=== TIMING SUMMARY ===")
        print(f"  positions opened:     +{t_positions_opened - t0:.2f}s from test start")
        print(f"  sessions started:     +{t_sessions_started - t0:.2f}s from test start")
        print(f"  TP placed:            +{t_tp_placed - t0:.2f}s from test start")
        for i, side in enumerate(update_order):
            seq = "1st" if i == 0 else "2nd"
            if side in t_fills:
                print(f"  {seq} fill  ({side}):       +{t_fills[side] - t_loop_start:.1f}s from loop start")
            if side in t_updates:
                print(f"  {seq} update ({side}):      +{t_updates[side] - t_loop_start:.1f}s from loop start")
                if side in t_fills:
                    print(f"  {seq} update lag ({side}): {t_updates[side] - t_fills[side]:.2f}s")

        # ------------------------------------------------------------------
        # CHECKS
        # ------------------------------------------------------------------
        print("\n=== CHECKS ===")
        passed = True

        # [1] обе позиции открыты
        if long_qty > 0:
            print(f"  PASS: LONG position opened  entry={long_entry:.8f}  qty={long_qty}")
        else:
            print("  FAIL: LONG position not opened")
            passed = False

        if short_qty > 0:
            print(f"  PASS: SHORT position opened  entry={short_entry:.8f}  qty={short_qty}")
        else:
            print("  FAIL: SHORT position not opened")
            passed = False

        # [2] обе session созданы
        long_s  = service.get_session(symbol, "LONG")
        short_s = service.get_session(symbol, "SHORT")

        if long_s is not None:
            print(f"  PASS: LONG session alive  session_id={long_s.session_id}")
        else:
            print("  FAIL: LONG session gone")
            passed = False

        if short_s is not None:
            print(f"  PASS: SHORT session alive  session_id={short_s.session_id}")
        else:
            print("  FAIL: SHORT session gone")
            passed = False

        # [3] initial TP placed
        for side in ("LONG", "SHORT"):
            if len(initial[side]["ids"]) == len(take_profits):
                print(f"  PASS: {side} initial TP placed  count={len(initial[side]['ids'])}")
            else:
                print(f"  FAIL: {side} initial TP count={len(initial[side]['ids'])}")
                passed = False

        # [4] both sides updated
        both_updated = len(update_order) == 2
        if both_updated:
            print(f"  PASS: both sides updated  order={update_order}")
        else:
            print(f"  FAIL: not both sides updated  completed={update_order}  pending={pending_sides}")
            passed = False

        if both_updated:
            first_side  = update_order[0]
            second_side = update_order[1]

            # [5] first side: ids changed, qty increased, prices unchanged
            snap_first = snapshots[first_side]
            init_first = initial[first_side]

            if snap_first["ids"] != init_first["ids"]:
                print(f"  PASS: {first_side} (1st) TP order_ids changed")
            else:
                print(f"  FAIL: {first_side} (1st) TP order_ids unchanged")
                passed = False

            sum_first_init    = sum(init_first["qtys"])
            sum_first_updated = sum(snap_first["qtys"])
            if sum_first_updated > sum_first_init:
                print(f"  PASS: {first_side} (1st) TP qty increased  {sum_first_init} -> {sum_first_updated}")
            else:
                print(f"  FAIL: {first_side} (1st) TP qty not increased  {sum_first_init} -> {sum_first_updated}")
                passed = False

            prices_first_ok = (
                len(snap_first["tp"]) == len(init_first["prices"])
                and all(
                    abs(snap_first["tp"][i]["price"] - init_first["prices"][i]) < 1e-9
                    for i in range(len(snap_first["tp"]))
                )
            )
            if prices_first_ok:
                print(f"  PASS: {first_side} (1st) TP prices unchanged (fixed mode)")
            else:
                print(f"  FAIL: {first_side} (1st) TP prices changed unexpectedly")
                passed = False

            # [6] second side untouched at moment of first update
            cross_at_first = cross_snap[first_side]
            init_second    = initial[second_side]

            if cross_at_first["ids"] == init_second["ids"]:
                print(f"  PASS: {second_side} untouched when {first_side} updated  ids unchanged")
            else:
                print(f"  FAIL: {second_side} changed during {first_side} update")
                passed = False

            if cross_at_first["qtys"] == init_second["qtys"]:
                print(f"  PASS: {second_side} TP qty unchanged at moment of {first_side} update")
            else:
                print(f"  FAIL: {second_side} TP qty changed during {first_side} update")
                passed = False

            # [7] second side updated
            snap_second = snapshots[second_side]
            init_second = initial[second_side]

            if snap_second["ids"] != init_second["ids"]:
                print(f"  PASS: {second_side} (2nd) TP order_ids changed")
            else:
                print(f"  FAIL: {second_side} (2nd) TP order_ids unchanged")
                passed = False

            sum_second_init    = sum(init_second["qtys"])
            sum_second_updated = sum(snap_second["qtys"])
            if sum_second_updated > sum_second_init:
                print(f"  PASS: {second_side} (2nd) TP qty increased  {sum_second_init} -> {sum_second_updated}")
            else:
                print(f"  FAIL: {second_side} (2nd) TP qty not increased  {sum_second_init} -> {sum_second_updated}")
                passed = False

            prices_second_ok = (
                len(snap_second["tp"]) == len(init_second["prices"])
                and all(
                    abs(snap_second["tp"][i]["price"] - init_second["prices"][i]) < 1e-9
                    for i in range(len(snap_second["tp"]))
                )
            )
            if prices_second_ok:
                print(f"  PASS: {second_side} (2nd) TP prices unchanged (fixed mode)")
            else:
                print(f"  FAIL: {second_side} (2nd) TP prices changed unexpectedly")
                passed = False

            # [8] first side preserved after second update
            final_first_tp     = service._grid_tp_orders.get((symbol, first_side), [])
            final_first_ids    = {tp["order_id"] for tp in final_first_tp}
            final_first_qtys   = [tp["qty"]      for tp in final_first_tp]
            final_first_prices = [tp["price"]    for tp in final_first_tp]

            if final_first_ids == snap_first["ids"]:
                print(f"  PASS: {first_side} TP order_ids preserved after {second_side} update")
            else:
                print(f"  FAIL: {first_side} TP order_ids changed during {second_side} update")
                passed = False

            if final_first_qtys == snap_first["qtys"]:
                print(f"  PASS: {first_side} TP qty preserved after {second_side} update")
            else:
                print(f"  FAIL: {first_side} TP qty changed during {second_side} update")
                passed = False

            if final_first_prices == snap_first["prices"]:
                print(f"  PASS: {first_side} TP prices preserved after {second_side} update")
            else:
                print(f"  FAIL: {first_side} TP prices changed during {second_side} update")
                passed = False

        # [9] обе session alive
        if long_s is not None and short_s is not None:
            print(f"  PASS: both sessions still alive")
        else:
            print(f"  FAIL: one or both sessions gone")
            passed = False

        # [10] watcher watching both sides
        watches_long  = (symbol, "LONG")  in watcher._watched
        watches_short = (symbol, "SHORT") in watcher._watched
        if watches_long and watches_short:
            print(f"  PASS: watcher still watching both sides")
        else:
            print(f"  FAIL: watcher lost a side  LONG={watches_long}  SHORT={watches_short}")
            passed = False

        if not passed:
            sys.exit(1)

    except Exception as e:
        print(f"\nERROR: {e}")
        raise

    finally:
        # [11] cleanup both sides
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
