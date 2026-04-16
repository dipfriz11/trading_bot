"""
test_grid_sl_avg_entry_full_live.py

Live: SL avg_entry mode — full LONG lifecycle.
SIRENUSDT, 5 levels, Reset TP on level[3].

SL is placed at avg_entry × (1 - SL_PCT%) and re-placed after every fill.

P1: level[1] fill → SL placed for first time  (no position before first fill)
P2: level[2] fill → SL re-placed  (new algo_id, price = new avg_entry × factor)
P3: level[3] fill → Reset TP placed + SL re-placed
P4: Reset TP drag → rebuild → SL re-placed via rebuild dispatch
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


def _wait_sl_change(service, symbol, old_id, timeout=30):
    """Poll until _sl_orders changes from old_id. Returns new id or old_id on timeout."""
    for _ in range(timeout):
        cur = service._sl_orders.get((symbol, "LONG"))
        if cur is not None and cur != old_id:
            return cur
        time.sleep(1.0)
    return old_id


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

        # enable_tpsl avg_entry: config stored, no SL placed yet (no position)
        service.enable_tpsl(symbol, "LONG", sl_percent=SL_PCT, tp_percent=100.0, sl_mode="avg_entry")
        sl_initial = service._sl_orders.get((symbol, "LONG"))
        print(f"\n  enable_tpsl: sl_mode=avg_entry  SL_PCT={SL_PCT}%")
        print(f"  _sl_orders (initial) = {sl_initial}  (expected None — no position yet)")

        watcher.start_watching(symbol, "LONG")
        print(f"  watcher started")

        # ================================================================
        # MANUAL ACTION 1 — fill level[1]
        # Expected: SL placed for first time after averaging
        # ================================================================
        print("\n" + "=" * 60)
        print("=== MANUAL ACTION 1: drag level[1] UP to market ===")
        print("=" * 60)
        lvl1 = session.levels[0]
        print(f"  order_id={lvl1.order_id}  price={lvl1.price:.8f}")
        print(f"  Expected: SL placed for first time  algo_id appears in _sl_orders")
        print(f"  Waiting up to {TIMEOUT}s ...")

        p1_fill = False
        for _ in range(TIMEOUT):
            _filled_now = [l for l in session.levels if l.status == "filled"]
            _sl_now     = service._sl_orders.get((symbol, "LONG"))
            if _filled_now or _sl_now is not None:
                p1_fill = True
                break
            _pos_now = 0.0
            for _p in exchange.get_positions(symbol):
                if _p["positionSide"] == "LONG":
                    _pos_now = abs(float(_p["positionAmt"]))
                    break
            if _pos_now > 0:
                p1_fill = True
                break
            time.sleep(1.0)

        # Wait for SL placement (watcher tick + update_sl_after_averaging)
        sl_after_p1 = None
        for _ in range(30):
            sl_after_p1 = service._sl_orders.get((symbol, "LONG"))
            if sl_after_p1 is not None:
                break
            time.sleep(1.0)

        _filled_p1 = [l for l in session.levels if l.status == "filled"]
        _pos_p1    = 0.0
        for _p in exchange.get_positions(symbol):
            if _p["positionSide"] == "LONG":
                _pos_p1 = abs(float(_p["positionAmt"]))
                break
        entry_p1    = _get_entry(exchange, symbol)
        exp_sl_p1   = round(entry_p1 * (1 - SL_PCT / 100), 8) if entry_p1 else None
        tp_after_p1 = list(service._grid_tp_orders.get((symbol, "LONG"), []))

        print(f"\n  --- State after MA1 ---")
        print(f"  filled levels        = {[l.index for l in _filled_p1]}")
        print(f"  current position     = {_pos_p1}")
        print(f"  entry (exchange)     = {entry_p1}")
        print(f"  expected SL price    = {exp_sl_p1}  ({entry_p1} × (1 - {SL_PCT}%))")
        print(f"  _sl_orders (algo_id) = {sl_after_p1}")
        print(f"  main TP order_id     = {tp_after_p1[0]['order_id'] if tp_after_p1 else None}")

        print("\n=== CHECKS PHASE 1 ===")
        p1_ok = True
        if p1_fill:
            print(f"  PASS [P1-1]: phase 1 trigger  filled={[l.index for l in _filled_p1]}  pos={_pos_p1}")
        else:
            print(f"  FAIL [P1-1]: no fill/position/SL after {TIMEOUT}s")
            p1_ok = False
        if sl_after_p1 is not None:
            print(f"  PASS [P1-2]: SL placed after first fill  algo_id={sl_after_p1}")
        else:
            print("  FAIL [P1-2]: SL not placed — _sl_orders is None after MA1")
            p1_ok = False
        if not p1_ok:
            print("  Phase 1 failed — aborting")
            sys.exit(1)

        sl_before_p2 = sl_after_p1

        # ================================================================
        # MANUAL ACTION 2 — fill level[2]
        # Expected: SL re-placed, algo_id changes, price = new avg_entry × factor
        # ================================================================
        print("\n" + "=" * 60)
        print("=== MANUAL ACTION 2: drag level[2] UP to market ===")
        print("=" * 60)
        lvl2 = session.levels[1]
        print(f"  order_id={lvl2.order_id}  price={lvl2.price:.8f}")
        print(f"  Expected: SL re-placed (new algo_id, new avg_entry)")
        print(f"  Waiting up to {TIMEOUT}s ...")

        p2_fill = False
        for _ in range(TIMEOUT):
            if session.levels[1].status == "filled":
                p2_fill = True
                break
            time.sleep(1.0)

        sl_after_p2 = _wait_sl_change(service, symbol, sl_before_p2)
        entry_p2    = _get_entry(exchange, symbol)
        exp_sl_p2   = round(entry_p2 * (1 - SL_PCT / 100), 8) if entry_p2 else None

        print(f"\n  --- State after MA2 ---")
        print(f"  level[2].status      = {session.levels[1].status}")
        print(f"  entry (exchange)     = {entry_p2}")
        print(f"  expected SL price    = {exp_sl_p2}")
        print(f"  sl_id before MA2     = {sl_before_p2}")
        print(f"  sl_id after  MA2     = {sl_after_p2}  "
              f"({'CHANGED ✓' if sl_after_p2 != sl_before_p2 else 'UNCHANGED ✗'})")

        print("\n=== CHECKS PHASE 2 ===")
        p2_ok = True
        if p2_fill:
            print("  PASS [P2-1]: level[2] fill detected")
        else:
            print(f"  FAIL [P2-1]: level[2] not filled after {TIMEOUT}s")
            p2_ok = False
        if sl_after_p2 != sl_before_p2:
            print(f"  PASS [P2-2]: SL re-placed after MA2 (id: {sl_before_p2} → {sl_after_p2})")
        else:
            print(f"  FAIL [P2-2]: SL not updated after MA2 — id unchanged: {sl_after_p2}")
            p2_ok = False
        if not p2_ok:
            print("  Phase 2 failed — aborting")
            sys.exit(1)

        sl_before_p3 = sl_after_p2

        # ================================================================
        # MANUAL ACTION 3 — fill level[3] → Reset TP
        # Expected: SL re-placed after averaging (and again inside place_reset_tp_complex path)
        # ================================================================
        print("\n" + "=" * 60)
        print("=== MANUAL ACTION 3: drag level[3] UP to market ===")
        print("=" * 60)
        lvl3 = session.levels[2]
        print(f"  order_id={lvl3.order_id}  price={lvl3.price:.8f}")
        print(f"  Expected: Reset TP placed + SL re-placed (new avg_entry)")
        print(f"  Waiting up to {TIMEOUT}s ...")

        p3_fill      = False
        reset_p3     = None
        for _ in range(TIMEOUT):
            reset_now = service._reset_tp_order.get((symbol, "LONG"))
            if reset_now and session.levels[2].status == "filled":
                p3_fill  = True
                reset_p3 = dict(reset_now)
                break
            time.sleep(1.0)

        sl_after_p3 = _wait_sl_change(service, symbol, sl_before_p3)
        entry_p3    = _get_entry(exchange, symbol)
        exp_sl_p3   = round(entry_p3 * (1 - SL_PCT / 100), 8) if entry_p3 else None
        old_placed_indices = {l.index for l in session.levels if l.status == "placed"}

        print(f"\n  --- State after MA3 ---")
        print(f"  level[3].status      = {session.levels[2].status}")
        print(f"  Reset TP order_id    = {reset_p3['order_id'] if reset_p3 else None}")
        print(f"  entry (exchange)     = {entry_p3}")
        print(f"  expected SL price    = {exp_sl_p3}")
        print(f"  sl_id before MA3     = {sl_before_p3}")
        print(f"  sl_id after  MA3     = {sl_after_p3}  "
              f"({'CHANGED ✓' if sl_after_p3 != sl_before_p3 else 'UNCHANGED ✗'})")
        print(f"  pending tail indices = {sorted(old_placed_indices)}")

        print("\n=== CHECKS PHASE 3 ===")
        p3_ok = True
        if p3_fill:
            print("  PASS [P3-1]: level[3] filled + Reset TP placed")
        else:
            print(f"  FAIL [P3-1]: level[3] fill or Reset TP missing after {TIMEOUT}s")
            p3_ok = False
        if sl_after_p3 != sl_before_p3:
            print(f"  PASS [P3-2]: SL re-placed after MA3 (id: {sl_before_p3} → {sl_after_p3})")
        else:
            print(f"  FAIL [P3-2]: SL not updated after MA3 — id unchanged: {sl_after_p3}")
            p3_ok = False
        if not p3_ok:
            print("  Phase 3 failed — aborting")
            sys.exit(1)

        sl_before_p4 = sl_after_p3

        # ================================================================
        # MANUAL ACTION 4 — drag Reset TP DOWN → rebuild
        # Expected: rebuild_pending_tail → SL re-placed via avg_entry dispatch
        # ================================================================
        print("\n" + "=" * 60)
        print("=== MANUAL ACTION 4: drag Reset TP DOWN to market ===")
        print("=" * 60)
        if reset_p3:
            print(f"  Reset TP order_id={reset_p3['order_id']}  price={reset_p3['price']:.8f}")
        print(f"  Expected: rebuild + SL re-placed (new avg_entry after reset TP fill)")
        print(f"  Waiting up to {TIMEOUT}s ...")

        p4_rebuild = False
        for _ in range(TIMEOUT):
            new_placed  = [l for l in session.levels
                           if l.status == "placed" and l.index not in old_placed_indices]
            old_canceled = [l for l in session.levels
                            if l.index in old_placed_indices and l.status == "canceled"]
            if len(new_placed) >= 1 and len(old_canceled) >= 1:
                p4_rebuild = True
                break
            time.sleep(1.0)

        sl_after_p4 = _wait_sl_change(service, symbol, sl_before_p4)
        time.sleep(1.0)
        entry_p4    = _get_entry(exchange, symbol)
        exp_sl_p4   = round(entry_p4 * (1 - SL_PCT / 100), 8) if entry_p4 else None
        new_tail    = sorted(
            [l for l in session.levels if l.status == "placed" and l.index not in old_placed_indices],
            key=lambda l: l.price, reverse=True
        )

        print(f"\n  --- State after MA4 ---")
        print(f"  entry (exchange)     = {entry_p4}")
        print(f"  expected SL price    = {exp_sl_p4}  ({entry_p4} × (1 - {SL_PCT}%))")
        print(f"  new tail indices     = {[l.index for l in new_tail]}")
        print(f"  new tail prices      = {[f'{l.price:.8f}' for l in new_tail]}")
        print(f"  sl_id before MA4     = {sl_before_p4}")
        print(f"  sl_id after  MA4     = {sl_after_p4}  "
              f"({'CHANGED ✓' if sl_after_p4 != sl_before_p4 else 'UNCHANGED ✗'})")

        print("\n=== CHECKS PHASE 4 ===")
        p4_ok = True
        if p4_rebuild:
            print(f"  PASS [P4-1]: rebuild detected  new_tail_count={len(new_tail)}")
        else:
            print(f"  FAIL [P4-1]: rebuild not detected after {TIMEOUT}s")
            p4_ok = False
        if sl_after_p4 != sl_before_p4:
            print(f"  PASS [P4-2]: SL re-placed after rebuild (id: {sl_before_p4} → {sl_after_p4})")
        else:
            print(f"  FAIL [P4-2]: SL not updated after rebuild — id unchanged: {sl_after_p4}")
            p4_ok = False
        if not p4_ok:
            print("  Phase 4 checks failed")

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
