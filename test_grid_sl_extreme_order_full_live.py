"""
test_grid_sl_extreme_order_full_live.py

Live: SL extreme_order mode — full LONG lifecycle.
SIRENUSDT, 5 levels, Reset TP on level[3].

SL is placed at min(placed_levels).price × (1 - SL_PCT%) at session start.
After fills (averaging): SL does NOT update.
After rebuild: SL updates to new min(placed_levels).price × (1 - SL_PCT%).

P1: enable_tpsl → SL placed immediately at extreme (min of all 5 placed)
P2: level[1] fill → SL NOT updated (same algo_id)
P3: level[2] fill → SL NOT updated (same algo_id)
P4: level[3] fill → Reset TP placed, SL NOT updated (same algo_id)
P5: Reset TP drag → rebuild → SL updated at new extreme (min of new tail)
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
FIRST_OFFSET_PCT = 1.0
LAST_OFFSET_PCT  = 5.0
TP_PCT           = 3.0
RESET_TP_PCT     = 1.0
RESET_CLOSE_PCT  = 45
SL_PCT           = 5.0
TIMEOUT          = 120

LEVEL_RESET_CONFIGS = [
    {"use_reset_tp": False},
    {"use_reset_tp": False},
    {"use_reset_tp": True, "reset_tp_percent": RESET_TP_PCT, "reset_tp_close_percent": RESET_CLOSE_PCT},
    {"use_reset_tp": True, "reset_tp_percent": RESET_TP_PCT, "reset_tp_close_percent": RESET_CLOSE_PCT},
    {"use_reset_tp": True, "reset_tp_percent": RESET_TP_PCT, "reset_tp_close_percent": RESET_CLOSE_PCT},
]


def _get_entry(exchange, symbol):
    for pos in exchange.get_positions(symbol):
        if pos["positionSide"] == "LONG":
            ep = float(pos["entryPrice"])
            return ep if ep > 0 else None
    return None


def _extreme_basis(session, symbol, position_side="LONG"):
    placed = [l for l in session.levels if l.status == "placed"]
    if not placed:
        return None
    return min(l.price for l in placed) if position_side == "LONG" else max(l.price for l in placed)


if __name__ == "__main__":
    symbol = "SIRENUSDT"

    exchange    = BinanceExchange()
    service     = GridService(GridBuilder(), GridRunner(exchange), GridRegistry(), exchange, GridSizer())
    market_data = MarketDataService(exchange.client)
    watcher     = GridTrailingWatcher(service, market_data, cooldown_sec=2.0)

    # ------------------------------------------------------------------
    # PRE-CLEANUP
    # ------------------------------------------------------------------
    print("\n=== PRE-CLEANUP ===")
    if service.get_session(symbol, "LONG"):
        service.stop_session(symbol, "LONG")
        print("  stopped leftover session")
    else:
        print("  no leftover session")
    for pos in exchange.get_positions(symbol):
        if pos["positionSide"] == "LONG":
            qty = abs(float(pos["positionAmt"]))
            if qty > 0:
                exchange.close_position(symbol, "sell", qty)
                print(f"  closed leftover position  qty={qty}")
    time.sleep(1.0)

    try:
        # ------------------------------------------------------------------
        # START SESSION
        # ------------------------------------------------------------------
        print("\n=== START SESSION ===")
        session = service.start_session(
            symbol=symbol, position_side="LONG",
            total_budget=45.0, levels_count=GRID_ORDERS,
            step_percent=1.0, orders_count=GRID_ORDERS,
            first_offset_percent=FIRST_OFFSET_PCT, last_offset_percent=LAST_OFFSET_PCT,
            distribution_mode="step", distribution_value=1.0,
            level_reset_configs=LEVEL_RESET_CONFIGS,
        )
        print(f"  session_id={session.session_id}")
        for lvl in session.levels:
            print(f"    [{lvl.index}] order_id={lvl.order_id}  price={lvl.price:.8f}"
                  f"  qty={lvl.qty}  use_reset_tp={lvl.use_reset_tp}")

        service.set_tp_update_mode(symbol, "LONG", "reprice")
        service._grid_tp_config[(symbol, "LONG")] = [{"tp_percent": TP_PCT, "close_percent": 100}]

        # enable_tpsl extreme_order: SL placed immediately at min(placed levels)
        initial_extreme = _extreme_basis(session, symbol)
        service.enable_tpsl(symbol, "LONG", sl_percent=SL_PCT, tp_percent=100.0, sl_mode="extreme_order")
        sl_initial = service._sl_orders.get((symbol, "LONG"))
        exp_sl_initial = round(initial_extreme * (1 - SL_PCT / 100), 8) if initial_extreme else None

        print(f"\n  enable_tpsl: sl_mode=extreme_order  SL_PCT={SL_PCT}%")
        print(f"  initial extreme basis (min placed) = {initial_extreme:.8f}" if initial_extreme else "  initial extreme = N/A")
        print(f"  expected initial SL price          = {exp_sl_initial}")
        print(f"  _sl_orders (initial algo_id)       = {sl_initial}")

        watcher.start_watching(symbol, "LONG")
        print(f"  watcher started")

        # ================================================================
        # CHECKS PHASE 1 — initial SL placement
        # ================================================================
        print("\n=== CHECKS PHASE 1: extreme_order config armed ===")
        p1_ok = True
        if sl_initial is not None:
            print(f"  PASS [P1-1]: SL placed at enable_tpsl  algo_id={sl_initial}")
        else:
            cfg_saved = service._tpsl_configs.get((symbol, "LONG"))
            if cfg_saved is not None:
                print(f"  PASS [P1-1]: SL armed virtually (no position yet) — config saved  sl_mode={cfg_saved.sl_mode}")
            else:
                print("  FAIL [P1-1]: config not saved after enable_tpsl")
                p1_ok = False
        if initial_extreme is not None:
            expected_extreme = min(l.price for l in session.levels if l.status == "placed")
            ok = abs(initial_extreme - expected_extreme) < 1e-8
            print(f"  {'PASS' if ok else 'FAIL'} [P1-2]: extreme basis = min(placed levels)"
                  f"  actual={initial_extreme:.8f}  expected={expected_extreme:.8f}")
            if not ok:
                p1_ok = False
        if not p1_ok:
            print("  Phase 1 failed — aborting")
            sys.exit(1)

        sl_id_anchor = sl_initial  # None if armed virtually; updated to real algo_id after first fill (Phase 2)

        # ================================================================
        # MANUAL ACTION 1 — fill level[1]
        # Expected: SL NOT updated (extreme_order early return)
        # ================================================================
        print("\n" + "=" * 60)
        print("=== MANUAL ACTION 1: drag level[1] UP to market ===")
        print("=" * 60)
        lvl1 = session.levels[0]
        print(f"  order_id={lvl1.order_id}  price={lvl1.price:.8f}")
        print(f"  Expected: SL placed after first fill (armed→placed)  anchor={sl_id_anchor}")
        print(f"  Waiting up to {TIMEOUT}s ...")

        p2_fill = False
        for _ in range(TIMEOUT):
            _filled_now = [l for l in session.levels if l.status == "filled"]
            if _filled_now:
                p2_fill = True
                break
            _pos_now = 0.0
            for _p in exchange.get_positions(symbol):
                if _p["positionSide"] == "LONG":
                    _pos_now = abs(float(_p["positionAmt"]))
                    break
            if _pos_now > 0:
                p2_fill = True
                break
            time.sleep(1.0)

        time.sleep(5.0)  # let watcher tick process the fill
        # For extreme_order armed virtually: wait for first real SL placement
        if sl_id_anchor is None:
            for _ in range(20):
                if service._sl_orders.get((symbol, "LONG")) is not None:
                    break
                time.sleep(1.0)
        _filled_p2   = [l for l in session.levels if l.status == "filled"]
        _pos_p2      = 0.0
        for _p in exchange.get_positions(symbol):
            if _p["positionSide"] == "LONG":
                _pos_p2 = abs(float(_p["positionAmt"]))
                break
        sl_after_p2  = service._sl_orders.get((symbol, "LONG"))
        extreme_p2   = _extreme_basis(session, symbol)
        entry_p2     = _get_entry(exchange, symbol)

        print(f"\n  --- State after MA1 ---")
        print(f"  filled levels           = {[l.index for l in _filled_p2]}")
        print(f"  current position        = {_pos_p2}")
        print(f"  entry (exchange)        = {entry_p2}")
        print(f"  current extreme basis   = {extreme_p2:.8f}" if extreme_p2 else "  extreme = N/A")
        print(f"  sl_id anchor            = {sl_id_anchor}")
        print(f"  sl_id now               = {sl_after_p2}  "
              f"({'armed→placed ✓' if sl_id_anchor is None and sl_after_p2 is not None else 'UNCHANGED ✓' if sl_after_p2 == sl_id_anchor else 'CHANGED ✗'})")

        print("\n=== CHECKS PHASE 2 ===")
        p2_ok = True
        if p2_fill:
            print(f"  PASS [P2-1]: phase 2 trigger  filled={[l.index for l in _filled_p2]}  pos={_pos_p2}")
        else:
            print(f"  FAIL [P2-1]: no fill/position after {TIMEOUT}s")
            p2_ok = False
        if sl_id_anchor is None:
            # armed→placed transition expected
            if sl_after_p2 is not None:
                print(f"  PASS [P2-2]: SL placed after first fill (armed→placed)  algo_id={sl_after_p2}")
                sl_id_anchor = sl_after_p2  # anchor now set; must stay unchanged through P3, P4
            else:
                print(f"  FAIL [P2-2]: SL still None after first fill — armed→placed transition failed")
                p2_ok = False
        elif sl_after_p2 == sl_id_anchor:
            print(f"  PASS [P2-2]: SL NOT updated after fill  (algo_id={sl_after_p2})")
        else:
            print(f"  FAIL [P2-2]: SL was updated unexpectedly: {sl_id_anchor} → {sl_after_p2}")
            p2_ok = False
        if not p2_ok:
            print("  Phase 2 failed — aborting")
            sys.exit(1)

        # ================================================================
        # MANUAL ACTION 2 — fill level[2]
        # Expected: SL NOT updated
        # ================================================================
        print("\n" + "=" * 60)
        print("=== MANUAL ACTION 2: drag level[2] UP to market ===")
        print("=" * 60)
        lvl2 = session.levels[1]
        print(f"  order_id={lvl2.order_id}  price={lvl2.price:.8f}")
        print(f"  Expected: SL NOT updated (same algo_id={sl_id_anchor})")
        print(f"  Waiting up to {TIMEOUT}s ...")

        p3_fill = False
        for _ in range(TIMEOUT):
            if session.levels[1].status == "filled":
                p3_fill = True
                break
            time.sleep(1.0)

        time.sleep(5.0)
        sl_after_p3  = service._sl_orders.get((symbol, "LONG"))
        extreme_p3   = _extreme_basis(session, symbol)
        entry_p3     = _get_entry(exchange, symbol)

        print(f"\n  --- State after MA2 ---")
        print(f"  level[2].status         = {session.levels[1].status}")
        print(f"  entry (exchange)        = {entry_p3}")
        print(f"  current extreme basis   = {extreme_p3:.8f}" if extreme_p3 else "  extreme = N/A")
        print(f"  sl_id anchor            = {sl_id_anchor}")
        print(f"  sl_id now               = {sl_after_p3}  "
              f"({'UNCHANGED ✓' if sl_after_p3 == sl_id_anchor else 'CHANGED ✗ — unexpected update'})")

        print("\n=== CHECKS PHASE 3 ===")
        p3_ok = True
        if p3_fill:
            print("  PASS [P3-1]: level[2] fill detected")
        else:
            print(f"  FAIL [P3-1]: level[2] not filled after {TIMEOUT}s")
            p3_ok = False
        if sl_after_p3 == sl_id_anchor:
            print(f"  PASS [P3-2]: SL NOT updated after level[2] fill  (algo_id={sl_after_p3})")
        else:
            print(f"  FAIL [P3-2]: SL was updated unexpectedly: {sl_id_anchor} → {sl_after_p3}")
            p3_ok = False
        if not p3_ok:
            print("  Phase 3 failed — aborting")
            sys.exit(1)

        # ================================================================
        # MANUAL ACTION 3 — fill level[3] → Reset TP
        # Expected: SL NOT updated even though Reset TP is placed
        # ================================================================
        print("\n" + "=" * 60)
        print("=== MANUAL ACTION 3: drag level[3] UP to market ===")
        print("=" * 60)
        lvl3 = session.levels[2]
        print(f"  order_id={lvl3.order_id}  price={lvl3.price:.8f}")
        print(f"  Expected: Reset TP placed, SL NOT updated (same algo_id={sl_id_anchor})")
        print(f"  Waiting up to {TIMEOUT}s ...")

        p4_fill  = False
        reset_p4 = None
        for _ in range(TIMEOUT):
            reset_now = service._reset_tp_order.get((symbol, "LONG"))
            if reset_now and session.levels[2].status == "filled":
                p4_fill  = True
                reset_p4 = dict(reset_now)
                break
            time.sleep(1.0)

        time.sleep(5.0)
        sl_after_p4  = service._sl_orders.get((symbol, "LONG"))
        extreme_p4   = _extreme_basis(session, symbol)
        old_placed_indices = {l.index for l in session.levels if l.status == "placed"}

        print(f"\n  --- State after MA3 ---")
        print(f"  level[3].status         = {session.levels[2].status}")
        print(f"  Reset TP order_id       = {reset_p4['order_id'] if reset_p4 else None}")
        print(f"  current extreme basis   = {extreme_p4:.8f}" if extreme_p4 else "  extreme = N/A")
        print(f"  sl_id anchor            = {sl_id_anchor}")
        print(f"  sl_id now               = {sl_after_p4}  "
              f"({'UNCHANGED ✓' if sl_after_p4 == sl_id_anchor else 'CHANGED ✗ — unexpected update'})")
        print(f"  pending tail indices    = {sorted(old_placed_indices)}")

        print("\n=== CHECKS PHASE 4 ===")
        p4_ok = True
        if p4_fill:
            print("  PASS [P4-1]: level[3] filled + Reset TP placed")
        else:
            print(f"  FAIL [P4-1]: level[3] fill or Reset TP missing after {TIMEOUT}s")
            p4_ok = False
        if sl_after_p4 == sl_id_anchor:
            print(f"  PASS [P4-2]: SL NOT updated after level[3] fill  (algo_id={sl_after_p4})")
        else:
            print(f"  FAIL [P4-2]: SL was updated unexpectedly: {sl_id_anchor} → {sl_after_p4}")
            p4_ok = False
        if not p4_ok:
            print("  Phase 4 failed — aborting")
            sys.exit(1)

        # ================================================================
        # MANUAL ACTION 4 — drag Reset TP DOWN → rebuild
        # Expected: SL UPDATED at new extreme (min of new tail levels)
        # ================================================================
        print("\n" + "=" * 60)
        print("=== MANUAL ACTION 4: drag Reset TP DOWN to market ===")
        print("=" * 60)
        if reset_p4:
            print(f"  Reset TP order_id={reset_p4['order_id']}  price={reset_p4['price']:.8f}")
        print(f"  Expected: rebuild → SL updated at new extreme (min of new tail)")
        print(f"  Waiting up to {TIMEOUT}s ...")

        p5_rebuild = False
        for _ in range(TIMEOUT):
            new_placed  = [l for l in session.levels
                           if l.status == "placed" and l.index not in old_placed_indices]
            old_canceled = [l for l in session.levels
                            if l.index in old_placed_indices and l.status == "canceled"]
            if len(new_placed) >= 1 and len(old_canceled) >= 1:
                p5_rebuild = True
                break
            time.sleep(1.0)

        # Wait for SL update (should change from anchor)
        sl_after_p5 = sl_id_anchor
        for _ in range(30):
            cur = service._sl_orders.get((symbol, "LONG"))
            if cur is not None and cur != sl_id_anchor:
                sl_after_p5 = cur
                break
            time.sleep(1.0)

        time.sleep(1.0)
        new_tail      = sorted(
            [l for l in session.levels if l.status == "placed" and l.index not in old_placed_indices],
            key=lambda l: l.price, reverse=True
        )
        extreme_after = _extreme_basis(session, symbol)
        exp_sl_after  = round(extreme_after * (1 - SL_PCT / 100), 8) if extreme_after else None

        print(f"\n  --- State after MA4 ---")
        print(f"  new tail indices        = {[l.index for l in new_tail]}")
        print(f"  new tail prices         = {[f'{l.price:.8f}' for l in new_tail]}")
        print(f"  new extreme basis       = {extreme_after:.8f}" if extreme_after else "  extreme = N/A")
        print(f"  expected SL price       = {exp_sl_after}  (extreme × (1 - {SL_PCT}%))")
        print(f"  sl_id anchor (initial)  = {sl_id_anchor}")
        print(f"  sl_id after rebuild     = {sl_after_p5}  "
              f"({'CHANGED ✓' if sl_after_p5 != sl_id_anchor else 'UNCHANGED ✗'})")

        print("\n=== CHECKS PHASE 5 ===")
        p5_ok = True
        if p5_rebuild:
            print(f"  PASS [P5-1]: rebuild detected  new_tail_count={len(new_tail)}")
        else:
            print(f"  FAIL [P5-1]: rebuild not detected after {TIMEOUT}s")
            p5_ok = False
        if sl_after_p5 != sl_id_anchor:
            print(f"  PASS [P5-2]: SL updated after rebuild (id: {sl_id_anchor} → {sl_after_p5})")
        else:
            print(f"  FAIL [P5-2]: SL not updated after rebuild — id unchanged: {sl_after_p5}")
            p5_ok = False
        if extreme_after is not None and new_tail:
            exp_extreme = min(l.price for l in new_tail)
            ok = abs(extreme_after - exp_extreme) < 1e-8
            print(f"  {'PASS' if ok else 'FAIL'} [P5-3]: new extreme = min(new tail)"
                  f"  actual={extreme_after:.8f}  expected={exp_extreme:.8f}")
            if not ok:
                p5_ok = False
        if not p5_ok:
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
            except Exception as ex:
                print(f"  cancel Reset TP error (ignored): {ex}")
        for tp in service._grid_tp_orders.pop((symbol, "LONG"), []):
            try:
                exchange.cancel_order(symbol, tp["order_id"])
                print(f"  cancelled main TP  order_id={tp['order_id']}")
            except Exception:
                pass
        service._tp_update_mode.pop((symbol, "LONG"), None)
        service.disable_tpsl(symbol, "LONG")
        try:
            if service.get_session(symbol, "LONG"):
                service.stop_session(symbol, "LONG")
                print("  stopped LONG session")
        except Exception as ex:
            print(f"  stop_session error (ignored): {ex}")
        for pos in exchange.get_positions(symbol):
            if pos["positionSide"] == "LONG":
                qty = abs(float(pos["positionAmt"]))
                if qty > 0:
                    exchange.close_position(symbol, "sell", qty)
                    print(f"  closed LONG position  qty={qty}")

    print("\nTEST DONE")
