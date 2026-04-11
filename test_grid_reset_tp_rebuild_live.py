"""
test_grid_reset_tp_rebuild_live.py

Live test: Reset TP → rebuild_pending_tail flow.
Pair: SIRENUSDT / LONG

Step-based grid: FIRST_OFFSET=1%, STEP=1%, GRID_ORDERS=5 → levels at 1%,2%,3%,4%,5%
Reset TP triggered by levels [3], [4], [5] (use_reset_tp=True).

Scenario (all fills are manual — drag orders on Binance UI):
  MA1: fill level[1]  — no Reset TP
  MA2: fill level[2]  — no Reset TP
  MA3: fill level[3]  — Reset TP placed at entry × (1 + RESET_TP_PCT%)
  MA4: drag Reset TP DOWN to market
       watcher: check_reset_tp_fill → rebuild_pending_tail
       → levels [4]+[5] cancelled, 2 new tail orders placed

Debug output:
  [DEBUG-A] grid config + original offsets + steps (before any fills)
  [DEBUG-B] rebuild detail + new level offsets (after MA4)
  [DEBUG-C] step consistency PASS/FAIL summary
"""
import sys
import io
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from exchange.binance_exchange import BinanceExchange
from trading_core.grid.grid_builder import GridBuilder
from trading_core.grid.grid_runner import GridRunner
from trading_core.grid.grid_registry import GridRegistry
from trading_core.grid.grid_sizer import GridSizer
from trading_core.grid.grid_service import GridService
from trading_core.market_data.market_data_service import MarketDataService
from trading_core.watchers.grid_trailing_watcher import GridTrailingWatcher

GRID_ORDERS      = 5
STEP_PCT         = 1.0    # step between grid levels
FIRST_OFFSET_PCT = 1.0    # level[1] at -1% from market
LAST_OFFSET_PCT  = FIRST_OFFSET_PCT + (GRID_ORDERS - 1) * STEP_PCT  # = 5.0
TP_PCT           = 3.0    # main TP: +3% above entry
RESET_TP_PCT     = 1.0    # Reset TP: +1% above entry
RESET_CLOSE_PCT  = 25     # ~1 level qty (triggered after 3rd fill: 1 level / 4 = 25%)
TIMEOUT          = 120    # seconds to wait per phase

