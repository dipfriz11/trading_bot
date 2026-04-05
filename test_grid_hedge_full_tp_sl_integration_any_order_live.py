import sys
import time
import copy

from exchange.binance_exchange import BinanceExchange
from trading_core.grid.grid_builder import GridBuilder
from trading_core.grid.grid_runner import GridRunner
from trading_core.grid.grid_registry import GridRegistry
from trading_core.grid.grid_sizer import GridSizer
from trading_core.grid.grid_service import GridService
from trading_core.market_data.market_data_service import MarketDataService
from trading_core.watchers.grid_trailing_watcher import GridTrailingWatcher

SL_PCT  = 5.0
TP1_PCT = 1.0   # partial close 50%
TP2_PCT = 3.0   # remaining close 50%
TAKE_PROFITS = [
    {"tp_percent": TP1_PCT, "close_percent": 50},
    {"tp_percent": TP2_PCT, "close_percent": 50},
]
TIMEOUT = 120

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
        return resp if isinstance(resp, list) else resp.get("openAlgoOrders", [])

    def find_algo(algo_id: int) -> dict | None:
        return next((o for o in get_open_algos(symbol) if o.get("algoId") == algo_id), None)

    def sl_formula(side: str, entry: float) -> float:
        return entry * (1 - SL_PCT / 100) if side == "LONG" else entry * (1 + SL_PCT / 100)

    def tp_formula(side: str, entry: float, tp_pct: float) -> float:
        return entry * (1 + tp_pct / 100) if side == "LONG" else entry * (1 - tp_pct / 100)

    def snap_tp(side: str) -> list:
        return copy.deepcopy(service._grid_tp_orders.get((symbol, side), []))

    def snap_sl(side: str) -> tuple:
        algo_id = service._sl_orders.get((symbol, side))
        if algo_id is None:
            return None, None
        obj = find_algo(algo_id)
        if obj is None:
            time.sleep(1.5)
            obj = find_algo(algo_id)
        trigger = float(obj.get("triggerPrice", 0)) if obj else None
        return algo_id, trigger

    def get_entry(side: str) -> float | None:
        for pos in exchange.get_positions(symbol):
            if pos["positionSide"] == side:
                ep = float(pos["entryPrice"])
                return ep if ep > 0 else None
        return None

    close_map = {"LONG": "sell", "SHORT": "buy"}

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

    for pos in exchange.get_positions(symbol):
        ps  = pos["positionSide"]
        qty = abs(float(pos["positionAmt"]))
        if ps in ("LONG", "SHORT") and qty > 0:
            exchange.close_position(symbol, close_map[ps], qty)
            print(f"  closed leftover {ps} position: qty={qty}")

    time.sleep(1.0)

    try:
        # ------------------------------------------------------------------
        # PHASE 0: SETUP
        # ------------------------------------------------------------------
        print("\n=== PHASE 0: SETUP ===")

        # --- open positions ---
        print("\n--- Open LONG + SHORT ---")
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

        # --- start sessions ---
        print("\n--- Start grid sessions ---")
        t1 = time.time()
        current_price = exchange.get_price(symbol)
        print(f"  current_price={current_price:.8f}")

        long_session = service.start_session(
            symbol=symbol, position_side="LONG",
            total_budget=15.0, levels_count=2, step_percent=1.0,
            orders_count=2,
            first_price=current_price * 0.950, last_price=current_price * 0.920,
            distribution_mode="step", distribution_value=1.0,
        )
        short_session = service.start_session(
            symbol=symbol, position_side="SHORT",
            total_budget=15.0, levels_count=2, step_percent=1.0,
            orders_count=2,
            first_price=current_price * 1.050, last_price=current_price * 1.080,
            distribution_mode="step", distribution_value=1.0,
        )
        print(f"  LONG  session_id={long_session.session_id}")
        for lvl in long_session.levels:
            print(f"    [{lvl.index}] price={lvl.price:.8f}  qty={lvl.qty}")
        print(f"  SHORT session_id={short_session.session_id}")
        for lvl in short_session.levels:
            print(f"    [{lvl.index}] price={lvl.price:.8f}  qty={lvl.qty}")
        print(f"  [TIMING] sessions started in {time.time() - t1:.2f}s")

        # --- place TP orders ---
        print("\n--- Place TP orders (mode=reprice) ---")
        t2 = time.time()
        service.set_tp_update_mode(symbol, "LONG",  "reprice")
        service.set_tp_update_mode(symbol, "SHORT", "reprice")

        long_tp_placed  = service.place_grid_tp_orders(symbol, "LONG",  TAKE_PROFITS)
        short_tp_placed = service.place_grid_tp_orders(symbol, "SHORT", TAKE_PROFITS)

        for side, placed in [("LONG", long_tp_placed), ("SHORT", short_tp_placed)]:
            for tp in placed:
                print(f"  {side} TP{tp['tp_percent']}%: order_id={tp['order_id']}"
                      f"  price={tp['price']:.8f}  qty={tp['qty']}")
        print(f"  [TIMING] TPs placed in {time.time() - t2:.2f}s")

        # --- enable exchange-native SL ---
        print("\n--- Enable exchange-native SL ---")
        t3 = time.time()
        service.enable_tpsl(symbol, "LONG",  sl_percent=SL_PCT, tp_percent=100.0)
        service.enable_tpsl(symbol, "SHORT", sl_percent=SL_PCT, tp_percent=100.0)
        time.sleep(0.3)

        init_sl = {}
        for side in ("LONG", "SHORT"):
            algo_id, trigger = snap_sl(side)
            init_sl[side] = {"algo": algo_id, "trigger": trigger}
            expected = sl_formula(side, entries[side])
            print(f"  {side}: algoId={algo_id}  triggerPrice={trigger}  expected={expected:.8f}")
        print(f"  [TIMING] SLs placed in {time.time() - t3:.2f}s")

        if any(init_sl[s]["algo"] is None for s in ("LONG", "SHORT")):
            print("FAIL: one or both initial SLs not placed")
            sys.exit(1)

        # --- snapshot initial TP state ---
        init_tp = {side: snap_tp(side) for side in ("LONG", "SHORT")}

        # --- start watcher ---
        watcher.start_watching(symbol, "LONG")
        watcher.start_watching(symbol, "SHORT")
        print(f"\n  watcher: {list(watcher._watched.keys())}")

        # ------------------------------------------------------------------
        # PHASE 1: FIRST SIDE AVERAGING (any side)
        # ------------------------------------------------------------------
        print("\n" + "=" * 60)
        print("=== PHASE 1: Drag any LONG or SHORT grid level to market ===")
        print("=" * 60)
        print("  Watcher will: update TP (reprice) + update SL for that side.")
        print(f"  Waiting up to {TIMEOUT}s ...")

        first_side = None
        t_p1 = time.time()
        while time.time() - t_p1 < TIMEOUT:
            for side in ("LONG", "SHORT"):
                if first_side == side:
                    continue
                sess = service.get_session(symbol, side)
                if sess and any(lvl.status == "filled" for lvl in sess.levels):
                    first_side = side
                    print(f"  [P1] averaging detected: {side}  t={time.time() - t_p1:.1f}s")
            if first_side:
                break
            time.sleep(2.0)

        if not first_side:
            print("  TIMEOUT: no averaging in phase 1")

        print("  Sleeping 3s for watcher TP+SL update ...")
        time.sleep(3.0)
        print(f"  [TIMING] phase 1 total: {time.time() - t_p1:.1f}s")

        second_side = "SHORT" if first_side == "LONG" else "LONG"

        # snapshot after phase 1
        p1 = {}
        for side in ("LONG", "SHORT"):
            entry      = get_entry(side)
            tp_snap    = snap_tp(side)
            sl_a, sl_t = snap_sl(side)
            p1[side]   = {"entry": entry, "tp": tp_snap, "sl_algo": sl_a, "sl_trigger": sl_t}

        print(f"\n  first_side={first_side}  second_side={second_side}")
        for side in ("LONG", "SHORT"):
            tps = [(tp["order_id"], f"{tp['tp_percent']}%", f"{tp['price']:.8f}") for tp in p1[side]["tp"]]
            print(f"  {side}: entry={p1[side]['entry']}  sl_algo={p1[side]['sl_algo']}"
                  f"  trigger={p1[side]['sl_trigger']}  tps={tps}")

        # ------------------------------------------------------------------
        # PHASE 2: SECOND SIDE TP1 PARTIAL FILL
        # ------------------------------------------------------------------
        tp1_info = init_tp[second_side][0] if init_tp[second_side] else {}
        print("\n" + "=" * 60)
        print(f"=== PHASE 2: Drag TP1 ({TP1_PCT}%) for {second_side} to market ===")
        print("=" * 60)
        print(f"  TP1 order_id={tp1_info.get('order_id')}  price={tp1_info.get('price', '?')}")
        print(f"  DO NOT drag an averaging level yet — that is PHASE 3.")
        print(f"  Waiting up to {TIMEOUT}s ...")

        tp1_filled_second = False
        t_p2 = time.time()
        while time.time() - t_p2 < TIMEOUT:
            n_tp = len(service._grid_tp_orders.get((symbol, second_side), []))
            if n_tp < 2:
                tp1_filled_second = True
                print(f"  [P2] TP1 fill detected on {second_side}  remaining={n_tp}"
                      f"  t={time.time() - t_p2:.1f}s")
                break
            time.sleep(2.0)

        if not tp1_filled_second:
            print(f"  TIMEOUT: TP1 not filled on {second_side}")

        time.sleep(2.0)
        p2_second_tp = snap_tp(second_side)
        for tp in p2_second_tp:
            print(f"  {second_side} remaining TP: order_id={tp['order_id']}"
                  f"  {tp['tp_percent']}%  price={tp['price']:.8f}  qty={tp['qty']}")
        print(f"  [TIMING] phase 2 total: {time.time() - t_p2:.1f}s")

        # ------------------------------------------------------------------
        # PHASE 3: SECOND SIDE AVERAGING
        # ------------------------------------------------------------------
        print("\n" + "=" * 60)
        print(f"=== PHASE 3: Drag a {second_side} grid level to market ===")
        print("=" * 60)
        print(f"  Watcher will: recalculate remaining TP (qty+reprice) + update SL.")
        print(f"  Waiting up to {TIMEOUT}s ...")

        p3_averaged = False
        t_p3 = time.time()
        while time.time() - t_p3 < TIMEOUT:
            sess = service.get_session(symbol, second_side)
            if sess and any(lvl.status == "filled" for lvl in sess.levels):
                p3_averaged = True
                print(f"  [P3] averaging detected: {second_side}  t={time.time() - t_p3:.1f}s")
                break
            time.sleep(2.0)

        if not p3_averaged:
            print(f"  TIMEOUT: {second_side} averaging not detected")

        print("  Sleeping 3s for watcher TP recalc + SL update ...")
        time.sleep(3.0)
        print(f"  [TIMING] phase 3 total: {time.time() - t_p3:.1f}s")

        # snapshot after phase 3
        p3_second_entry              = get_entry(second_side)
        p3_second_tp                 = snap_tp(second_side)
        p3_second_sl_algo, p3_second_sl_trigger = snap_sl(second_side)
        p3_first_tp                  = snap_tp(first_side)
        p3_first_sl_algo, p3_first_sl_trigger   = snap_sl(first_side)

        print(f"\n  {second_side} after phase 3:")
        print(f"    entry={p3_second_entry}  sl_algo={p3_second_sl_algo}"
              f"  sl_trigger={p3_second_sl_trigger}")
        for tp in p3_second_tp:
            print(f"    TP{tp['tp_percent']}%: order_id={tp['order_id']}"
                  f"  price={tp['price']:.8f}  qty={tp['qty']}")
        print(f"  {first_side} preserved:")
        for tp in p3_first_tp:
            print(f"    TP{tp['tp_percent']}%: order_id={tp['order_id']}"
                  f"  price={tp['price']:.8f}  qty={tp['qty']}")
        print(f"    sl_algo={p3_first_sl_algo}  sl_trigger={p3_first_sl_trigger}")

        # ------------------------------------------------------------------
        # CHECKS
        # ------------------------------------------------------------------
        print("\n=== CHECKS ===")
        passed = True
        tol_pct = 0.001   # 0.1%

        # [1] both positions opened
        if "LONG" in entries and "SHORT" in entries:
            print(f"  PASS [1]: both positions opened"
                  f"  LONG={entries['LONG']:.8f}  SHORT={entries['SHORT']:.8f}")
        else:
            print(f"  FAIL [1]: positions={list(entries.keys())}")
            passed = False

        # [2] both sessions alive
        ls = service.get_session(symbol, "LONG")
        ss = service.get_session(symbol, "SHORT")
        if ls and ss:
            print(f"  PASS [2]: both sessions alive")
        else:
            print(f"  FAIL [2]: LONG={ls is not None}  SHORT={ss is not None}")
            passed = False

        # [3] initial LONG TPs placed
        if len(init_tp["LONG"]) == 2:
            print(f"  PASS [3]: initial LONG TPs placed  ids={[tp['order_id'] for tp in init_tp['LONG']]}")
        else:
            print(f"  FAIL [3]: initial LONG TP count={len(init_tp['LONG'])}")
            passed = False

        # [4] initial SHORT TPs placed
        if len(init_tp["SHORT"]) == 2:
            print(f"  PASS [4]: initial SHORT TPs placed  ids={[tp['order_id'] for tp in init_tp['SHORT']]}")
        else:
            print(f"  FAIL [4]: initial SHORT TP count={len(init_tp['SHORT'])}")
            passed = False

        # [5] initial LONG SL placed
        if init_sl["LONG"]["algo"] and init_sl["LONG"]["trigger"]:
            print(f"  PASS [5]: initial LONG SL  algoId={init_sl['LONG']['algo']}"
                  f"  trigger={init_sl['LONG']['trigger']}")
        else:
            print(f"  FAIL [5]: initial LONG SL not confirmed")
            passed = False

        # [6] initial SHORT SL placed
        if init_sl["SHORT"]["algo"] and init_sl["SHORT"]["trigger"]:
            print(f"  PASS [6]: initial SHORT SL  algoId={init_sl['SHORT']['algo']}"
                  f"  trigger={init_sl['SHORT']['trigger']}")
        else:
            print(f"  FAIL [6]: initial SHORT SL not confirmed")
            passed = False

        # [7] first side averaging detected
        if first_side:
            print(f"  PASS [7]: first averaging detected  side={first_side}")
        else:
            print(f"  FAIL [7]: no first averaging")
            passed = False

        # [8] first side TP repriced (new IDs + formula)
        if first_side:
            init_ids   = {tp["order_id"] for tp in init_tp[first_side]}
            p1_ids     = {tp["order_id"] for tp in p1[first_side]["tp"]}
            ids_changed = init_ids.isdisjoint(p1_ids)
            price_ok    = True
            fe = p1[first_side]["entry"]
            if fe and len(p1[first_side]["tp"]) == 2:
                for tp in p1[first_side]["tp"]:
                    exp = tp_formula(first_side, fe, tp["tp_percent"])
                    if abs(tp["price"] - exp) > fe * tol_pct:
                        price_ok = False
            if ids_changed and price_ok and len(p1[first_side]["tp"]) >= 1:
                prices = [f"{tp['price']:.8f}" for tp in p1[first_side]["tp"]]
                print(f"  PASS [8]: {first_side} TP repriced  new_ids={list(p1_ids)}  prices={prices}")
            else:
                print(f"  FAIL [8]: {first_side} TP reprice  ids_changed={ids_changed}"
                      f"  price_ok={price_ok}  count={len(p1[first_side]['tp'])}")
                passed = False

        # [9] first side SL updated (new algo, formula)
        if first_side:
            old_algo = init_sl[first_side]["algo"]
            new_algo = p1[first_side]["sl_algo"]
            new_trig = p1[first_side]["sl_trigger"]
            fe       = p1[first_side]["entry"]
            algo_ok  = new_algo is not None and new_algo != old_algo
            trig_ok  = (fe and new_trig and
                        abs(new_trig - sl_formula(first_side, fe)) <= fe * tol_pct)
            if algo_ok and trig_ok:
                print(f"  PASS [9]: {first_side} SL updated  algoId={new_algo}"
                      f"  trigger={new_trig:.8f}  expected={sl_formula(first_side, fe):.8f}")
            else:
                print(f"  FAIL [9]: {first_side} SL  algo_ok={algo_ok}  trig_ok={trig_ok}")
                passed = False

        # [10] second side not actively modified by watcher during phase 1
        # Natural TP fills (reducing count) are OK — watcher reprice would introduce new IDs.
        if second_side:
            p1_second_ids   = {tp["order_id"] for tp in p1[second_side]["tp"]}
            init_second_ids = {tp["order_id"] for tp in init_tp[second_side]}
            tp_preserved = p1_second_ids.issubset(init_second_ids)   # no new IDs introduced
            sl_same      = p1[second_side]["sl_algo"] == init_sl[second_side]["algo"]
            if tp_preserved and sl_same:
                print(f"  PASS [10]: {second_side} not repriced by watcher in phase 1"
                      f"  (tp_ids={p1_second_ids} subset-of init={init_second_ids}  sl_same={sl_same})")
            else:
                print(f"  FAIL [10]: {second_side} changed: tp_preserved={tp_preserved}"
                      f"  (ids={p1_second_ids} vs init={init_second_ids})  sl_same={sl_same}")
                passed = False

        # [11] second side TP1 fill detected
        if tp1_filled_second:
            print(f"  PASS [11]: {second_side} TP1 fill detected"
                  f"  remaining={len(p2_second_tp)}")
        else:
            print(f"  FAIL [11]: {second_side} TP1 not filled")
            passed = False

        # [12] second side averaging detected
        if p3_averaged:
            print(f"  PASS [12]: {second_side} averaging detected in phase 3")
        else:
            print(f"  FAIL [12]: {second_side} averaging not detected")
            passed = False

        # [13] second side remaining TP recalculated (new ID, repriced)
        # Compare against original init IDs — averaging may have happened during phase 2
        if second_side:
            old_p2_ids = {tp["order_id"] for tp in init_tp[second_side]}
            p3_ids     = {tp["order_id"] for tp in p3_second_tp}
            ids_new    = old_p2_ids.isdisjoint(p3_ids) and len(p3_second_tp) >= 1
            price_ok   = True
            if p3_second_entry and p3_second_tp:
                for tp in p3_second_tp:
                    exp = tp_formula(second_side, p3_second_entry, tp["tp_percent"])
                    if abs(tp["price"] - exp) > p3_second_entry * tol_pct:
                        price_ok = False
            if ids_new and price_ok:
                info = [(tp["order_id"], f"{tp['tp_percent']}%",
                         f"{tp['price']:.8f}", tp["qty"]) for tp in p3_second_tp]
                print(f"  PASS [13]: {second_side} remaining TP recalculated  {info}")
            else:
                print(f"  FAIL [13]: {second_side} TP  ids_new={ids_new}  price_ok={price_ok}")
                passed = False

        # [14] second side SL updated after phase 3
        # If position fully closed (entry=None), SL auto-cancelled by exchange — algo_ok alone suffices.
        p2_sl_algo = p1[second_side]["sl_algo"]
        algo_ok    = (p3_second_sl_algo is not None and p3_second_sl_algo != p2_sl_algo)
        trig_ok    = False
        pos_closed = p3_second_entry is None
        if p3_second_entry and p3_second_sl_trigger:
            exp = sl_formula(second_side, p3_second_entry)
            trig_ok = abs(p3_second_sl_trigger - exp) <= p3_second_entry * tol_pct
        if algo_ok and (trig_ok or pos_closed):
            detail = (f"trigger={p3_second_sl_trigger:.8f}  expected={sl_formula(second_side, p3_second_entry):.8f}"
                      if not pos_closed else "position closed (TP filled all), SL auto-cancelled")
            print(f"  PASS [14]: {second_side} SL updated  algoId={p3_second_sl_algo}  {detail}")
        else:
            print(f"  FAIL [14]: {second_side} SL  algo_ok={algo_ok}  trig_ok={trig_ok}  pos_closed={pos_closed}")
            passed = False

        # [15] first side preserved after second side lifecycle
        if first_side:
            p1_ids     = {tp["order_id"] for tp in p1[first_side]["tp"]}
            p3_fp_ids  = {tp["order_id"] for tp in p3_first_tp}
            tp_pres    = p1_ids == p3_fp_ids
            sl_pres    = p3_first_sl_algo == p1[first_side]["sl_algo"]
            if tp_pres and sl_pres:
                print(f"  PASS [15]: {first_side} TP+SL preserved after {second_side} lifecycle"
                      f"  sl={p3_first_sl_algo}  trigger={p3_first_sl_trigger}")
            else:
                print(f"  FAIL [15]: {first_side} not preserved  tp_pres={tp_pres}  sl_pres={sl_pres}")
                passed = False

        # [16] both sessions alive at end
        ls2 = service.get_session(symbol, "LONG")
        ss2 = service.get_session(symbol, "SHORT")
        if ls2 and ss2:
            print(f"  PASS [16]: both sessions alive at end")
        else:
            print(f"  FAIL [16]: LONG={ls2 is not None}  SHORT={ss2 is not None}")
            passed = False

        # [17] watcher watching both
        w_l = (symbol, "LONG")  in watcher._watched
        w_s = (symbol, "SHORT") in watcher._watched
        if w_l and w_s:
            print(f"  PASS [17]: watcher watching both sides")
        else:
            print(f"  FAIL [17]: LONG={w_l}  SHORT={w_s}")
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
            tp_list = service._grid_tp_orders.get((symbol, side), [])
            for tp in tp_list:
                try:
                    exchange.cancel_order(symbol, tp["order_id"])
                    print(f"  cancelled {side} TP order_id={tp['order_id']}")
                except Exception:
                    pass
            service._grid_tp_orders.pop((symbol, side), None)
            service._tp_update_mode.pop((symbol, side), None)

            try:
                leftover = service.get_session(symbol, side)
                if leftover is not None:
                    service.stop_session(symbol, side)
                    print(f"  stopped {side} session")
            except Exception as e:
                print(f"  stop_session {side} error (ignored): {e}")

        for pos in exchange.get_positions(symbol):
            ps  = pos["positionSide"]
            qty = abs(float(pos["positionAmt"]))
            if ps in ("LONG", "SHORT") and qty > 0:
                exchange.close_position(symbol, close_map[ps], qty)
                print(f"  closed {ps} position: qty={qty}")

    print("\nTEST DONE")
