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
    # HELPERS
    # ------------------------------------------------------------------
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

    def sl_formula(side: str, entry: float) -> float:
        if side == "LONG":
            return entry * (1 - SL_PCT / 100)
        return entry * (1 + SL_PCT / 100)

    # state per side
    state = {
        "LONG":  {"initial_algo": None, "initial_trigger": None,
                  "new_algo": None,     "new_trigger": None,
                  "new_entry": None,    "averaged": False,
                  "t_fill": None},
        "SHORT": {"initial_algo": None, "initial_trigger": None,
                  "new_algo": None,     "new_trigger": None,
                  "new_entry": None,    "averaged": False,
                  "t_fill": None},
    }

    # ------------------------------------------------------------------
    # PRE-CLEANUP
    # ------------------------------------------------------------------
    print("\n=== PRE-CLEANUP ===")

    for side in ("LONG", "SHORT"):
        leftover = service.get_session(symbol, side)
        if leftover is not None:
            service.stop_session(symbol, side)
            print(f"  stopped leftover {side} session")
        else:
            print(f"  no leftover {side} session")

    try:
        for o in get_open_algos(symbol):
            ps = o.get("positionSide")
            if ps in ("LONG", "SHORT"):
                exchange.cancel_algo_order(o["algoId"])
                print(f"  cancelled leftover {ps} algo algoId={o['algoId']}")
    except Exception as e:
        print(f"  algo cleanup skipped: {e}")

    close_map = {"LONG": "sell", "SHORT": "buy"}
    for pos in exchange.get_positions(symbol):
        ps  = pos["positionSide"]
        qty = abs(float(pos["positionAmt"]))
        if ps in ("LONG", "SHORT") and qty > 0:
            exchange.close_position(symbol, close_map[ps], qty)
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

        entries = {}
        qtys    = {}
        for pos in exchange.get_positions(symbol):
            ps  = pos["positionSide"]
            qty = abs(float(pos["positionAmt"]))
            if ps in ("LONG", "SHORT") and qty > 0:
                entries[ps] = float(pos["entryPrice"])
                qtys[ps]    = qty

        print(f"  LONG:  entry={entries.get('LONG')}  qty={qtys.get('LONG')}")
        print(f"  SHORT: entry={entries.get('SHORT')}  qty={qtys.get('SHORT')}")
        print(f"  [TIMING] positions opened in {time.time() - t0:.2f}s")

        if "LONG" not in entries or "SHORT" not in entries:
            print("FAIL: one or both positions not opened")
            sys.exit(1)

        # ------------------------------------------------------------------
        # START GRID SESSIONS
        # ------------------------------------------------------------------
        print("\n=== START GRID SESSIONS ===")
        t1 = time.time()
        current_price = exchange.get_price(symbol)
        print(f"  current_price={current_price:.8f}")

        long_session = service.start_session(
            symbol=symbol,
            position_side="LONG",
            total_budget=15.0,
            levels_count=2,
            step_percent=1.0,
            orders_count=2,
            first_price=current_price * 0.950,
            last_price=current_price * 0.920,
            distribution_mode="step",
            distribution_value=1.0,
        )
        short_session = service.start_session(
            symbol=symbol,
            position_side="SHORT",
            total_budget=15.0,
            levels_count=2,
            step_percent=1.0,
            orders_count=2,
            first_price=current_price * 1.050,
            last_price=current_price * 1.080,
            distribution_mode="step",
            distribution_value=1.0,
        )
        print(f"  LONG  session_id={long_session.session_id}")
        for lvl in long_session.levels:
            print(f"    [{lvl.index}] price={lvl.price:.8f}  qty={lvl.qty}")
        print(f"  SHORT session_id={short_session.session_id}")
        for lvl in short_session.levels:
            print(f"    [{lvl.index}] price={lvl.price:.8f}  qty={lvl.qty}")
        print(f"  [TIMING] sessions started in {time.time() - t1:.2f}s")

        # ------------------------------------------------------------------
        # ENABLE TPSL FOR BOTH SIDES
        # ------------------------------------------------------------------
        print("\n=== ENABLE TPSL (both sides) ===")
        t2 = time.time()

        for side in ("LONG", "SHORT"):
            service._base_position_qty[(symbol, side)] = qtys[side]
            service.enable_tpsl(symbol, side, sl_percent=SL_PCT, tp_percent=TP_PCT)

        time.sleep(0.3)

        for side in ("LONG", "SHORT"):
            algo_id = service._sl_orders.get((symbol, side))
            sl_obj  = find_algo(algo_id)
            trigger = float(sl_obj.get("triggerPrice", 0)) if sl_obj else None
            state[side]["initial_algo"]    = algo_id
            state[side]["initial_trigger"] = trigger
            expected = sl_formula(side, entries[side])
            print(
                f"  {side}: algoId={algo_id}  triggerPrice={trigger}"
                f"  expected={expected:.8f}"
            )

        print(f"  [TIMING] both SLs placed in {time.time() - t2:.2f}s")

        if any(state[s]["initial_algo"] is None for s in ("LONG", "SHORT")):
            print("FAIL: one or both initial SLs not placed")
            sys.exit(1)

        # ------------------------------------------------------------------
        # START WATCHER FOR BOTH SIDES
        # ------------------------------------------------------------------
        print("\n=== START WATCHER ===")
        watcher.start_watching(symbol, "LONG")
        watcher.start_watching(symbol, "SHORT")
        print(f"  watching: {list(watcher._watched.keys())}")

        # ------------------------------------------------------------------
        # PHASE 1: WAIT FOR FIRST AVERAGING (either side)
        # ------------------------------------------------------------------
        print("\n=== PHASE 1: WAIT FOR FIRST AVERAGING (any side) ===")
        print("  Drag any grid level to market to trigger averaging.")
        print("  Waiting up to 120s ...")

        TIMEOUT    = 120
        t_phase1   = time.time()
        first_side = None

        while time.time() - t_phase1 < TIMEOUT:
            for side in ("LONG", "SHORT"):
                if state[side]["averaged"]:
                    continue
                sess = service.get_session(symbol, side)
                if sess is not None and any(lvl.status == "filled" for lvl in sess.levels):
                    state[side]["averaged"] = True
                    state[side]["t_fill"]   = time.time()
                    if first_side is None:
                        first_side = side
                    print(f"  averaging detected: {side}  after {state[side]['t_fill'] - t_phase1:.1f}s")
            if first_side is not None:
                break
            time.sleep(2.0)

        if first_side is None:
            print("  TIMEOUT: no averaging fill detected (phase 1)")

        time.sleep(2.0)  # propagate

        # snapshot state after phase 1
        second_side = "SHORT" if first_side == "LONG" else "LONG"

        for side in ("LONG", "SHORT"):
            new_algo = service._sl_orders.get((symbol, side))
            sl_obj   = find_algo(new_algo) if new_algo else None
            if sl_obj is None and new_algo is not None:
                time.sleep(1.5)
                sl_obj = find_algo(new_algo)
            trigger   = float(sl_obj.get("triggerPrice", 0)) if sl_obj else None
            new_entry = None
            for pos in exchange.get_positions(symbol):
                if pos["positionSide"] == side:
                    ep = float(pos["entryPrice"])
                    if ep > 0:
                        new_entry = ep
                    break
            state[side]["new_algo"]    = new_algo
            state[side]["new_trigger"] = trigger
            state[side]["new_entry"]   = new_entry

        print(f"\n  first_side={first_side}  second_side={second_side}")
        for side in ("LONG", "SHORT"):
            print(
                f"  {side}: algo={state[side]['new_algo']}"
                f"  trigger={state[side]['new_trigger']}"
                f"  entry={state[side]['new_entry']}"
            )

        # ------------------------------------------------------------------
        # PHASE 2: WAIT FOR SECOND AVERAGING (other side)
        # ------------------------------------------------------------------
        print(f"\n=== PHASE 2: WAIT FOR {second_side} AVERAGING ===")
        print(f"  Now drag a {second_side} grid level to market.")
        print("  Waiting up to 120s ...")

        t_phase2 = time.time()
        while time.time() - t_phase2 < TIMEOUT:
            if state[second_side]["averaged"]:
                break
            sess = service.get_session(symbol, second_side)
            if sess is not None and any(lvl.status == "filled" for lvl in sess.levels):
                state[second_side]["averaged"] = True
                state[second_side]["t_fill"]   = time.time()
                print(f"  averaging detected: {second_side}  after {state[second_side]['t_fill'] - t_phase2:.1f}s")
                break
            time.sleep(2.0)

        if not state[second_side]["averaged"]:
            print(f"  TIMEOUT: {second_side} averaging not detected (phase 2)")

        time.sleep(2.0)  # propagate

        # snapshot second side after phase 2
        p2_algo  = service._sl_orders.get((symbol, second_side))
        p2_obj   = find_algo(p2_algo) if p2_algo else None
        if p2_obj is None and p2_algo is not None:
            time.sleep(1.5)
            p2_obj = find_algo(p2_algo)
        p2_trigger = float(p2_obj.get("triggerPrice", 0)) if p2_obj else None
        p2_entry   = None
        for pos in exchange.get_positions(symbol):
            if pos["positionSide"] == second_side:
                ep = float(pos["entryPrice"])
                if ep > 0:
                    p2_entry = ep
                break

        # snapshot first side — must be preserved
        p2_first_algo    = service._sl_orders.get((symbol, first_side))
        p2_first_sl_obj  = find_algo(p2_first_algo) if p2_first_algo else None
        p2_first_trigger = float(p2_first_sl_obj.get("triggerPrice", 0)) if p2_first_sl_obj else None

        print(f"\n  {second_side} after phase 2:")
        print(f"    new_algo={p2_algo}  trigger={p2_trigger}  entry={p2_entry}")
        print(f"  {first_side} preserved:")
        print(f"    algo={p2_first_algo}  trigger={p2_first_trigger}")

        # ------------------------------------------------------------------
        # CHECKS
        # ------------------------------------------------------------------
        print("\n=== CHECKS ===")
        passed = True

        # [1] both positions opened
        if "LONG" in entries and "SHORT" in entries:
            print(f"  PASS [1]: both positions opened"
                  f"  LONG={entries['LONG']:.8f}  SHORT={entries['SHORT']:.8f}")
        else:
            print(f"  FAIL [1]: missing positions  {list(entries.keys())}")
            passed = False

        # [2] both sessions alive
        ls = service.get_session(symbol, "LONG")
        ss = service.get_session(symbol, "SHORT")
        if ls is not None and ss is not None:
            print(f"  PASS [2]: both sessions alive")
        else:
            print(f"  FAIL [2]: sessions  LONG={ls is not None}  SHORT={ss is not None}")
            passed = False

        # [3] initial LONG SL was placed
        if state["LONG"]["initial_algo"] is not None and state["LONG"]["initial_trigger"] is not None:
            print(f"  PASS [3]: initial LONG SL placed  algoId={state['LONG']['initial_algo']}"
                  f"  trigger={state['LONG']['initial_trigger']}")
        else:
            print(f"  FAIL [3]: initial LONG SL not confirmed")
            passed = False

        # [4] initial SHORT SL was placed
        if state["SHORT"]["initial_algo"] is not None and state["SHORT"]["initial_trigger"] is not None:
            print(f"  PASS [4]: initial SHORT SL placed  algoId={state['SHORT']['initial_algo']}"
                  f"  trigger={state['SHORT']['initial_trigger']}")
        else:
            print(f"  FAIL [4]: initial SHORT SL not confirmed")
            passed = False

        # [5] first side averaged
        if first_side is not None and state[first_side]["averaged"]:
            print(f"  PASS [5]: first averaging detected  side={first_side}")
        else:
            print(f"  FAIL [5]: no first averaging detected")
            passed = False

        # [6a] first side: old SL removed
        if first_side is not None:
            old_id   = state[first_side]["initial_algo"]
            new_id   = state[first_side]["new_algo"]
            old_gone = find_algo(old_id) is None
            if old_gone:
                print(f"  PASS [6a]: {first_side} old SL removed  algoId={old_id}")
            else:
                print(f"  FAIL [6a]: {first_side} old SL still on exchange  algoId={old_id}")
                passed = False

            # [6b] first side: new SL placed with different algoId
            if new_id is not None and new_id != old_id:
                print(f"  PASS [6b]: {first_side} new SL placed  algoId={new_id}")
            else:
                print(f"  FAIL [6b]: {first_side} new SL not placed  new={new_id}  old={old_id}")
                passed = False

            # [6c] first side: triggerPrice matches formula
            fe = state[first_side]["new_entry"]
            ft = state[first_side]["new_trigger"]
            if fe is not None and ft is not None:
                expected  = sl_formula(first_side, fe)
                tolerance = fe * 0.0005
                if abs(ft - expected) <= tolerance:
                    print(f"  PASS [6c]: {first_side} triggerPrice={ft:.8f}"
                          f"  expected={expected:.8f}  diff={abs(ft-expected):.8f}")
                else:
                    print(f"  FAIL [6c]: {first_side} triggerPrice={ft:.8f}"
                          f"  expected={expected:.8f}  diff={abs(ft-expected):.8f}")
                    passed = False
            else:
                print(f"  FAIL [6c]: {first_side} cannot check formula  entry={fe}  trigger={ft}")
                passed = False

        # [7] second side unchanged during phase 1
        if second_side is not None:
            s2_algo_phase1 = state[second_side]["new_algo"]
            s2_init_algo   = state[second_side]["initial_algo"]
            if s2_algo_phase1 == s2_init_algo:
                print(f"  PASS [7]: {second_side} SL unchanged during phase 1"
                      f"  algoId={s2_algo_phase1}")
            else:
                print(f"  FAIL [7]: {second_side} SL changed unexpectedly"
                      f"  initial={s2_init_algo}  after_phase1={s2_algo_phase1}")
                passed = False

        # [8] second side averaged
        if state[second_side]["averaged"]:
            print(f"  PASS [8]: second averaging detected  side={second_side}")
        else:
            print(f"  FAIL [8]: {second_side} averaging not detected")
            passed = False

        # [9a] second side: old SL removed
        s2_old_id   = state[second_side]["initial_algo"]
        s2_old_gone = find_algo(s2_old_id) is None
        if s2_old_gone:
            print(f"  PASS [9a]: {second_side} old SL removed  algoId={s2_old_id}")
        else:
            print(f"  FAIL [9a]: {second_side} old SL still on exchange  algoId={s2_old_id}")
            passed = False

        # [9b] second side: new SL placed
        if p2_algo is not None and p2_algo != s2_old_id:
            print(f"  PASS [9b]: {second_side} new SL placed  algoId={p2_algo}")
        else:
            print(f"  FAIL [9b]: {second_side} new SL not placed  p2_algo={p2_algo}")
            passed = False

        # [9c] second side: triggerPrice matches formula
        if p2_entry is not None and p2_trigger is not None:
            expected  = sl_formula(second_side, p2_entry)
            tolerance = p2_entry * 0.0005
            if abs(p2_trigger - expected) <= tolerance:
                print(f"  PASS [9c]: {second_side} triggerPrice={p2_trigger:.8f}"
                      f"  expected={expected:.8f}  diff={abs(p2_trigger-expected):.8f}")
            else:
                print(f"  FAIL [9c]: {second_side} triggerPrice={p2_trigger:.8f}"
                      f"  expected={expected:.8f}  diff={abs(p2_trigger-expected):.8f}")
                passed = False
        else:
            print(f"  FAIL [9c]: {second_side} cannot check formula  entry={p2_entry}  trigger={p2_trigger}")
            passed = False

        # [10] first side SL preserved after second update
        fs_preserved = (p2_first_algo == state[first_side]["new_algo"] and p2_first_algo is not None)
        if fs_preserved:
            print(f"  PASS [10]: {first_side} SL preserved after {second_side} update"
                  f"  algoId={p2_first_algo}  trigger={p2_first_trigger}")
        else:
            print(f"  FAIL [10]: {first_side} SL changed after {second_side} update"
                  f"  expected={state[first_side]['new_algo']}  got={p2_first_algo}")
            passed = False

        # [11] both sessions alive at end
        ls2 = service.get_session(symbol, "LONG")
        ss2 = service.get_session(symbol, "SHORT")
        if ls2 is not None and ss2 is not None:
            print(f"  PASS [11]: both sessions alive at end")
        else:
            print(f"  FAIL [11]: LONG={ls2 is not None}  SHORT={ss2 is not None}")
            passed = False

        # [12] watcher still watching both
        w_long  = (symbol, "LONG")  in watcher._watched
        w_short = (symbol, "SHORT") in watcher._watched
        if w_long and w_short:
            print(f"  PASS [12]: watcher watching both sides")
        else:
            print(f"  FAIL [12]: LONG={w_long}  SHORT={w_short}")
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
                ps = o.get("positionSide")
                if ps in ("LONG", "SHORT"):
                    try:
                        exchange.cancel_algo_order(o["algoId"])
                        print(f"  cancelled {ps} algo algoId={o['algoId']}")
                    except Exception as e:
                        print(f"  cancel algo error: {e}")
        except Exception as e:
            print(f"  algo cleanup error: {e}")

        for side in ("LONG", "SHORT"):
            try:
                leftover = service.get_session(symbol, side)
                if leftover is not None:
                    service.stop_session(symbol, side)
                    print(f"  stopped {side} session")
            except Exception as e:
                print(f"  stop_session {side} error (ignored): {e}")

        close_map = {"LONG": "sell", "SHORT": "buy"}
        for pos in exchange.get_positions(symbol):
            ps  = pos["positionSide"]
            qty = abs(float(pos["positionAmt"]))
            if ps in ("LONG", "SHORT") and qty > 0:
                exchange.close_position(symbol, close_map[ps], qty)
                print(f"  closed {ps} position: qty={qty}")

    print("\nTEST DONE")