# index 0 → level[1], ..., index 4 → level[5]
# Reset TP triggered by levels [3], [4], [5]
LEVEL_RESET_CONFIGS = [
    {"use_reset_tp": False},
    {"use_reset_tp": False},
    {"use_reset_tp": True, "reset_tp_percent": RESET_TP_PCT, "reset_tp_close_percent": RESET_CLOSE_PCT},
    {"use_reset_tp": True, "reset_tp_percent": RESET_TP_PCT, "reset_tp_close_percent": RESET_CLOSE_PCT},
    {"use_reset_tp": True, "reset_tp_percent": RESET_TP_PCT, "reset_tp_close_percent": RESET_CLOSE_PCT},
]

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
        print("  stopped leftover LONG session")
    else:
        print("  no leftover LONG session")

    for pos in exchange.get_positions(symbol):
        if pos["positionSide"] == "LONG":
            qty = abs(float(pos["positionAmt"]))
            if qty > 0:
                exchange.close_position(symbol, "sell", qty)
                print(f"  closed leftover LONG position  qty={qty}")

    time.sleep(1.0)

    try:
        # ------------------------------------------------------------------
        # START GRID SESSION
        # ------------------------------------------------------------------
        base_price = exchange.get_price(symbol)
        print(f"\n  base_price={base_price:.8f}  (grid levels computed from this)")
        print("\n=== START GRID SESSION ===")
        current_price = exchange.get_price(symbol)
        print(f"  current_price={current_price:.8f}")

        t_sess = time.time()
        session = service.start_session(
            symbol=symbol,
            position_side="LONG",
            total_budget=45.0,
            levels_count=GRID_ORDERS,
            step_percent=1.0,
            orders_count=GRID_ORDERS,
            first_offset_percent=FIRST_OFFSET_PCT,
            last_offset_percent=LAST_OFFSET_PCT,
            distribution_mode="step",
            distribution_value=1.0,
            level_reset_configs=LEVEL_RESET_CONFIGS,
        )
        print(f"  session_id={session.session_id}  [TIMING] {time.time() - t_sess:.2f}s")
        print(f"  Grid levels:")
        for lvl in session.levels:
            if lvl.index == 1:
                action = "<-- MA1"
            elif lvl.index == 2:
                action = "<-- MA2"
            elif lvl.index == 3:
                action = "<-- MA3 (triggers Reset TP)"
            else:
                action = "    (tail -- will be rebuilt)"
            print(f"    [{lvl.index}] order_id={lvl.order_id}  price={lvl.price:.8f}"
                  f"  qty={lvl.qty}  use_reset_tp={lvl.use_reset_tp}  {action}")

        # ── Debug Block A ──────────────────────────────────────────────────
        print("\n=== [DEBUG-A] GRID CONFIG ===")
        print(f"  total_budget=45.0 USDT  leverage=5x  GRID_ORDERS={GRID_ORDERS}")
        print(f"  STEP_PCT={STEP_PCT}%  FIRST_OFFSET={FIRST_OFFSET_PCT}%"
              f"  LAST_OFFSET={LAST_OFFSET_PCT}%")
        print(f"  TP_PCT={TP_PCT}%  RESET_TP_PCT={RESET_TP_PCT}%"
              f"  RESET_CLOSE_PCT={RESET_CLOSE_PCT}%")
        print(f"  Reset TP rule: triggered by levels [3, 4, 5]")
        if session.levels:
            lq = session.levels[0].qty
            print(f"  level_qty ~{lq:.2f} coins  ~{lq * base_price:.2f} USDT each")
        print(f"\n  Levels (offsets from base_price={base_price:.5f}):")
        for lvl in session.levels:
            off = (lvl.price - base_price) / base_price * 100
            tag = "  <- Reset TP trigger" if lvl.use_reset_tp else ""
            print(f"    [{lvl.index}]  price={lvl.price:.5f}  offset={off:+.2f}%{tag}")
        if len(session.levels) >= 2:
            print(f"  Steps:")
            for i in range(1, len(session.levels)):
                s = abs(session.levels[i].price - session.levels[i-1].price) / base_price * 100
                print(f"    [{i}->{i+1}] {s:.2f}%")
        # ── End Debug Block A ──────────────────────────────────────────────

        # ------------------------------------------------------------------
        # START WATCHER
        # Register TP config before position exists — watcher will auto-place
        # TP on first fill via update_grid_tp_orders_reprice (uses _grid_tp_config).
        # ------------------------------------------------------------------
        service.set_tp_update_mode(symbol, "LONG", "reprice")
        service._grid_tp_config[(symbol, "LONG")] = [
            {"tp_percent": TP_PCT, "close_percent": 100}
        ]
        initial_tp_id = None
        print("\n=== START WATCHER ===")
        watcher.start_watching(symbol, "LONG")
        print(f"  watching: {list(watcher._watched.keys())}")

        # ------------------------------------------------------------------
        # MANUAL ACTION 1: fill level[1]  — no Reset TP
        # ------------------------------------------------------------------
        print("\n" + "=" * 60)
        print("=== MANUAL ACTION 1: drag level[1] UP to market ===")
        print("=" * 60)
        lvl1 = session.levels[0]
        print(f"  Order:  order_id={lvl1.order_id}  price={lvl1.price:.8f}")
        print(f"  level[1].use_reset_tp={lvl1.use_reset_tp}  → no Reset TP will appear")
        print(f"  Expected: main TP repriced to new entry x {1 + TP_PCT / 100:.4f}")
        print(f"  Waiting up to {TIMEOUT}s ...")

        p1_fill_detected = False
        for _ in range(TIMEOUT):
            if session.levels[0].status == "filled":
                p1_fill_detected = True
                break
            time.sleep(1.0)

        if not p1_fill_detected:
            print(f"  TIMEOUT: level[1] fill not detected after {TIMEOUT}s")
        else:
            print(f"  level[1] fill detected")

        # Poll for TP to appear (watcher places TP after check_grid_fills API call)
        tp_after_p1 = []
        for _ in range(20):
            tp_after_p1 = list(service._grid_tp_orders.get((symbol, "LONG"), []))
            if tp_after_p1:
                break
            time.sleep(1.0)

        reset_after_p1 = service._reset_tp_order.get((symbol, "LONG"))
        tp_after_p1_id = tp_after_p1[0]["order_id"] if tp_after_p1 else None
        initial_tp_id  = tp_after_p1_id  # set from watcher-placed TP

        print(f"\n  --- State after MANUAL ACTION 1 ---")
        print(f"  level[1].status     = {session.levels[0].status}")
        print(f"  _reset_tp_order     = {reset_after_p1}  (expected None)")
        if tp_after_p1:
            tp0      = tp_after_p1[0]
            repriced = (tp0["order_id"] != initial_tp_id)
            print(f"  main TP order_id    = {tp0['order_id']}"
                  f"  price={tp0['price']:.8f}  qty={tp0['qty']}"
                  f"  {'(repriced)' if repriced else '(same id -- reprice pending)'}")
        else:
            print(f"  main TP             = None  (unexpected)")
        print(f"  _sl_orders          = {service._sl_orders.get((symbol, 'LONG'))}"
              f"  (no SL configured → None expected)")

        print("\n=== CHECKS PHASE 1 ===")
        p1_passed = True

        if p1_fill_detected:
            print("  PASS [P1-1]: level[1] fill detected")
        else:
            print("  FAIL [P1-1]: level[1] fill not detected")
            p1_passed = False

        if session.levels[0].status == "filled":
            print("  PASS [P1-2]: level[1].status == 'filled'")
        else:
            print(f"  FAIL [P1-2]: level[1].status = '{session.levels[0].status}'")
            p1_passed = False

        if reset_after_p1 is None:
            print("  PASS [P1-3]: _reset_tp_order is None  (use_reset_tp=False)")
        else:
            print(f"  FAIL [P1-3]: unexpected Reset TP after level[1]: {reset_after_p1}")
            p1_passed = False

        if tp_after_p1:
            print(f"  PASS [P1-4]: main TP active  order_id={tp_after_p1_id}"
                  f"  price={tp_after_p1[0]['price']:.8f}")
        else:
            print("  FAIL [P1-4]: main TP missing after level[1] fill")
            p1_passed = False

        if not p1_passed:
            print("  Phase 1 checks failed — aborting")
            sys.exit(1)

        # ------------------------------------------------------------------
        # MANUAL ACTION 2: fill level[2]  — no Reset TP (use_reset_tp=False)
        # ------------------------------------------------------------------
        print("\n" + "=" * 60)
        print("=== MANUAL ACTION 2: drag level[2] UP to market ===")
        print("=" * 60)
        lvl2 = session.levels[1]
        print(f"  Order:  order_id={lvl2.order_id}  price={lvl2.price:.8f}")
        print(f"  level[2].use_reset_tp={lvl2.use_reset_tp}  → no Reset TP expected")
        print(f"  Expected: main TP repriced to new entry x {1 + TP_PCT / 100:.4f}")
        print(f"  Waiting up to {TIMEOUT}s ...")

        p2_fill_detected = False
        for _ in range(TIMEOUT):
            if session.levels[1].status == "filled":
                p2_fill_detected = True
                break
            time.sleep(1.0)

        # Poll for TP reprice to complete
        tp_after_p2 = []
        for _ in range(20):
            tp_after_p2 = list(service._grid_tp_orders.get((symbol, "LONG"), []))
            if tp_after_p2:
                break
            time.sleep(1.0)
        reset_after_p2 = service._reset_tp_order.get((symbol, "LONG"))

        print(f"\n  --- State after MANUAL ACTION 2 ---")
        print(f"  level[2].status  = {session.levels[1].status}")
        print(f"  _reset_tp_order  = {reset_after_p2}  (expected None)")
        if tp_after_p2:
            tp0 = tp_after_p2[0]
            print(f"  main TP  order_id={tp0['order_id']}  price={tp0['price']:.8f}  qty={tp0['qty']}")

        print("\n=== CHECKS PHASE 2 ===")
        p2_passed = True

        if p2_fill_detected:
            print("  PASS [P2-1]: level[2] fill detected")
        else:
            print(f"  FAIL [P2-1]: level[2] fill not detected after {TIMEOUT}s")
            p2_passed = False

        if session.levels[1].status == "filled":
            print("  PASS [P2-2]: level[2].status == 'filled'")
        else:
            print(f"  FAIL [P2-2]: level[2].status = '{session.levels[1].status}'")
            p2_passed = False

        if reset_after_p2 is None:
            print("  PASS [P2-3]: no Reset TP after level[2]  (use_reset_tp=False)")
        else:
            print(f"  FAIL [P2-3]: unexpected Reset TP: {reset_after_p2}")
            p2_passed = False

        if not p2_passed:
            print("  Phase 2 checks failed — aborting")
            sys.exit(1)

        # ------------------------------------------------------------------
        # MANUAL ACTION 3: fill level[3]  → Reset TP appears (use_reset_tp=True)
        # ------------------------------------------------------------------
        print("\n" + "=" * 60)
        print("=== MANUAL ACTION 3: drag level[3] UP to market ===")
        print("=" * 60)
        lvl3 = session.levels[2]
        print(f"  Order:  order_id={lvl3.order_id}  price={lvl3.price:.8f}")
        print(f"  level[3].use_reset_tp={lvl3.use_reset_tp}  → Reset TP will appear")
        print(f"  Expected after fill:")
        print(f"    Reset TP  at new_entry x {1 + RESET_TP_PCT / 100:.4f}"
              f"  qty = {RESET_CLOSE_PCT}% of position")
        print(f"    Main  TP  at new_entry x {1 + TP_PCT / 100:.4f}"
              f"  qty = {100 - RESET_CLOSE_PCT}% of position")
        print(f"  Waiting up to {TIMEOUT}s for watcher to call place_reset_tp_complex ...")

        p3_fill_detected = False
        reset_entry_p3   = None
        new_main_tp_p3   = None
        for _ in range(TIMEOUT):
            reset_now = service._reset_tp_order.get((symbol, "LONG"))
            main_now  = service._grid_tp_orders.get((symbol, "LONG"), [])
            if reset_now and main_now:
                p3_fill_detected = True
                reset_entry_p3   = dict(reset_now)
                new_main_tp_p3   = dict(main_now[0])
                break
            time.sleep(1.0)

        if not p3_fill_detected:
            print(f"  TIMEOUT: Reset TP not placed after {TIMEOUT}s")
        else:
            print(f"  Reset TP placed!")

        entry_after_p3 = None
        for pos in exchange.get_positions(symbol):
            if pos["positionSide"] == "LONG":
                ep = float(pos["entryPrice"])
                if ep > 0:
                    entry_after_p3 = ep
                break

        exp_reset_price = entry_after_p3 * (1 + RESET_TP_PCT / 100) if entry_after_p3 else None
        exp_main_price  = entry_after_p3 * (1 + TP_PCT / 100)       if entry_after_p3 else None

        print(f"\n  --- State after MANUAL ACTION 3 ---")
        print(f"  level[3].status    = {session.levels[2].status}")
        print(f"  entry (exchange)   = {entry_after_p3}")
        if reset_entry_p3:
            print(f"  Reset TP order_id  = {reset_entry_p3['order_id']}")
            print(f"  Reset TP price     = {reset_entry_p3['price']:.8f}"
                  + (f"  (expected {exp_reset_price:.8f})" if exp_reset_price else ""))
            print(f"  Reset TP qty       = {reset_entry_p3['qty']}")
            print(f"  *** MA4: drag order_id={reset_entry_p3['order_id']}  DOWN to market ***")
        else:
            print(f"  Reset TP           = not placed")
        if new_main_tp_p3:
            print(f"  Main TP order_id   = {new_main_tp_p3['order_id']}  (was {initial_tp_id})")
            print(f"  Main TP price      = {new_main_tp_p3['price']:.8f}"
                  + (f"  (expected {exp_main_price:.8f})" if exp_main_price else ""))
            print(f"  Main TP qty        = {new_main_tp_p3['qty']}")
        print(f"  _sl_orders         = {service._sl_orders.get((symbol, 'LONG'))}"
              f"  (no SL configured)")

        placed_before      = [l for l in session.levels if l.status == "placed"]
        old_placed_indices = {l.index for l in placed_before}
        print(f"\n  Pending tail (will be cancelled by rebuild):")
        for l in placed_before:
            print(f"    [{l.index}] order_id={l.order_id}  price={l.price:.8f}  qty={l.qty}")

        print("\n=== CHECKS PHASE 3 ===")
        p3_passed = True

        if p3_fill_detected:
            print("  PASS [P3-1]: Reset TP placed (level[3] fill confirmed via watcher)")
        else:
            print("  FAIL [P3-1]: Reset TP not placed after level[3] fill")
            p3_passed = False

        if session.levels[2].status == "filled":
            print("  PASS [P3-2]: level[3].status == 'filled'")
        else:
            print(f"  FAIL [P3-2]: level[3].status = '{session.levels[2].status}'")
            p3_passed = False

        if reset_entry_p3 and reset_entry_p3["order_id"] != initial_tp_id:
            print(f"  PASS [P3-3]: old main TP (id={initial_tp_id}) cancelled,"
                  f" Reset TP = id={reset_entry_p3['order_id']}")
        else:
            print("  FAIL [P3-3]: Reset TP not placed or same id as initial TP")
            p3_passed = False

        if reset_entry_p3 and exp_reset_price is not None:
            tol = exp_reset_price * 0.001
            ok  = abs(reset_entry_p3["price"] - exp_reset_price) <= tol
            print(f"  {'PASS' if ok else 'FAIL'} [P3-4]: Reset TP price"
                  f"  actual={reset_entry_p3['price']:.8f}"
                  f"  expected={exp_reset_price:.8f}")
            if not ok:
                p3_passed = False

        if new_main_tp_p3 and exp_main_price is not None:
            tol = exp_main_price * 0.001
            ok  = abs(new_main_tp_p3["price"] - exp_main_price) <= tol
            print(f"  {'PASS' if ok else 'FAIL'} [P3-5]: Main TP price"
                  f"  actual={new_main_tp_p3['price']:.8f}"
                  f"  expected={exp_main_price:.8f}")
            if not ok:
                p3_passed = False

        if old_placed_indices == {4, 5}:
            print(f"  PASS [P3-6]: pending tail = levels [4, 5]"
                  f"  (levels 1+2+3 filled, 4+5 placed)")
        else:
            print(f"  WARN [P3-6]: pending tail = {sorted(old_placed_indices)}"
                  f"  (expected [4, 5])")

        if not p3_passed:
            print("  Phase 3 checks failed — aborting")
            sys.exit(1)

        # ------------------------------------------------------------------
        # MANUAL ACTION 4: drag Reset TP DOWN to market → rebuild
        # ------------------------------------------------------------------
        print("\n" + "=" * 60)
        print("=== MANUAL ACTION 4: drag Reset TP DOWN to market ===")
        print("=" * 60)
        if reset_entry_p3:
            print(f"  Order:  order_id={reset_entry_p3['order_id']}"
                  f"  price={reset_entry_p3['price']:.8f}")
            print(f"  (Reset TP is ABOVE current price — drag DOWN)")
        else:
            print("  WARNING: Reset TP entry not available")
        print(f"  Expected: rebuild_pending_tail cancels levels [4]+[5]"
              f" and places 2 new tail orders")
        print(f"  Waiting up to {TIMEOUT}s for watcher to detect Reset TP fill ...")

        p4_rebuild_detected = False
        for _ in range(TIMEOUT):
            new_placed   = [l for l in session.levels
                            if l.status == "placed" and l.index not in old_placed_indices]
            old_canceled = [l for l in session.levels
                            if l.index in old_placed_indices and l.status == "canceled"]
            if len(new_placed) >= 1 and len(old_canceled) >= 1:
                p4_rebuild_detected = True
                break
            time.sleep(1.0)

        if not p4_rebuild_detected:
            print(f"  TIMEOUT: tail rebuild not detected after {TIMEOUT}s")
        else:
            print(f"  Tail rebuilt!")

        time.sleep(1.0)

        entry_after_p4 = None
        for pos in exchange.get_positions(symbol):
            if pos["positionSide"] == "LONG":
                ep = float(pos["entryPrice"])
                if ep > 0:
                    entry_after_p4 = ep
                break

        new_tail_all    = [l for l in session.levels
                           if l.status == "placed" and l.index not in old_placed_indices]
        new_tail_sorted = sorted(new_tail_all, key=lambda l: l.price, reverse=True)
        cfg_dbg         = service._grid_build_config.get((symbol, "LONG"), {})
        fo_c = cfg_dbg.get("first_offset_percent")
        lo_c = cfg_dbg.get("last_offset_percent")
        n_c  = cfg_dbg.get("orders_count")
        nc   = len(old_placed_indices)

        # ── Debug Block B ──────────────────────────────────────────────────
        print(f"\n=== [DEBUG-B] REBUILD ===")
        print(f"  new_entry_price   = {entry_after_p4}")
        print(f"  levels_cancelled  = {nc}  indices={sorted(old_placed_indices)}")
        print(f"  levels_placed     = {len(new_tail_all)}")
        print(f"  _grid_build_config:")
        print(f"    orders_count={n_c}  first_offset={fo_c}%  last_offset={lo_c}%"
              f"  distribution={cfg_dbg.get('distribution_mode')}")
        if fo_c is not None and lo_c is not None and n_c and nc > 1:
            orig_step    = (lo_c - fo_c) / (n_c - 1)
            rebuild_step = (lo_c - fo_c) / (nc - 1)
            print(f"  expected step (1/{n_c-1} of range): {orig_step:.2f}%")
            print(f"  actual rebuild step (1/{nc-1} of range): {rebuild_step:.2f}%")
        if entry_after_p4 and new_tail_sorted:
            print(f"\n  New levels (offsets from new_entry={entry_after_p4:.5f}):")
            for lvl in new_tail_sorted:
                off = (lvl.price - entry_after_p4) / entry_after_p4 * 100
                print(f"    [{lvl.index}]  price={lvl.price:.5f}  offset={off:+.2f}%")
            if len(new_tail_sorted) >= 2:
                print(f"  Steps between new levels:")
                for i in range(1, len(new_tail_sorted)):
                    s = abs(new_tail_sorted[i].price - new_tail_sorted[i-1].price) \
                        / entry_after_p4 * 100
                    print(f"    [{new_tail_sorted[i-1].index}->{new_tail_sorted[i].index}] {s:.2f}%")
        # ── End Debug Block B ──────────────────────────────────────────────

        print(f"\n  --- State after MANUAL ACTION 4 ---")
        print(f"  entry after Reset TP fill: {entry_after_p4}")
        print(f"  Final session levels ({len(session.levels)} total):")
        for l in session.levels:
            if l.status == "filled":
                tag = "filled"
            elif l.index in old_placed_indices and l.status == "canceled":
                tag = "CANCELED (old tail)"
            elif l.status == "placed" and l.index not in old_placed_indices:
                tag = "PLACED   (new tail)"
            else:
                tag = l.status
            print(f"    [{l.index}] order_id={l.order_id}  price={l.price:.8f}"
                  f"  status={l.status}  [{tag}]")
        print(f"  _reset_tp_order  = {service._reset_tp_order.get((symbol, 'LONG'))}")
        print(f"  _sl_orders       = {service._sl_orders.get((symbol, 'LONG'))}"
              f"  (no SL configured → None expected)")

        # ------------------------------------------------------------------
        # CHECKS PHASE 4
        # ------------------------------------------------------------------
        print("\n=== CHECKS PHASE 4 ===")
        p4_passed = True

        if p4_rebuild_detected:
            print("  PASS [P4-1]: tail rebuild detected")
        else:
            print("  FAIL [P4-1]: tail rebuild not detected")
            p4_passed = False

        old_tail = [l for l in session.levels if l.index in old_placed_indices]
        if old_tail and all(l.status == "canceled" for l in old_tail):
            print(f"  PASS [P4-2]: old tail levels canceled"
                  f"  indices={sorted(l.index for l in old_tail)}")
        else:
            print(f"  FAIL [P4-2]: old tail not fully canceled:"
                  f" {[(l.index, l.status) for l in old_tail]}")
            p4_passed = False

        expected_new_count = len(old_placed_indices)
        if new_tail_all and len(new_tail_all) == expected_new_count:
            print(f"  PASS [P4-3]: new tail placed  count={len(new_tail_all)}"
                  f"  indices={sorted(l.index for l in new_tail_all)}")
        else:
            print(f"  FAIL [P4-3]: new tail wrong  count={len(new_tail_all)}"
                  f"  expected={expected_new_count}")
            p4_passed = False

        if service.get_session(symbol, "LONG") is not None:
            print("  PASS [P4-4]: session still alive after rebuild")
        else:
            print("  FAIL [P4-4]: session was stopped unexpectedly")
            p4_passed = False

        sl_final = service._sl_orders.get((symbol, "LONG"))
        if sl_final is None:
            print("  PASS [P4-5]: _sl_orders is None  (no SL configured)")
        else:
            print(f"  INFO [P4-5]: _sl_orders = {sl_final}")

        # ── Debug Block C ──────────────────────────────────────────────────
        print(f"\n=== [DEBUG-C] GRID STEP SUMMARY ===")
        if entry_after_p4 and new_tail_sorted and fo_c is not None and n_c:
            expected_step = (lo_c - fo_c) / (n_c - 1)
            first_off = abs(new_tail_sorted[0].price - entry_after_p4) / entry_after_p4 * 100
            first_ok  = abs(first_off - fo_c) < 0.05
            print(f"  first rebuilt level at {fo_c:.1f}% from new entry:"
                  f"  {'PASS' if first_ok else 'FAIL'}  (actual: {first_off:.2f}%)")
            steps_ok = True
            for i in range(1, len(new_tail_sorted)):
                s  = abs(new_tail_sorted[i].price - new_tail_sorted[i-1].price) \
                     / entry_after_p4 * 100
                ok = abs(s - expected_step) < 0.05
                if not ok:
                    steps_ok = False
                lbl = f"[{new_tail_sorted[i-1].index}->{new_tail_sorted[i].index}]"
                print(f"  step {lbl} = {s:.2f}%:  {'PASS' if ok else 'FAIL'}"
                      f"  (expected {expected_step:.2f}%)")
            print(f"\n  rebuild preserved {expected_step:.1f}% grid step:"
                  f"         {'yes' if first_ok and steps_ok else 'NO'}")
            print(f"  rebuild followed expected non-custom grid logic:"
                  f" {'yes' if first_ok and steps_ok else 'NO'}")
        else:
            print("  (insufficient data for step check)")
        # ── End Debug Block C ──────────────────────────────────────────────

        if not p4_passed:
            sys.exit(1)

        # ------------------------------------------------------------------
        # MANUAL ACTION 5: close ~5 coins after rebuild
        # Tests Fix A (_last_known_qty tracking) + manual close branch
        # ------------------------------------------------------------------
        print("\n" + "=" * 60)
        print("=== MANUAL ACTION 5: close ~5 coins after rebuild ===")
        print("=" * 60)

        pos5_start    = 0.0
        entry5_start  = None
        for pos in exchange.get_positions(symbol):
            if pos["positionSide"] == "LONG":
                pos5_start   = abs(float(pos["positionAmt"]))
                entry5_start = float(pos["entryPrice"]) or None
                break

        main_tp_before_p5 = list(service._grid_tp_orders.get((symbol, "LONG"), []))
        main_tp_qty_start = main_tp_before_p5[0]["qty"] if main_tp_before_p5 else None
        tail_count_start  = len([l for l in session.levels if l.status == "placed"])

        print(f"  Current position     = {pos5_start}")
        print(f"  Current main TP qty  = {main_tp_qty_start}")
        print(f"  Current tail count   = {tail_count_start}")
        print(f"  Action: close ~5 coins manually on Binance (market sell)")
        print(f"  Expected:")
        print(f"    ManualClose detected by watcher on next tick")
        print(f"    Main TP repriced to ~{(pos5_start - 5):.0f} coins")
        print(f"    Tail grows {tail_count_start} → {tail_count_start + 1} levels")
        print(f"    New level at -3% from entry")
        print(f"  Waiting up to {TIMEOUT}s ...")

        p5_main_tp_repriced = False
        p5_tail_grew        = False
        for _ in range(TIMEOUT):
            main_tp_now  = list(service._grid_tp_orders.get((symbol, "LONG"), []))
            tail_now_cnt = len([l for l in session.levels if l.status == "placed"])
            qty_now      = main_tp_now[0]["qty"] if main_tp_now else None
            if qty_now is not None and qty_now != main_tp_qty_start:
                p5_main_tp_repriced = True
            if tail_now_cnt > tail_count_start:
                p5_tail_grew = True
            if p5_main_tp_repriced and p5_tail_grew:
                break
            time.sleep(1.0)

        watcher.stop_watching(symbol, "LONG")
        time.sleep(1.0)

        pos5_final   = 0.0
        entry5_final = None
        for pos in exchange.get_positions(symbol):
            if pos["positionSide"] == "LONG":
                pos5_final   = abs(float(pos["positionAmt"]))
                ep           = float(pos["entryPrice"])
                entry5_final = ep if ep > 0 else None
                break

        main_tp_p5   = list(service._grid_tp_orders.get((symbol, "LONG"), []))
        tail_p5      = [l for l in session.levels if l.status == "placed"]
        tail_p5_sort = sorted(tail_p5, key=lambda x: x.price, reverse=True)

        print(f"\n  --- State after MANUAL ACTION 5 ---")
        print(f"  position: {pos5_start} → {pos5_final}")
        if main_tp_p5:
            print(f"  main TP: qty={main_tp_p5[0]['qty']}"
                  f"  price={main_tp_p5[0]['price']:.8f}"
                  f"  order_id={main_tp_p5[0]['order_id']}")
        else:
            print(f"  main TP: None  ← MISSING!")
        print(f"  tail levels ({len(tail_p5)} total):")
        for l in tail_p5_sort:
            off = (l.price - entry5_final) / entry5_final * 100 if entry5_final else 0
            print(f"    [{l.index}]  price={l.price:.8f}  offset={off:+.2f}%")

        print("\n=== CHECKS PHASE 5 ===")
        p5_passed = True

        if p5_main_tp_repriced:
            qty_now = main_tp_p5[0]["qty"] if main_tp_p5 else None
            print(f"  PASS [P5-1]: main TP repriced  qty: {main_tp_qty_start} → {qty_now}")
        else:
            print(f"  FAIL [P5-1]: main TP NOT repriced after manual close")
            p5_passed = False

        if main_tp_p5 and abs(main_tp_p5[0]["qty"] - pos5_final) <= 1:
            print(f"  PASS [P5-2]: main TP qty={main_tp_p5[0]['qty']}"
                  f" matches position={pos5_final}")
        else:
            actual = main_tp_p5[0]["qty"] if main_tp_p5 else None
            print(f"  FAIL [P5-2]: main TP qty={actual} != position={pos5_final}")
            p5_passed = False

        if len(tail_p5) >= 3:
            print(f"  PASS [P5-3]: tail has {len(tail_p5)} levels (≥3 expected)")
        else:
            print(f"  FAIL [P5-3]: tail has {len(tail_p5)} levels (<3)")
            p5_passed = False

        if entry5_final and tail_p5_sort:
            first_off = abs(tail_p5_sort[0].price - entry5_final) / entry5_final * 100
            ok = abs(first_off - FIRST_OFFSET_PCT) < 0.05
            print(f"  {'PASS' if ok else 'FAIL'} [P5-4]: first tail at {first_off:.2f}%"
                  f"  (expected {FIRST_OFFSET_PCT:.1f}%)")
            if not ok:
                p5_passed = False

        if not p5_passed:
            print("  Phase 5 checks failed")

    except Exception as e:
        print(f"\nERROR: {e}")
        raise

    finally:
        watcher.stop_all()
        market_data.stop()

        print("\n=== FINAL CLEANUP ===")

        reset_e = service._reset_tp_order.pop((symbol, "LONG"), None)
        if reset_e:
            try:
                exchange.cancel_order(symbol, reset_e["order_id"])
                print(f"  cancelled Reset TP  order_id={reset_e['order_id']}")
            except Exception as e:
                print(f"  cancel Reset TP error (ignored): {e}")

        for tp in service._grid_tp_orders.pop((symbol, "LONG"), []):
            try:
                exchange.cancel_order(symbol, tp["order_id"])
                print(f"  cancelled main TP  order_id={tp['order_id']}")
            except Exception:
                pass
        service._tp_update_mode.pop((symbol, "LONG"), None)

        try:
            leftover = service.get_session(symbol, "LONG")
            if leftover is not None:
                service.stop_session(symbol, "LONG")
                print("  stopped LONG session")
        except Exception as e:
            print(f"  stop_session error (ignored): {e}")

        for pos in exchange.get_positions(symbol):
            if pos["positionSide"] == "LONG":
                qty = abs(float(pos["positionAmt"]))
                if qty > 0:
                    exchange.close_position(symbol, "sell", qty)
                    print(f"  closed LONG position  qty={qty}")

    print("\nTEST DONE")
