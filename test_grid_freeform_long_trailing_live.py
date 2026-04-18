"""
test_grid_freeform_long_trailing_live.py

Freeform live reconcile test — LONG, HIGHUSDT — trailing pre-entry enabled.

Session starts with full config (5 levels, Reset TP on [3,4,5], SL, main TP, trailing).
After start: no scripted phases. User can freely:
  - let grid trail as price moves up (pre-entry)
  - drag grid orders to market
  - move Reset TP
  - partially close / add to position manually
  - do anything on exchange

System reconciles automatically via GridTrailingWatcher.
Test prints state snapshots on every change + 30s heartbeat.
Exits when: position=0 + no active orders + no reset TP + no main TP + no SL.
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

GRID_ORDERS       = 5
FIRST_OFFSET_PCT  = 1.0
LAST_OFFSET_PCT   = 5.0
TP_PCT            = 3.0
RESET_TP_PCT      = 1.0
RESET_CLOSE_PCT   = 45
SL_PCT            = 5.0
TRAILING_STEP_PCT     = 1.0    # используется только для step mode (trailing SL)
TRAILING_DEBOUNCE_PCT = 0.1    # continuous mode: min move to trigger reprice (rate-limit guard)
SNAP_INTERVAL         = 3      # poll every N seconds
HEARTBEAT_EVERY   = 30     # force-print snapshot every N seconds

LEVEL_RESET_CONFIGS = [
    {"use_reset_tp": False},
    {"use_reset_tp": False},
    {"use_reset_tp": True, "reset_tp_percent": RESET_TP_PCT, "reset_tp_close_percent": RESET_CLOSE_PCT},
    {"use_reset_tp": True, "reset_tp_percent": RESET_TP_PCT, "reset_tp_close_percent": RESET_CLOSE_PCT},
    {"use_reset_tp": True, "reset_tp_percent": RESET_TP_PCT, "reset_tp_close_percent": RESET_CLOSE_PCT},
]


def _get_pos(exchange, symbol):
    for p in exchange.get_positions(symbol):
        if p["positionSide"] == "LONG":
            return abs(float(p["positionAmt"])), float(p["entryPrice"])
    return 0.0, 0.0


def _snap_key(service, exchange, session, symbol):
    """Build a comparable state dict for change detection."""
    pos_qty, entry = _get_pos(exchange, symbol)
    key = (symbol, "LONG")
    levels_status = {l.index: l.status for l in session.levels}
    tp_ids  = [t["order_id"] for t in service._grid_tp_orders.get(key, [])]
    rtp     = service._reset_tp_order.get(key)
    rtp_id  = rtp["order_id"] if rtp else None
    sl_id   = service._sl_orders.get(key)
    tcfg    = service._trailing_configs.get(key)
    anchor  = round(tcfg.anchor_price, 8) if tcfg else None
    return {
        "pos_qty":    round(pos_qty, 4),
        "entry":      round(entry, 8),
        "levels":     levels_status,
        "tp_ids":     tp_ids,
        "rtp_id":     rtp_id,
        "sl_id":      sl_id,
        "anchor":     anchor,
    }


def _print_snap(service, exchange, session, symbol, elapsed, tag="SNAP"):
    pos_qty, entry = _get_pos(exchange, symbol)
    key = (symbol, "LONG")

    by_status = {}
    for l in session.levels:
        by_status.setdefault(l.status, []).append(l.index)

    tp_list  = service._grid_tp_orders.get(key, [])
    rtp      = service._reset_tp_order.get(key)
    sl_id    = service._sl_orders.get(key)
    tcfg     = service._trailing_configs.get(key)

    mins  = int(elapsed) // 60
    secs  = int(elapsed) % 60
    ts    = f"{mins:02d}:{secs:02d}"

    print(f"\n[{tag}] {ts}  pos={pos_qty}  entry={entry:.8f}")
    print(f"  levels  : { {s: idx for s, idx in by_status.items()} }")
    for tp in tp_list:
        print(f"  main TP : order_id={tp['order_id']}  price={tp['price']:.8f}  qty={tp['qty']}")
    if not tp_list:
        print(f"  main TP : None")
    if rtp:
        print(f"  reset TP: order_id={rtp['order_id']}  price={rtp['price']:.8f}  qty={rtp['qty']}")
    else:
        print(f"  reset TP: None")
    if sl_id:
        print(f"  SL      : algoId={sl_id}")
    else:
        print(f"  SL      : None")
    if tcfg:
        print(f"  trailing: anchor={tcfg.anchor_price:.8f}  step={tcfg.trailing_step_percent}%")
    else:
        print(f"  trailing: (inactive)")


def _is_cycle_done(service, exchange, session, symbol):
    pos_qty, _ = _get_pos(exchange, symbol)
    if pos_qty > 0:
        return False
    key = (symbol, "LONG")
    has_placed  = any(l.status == "placed" for l in session.levels)
    has_rtp     = bool(service._reset_tp_order.get(key))
    has_tp      = bool(service._grid_tp_orders.get(key))
    has_sl      = bool(service._sl_orders.get(key))
    return not has_placed and not has_rtp and not has_tp and not has_sl


if __name__ == "__main__":
    symbol = "HIGHUSDT"

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

    start_time = time.monotonic()

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
        service.enable_tpsl(symbol, "LONG", sl_percent=SL_PCT, tp_percent=100.0, sl_mode="avg_entry")

        anchor = service.enable_trailing(
            symbol, "LONG",
            trailing_step_percent=TRAILING_STEP_PCT,
            first_offset_percent=FIRST_OFFSET_PCT,
            last_offset_percent=LAST_OFFSET_PCT,
            total_budget=45.0,
            orders_count=GRID_ORDERS,
            distribution_mode="step",
            distribution_value=1.0,
            trailing_mode="continuous",
            trailing_debounce_percent=TRAILING_DEBOUNCE_PCT,
        )
        print(f"  trailing enabled  anchor={anchor:.8f}  step={TRAILING_STEP_PCT}%")

        watcher.start_watching(symbol, "LONG")
        print(f"\n  watcher started  SL_PCT={SL_PCT}%  TP_PCT={TP_PCT}%"
              f"  RESET_CLOSE={RESET_CLOSE_PCT}%  TRAILING_STEP={TRAILING_STEP_PCT}%")
        print(f"\n  *** Free to act on exchange. Test exits when position=0 + no active orders. ***\n")

        # ------------------------------------------------------------------
        # MONITOR LOOP
        # ------------------------------------------------------------------
        prev_state   = {}
        last_hb_time = start_time

        while True:
            now     = time.monotonic()
            elapsed = now - start_time

            cur_state = _snap_key(service, exchange, session, symbol)

            changed   = cur_state != prev_state
            heartbeat = (now - last_hb_time) >= HEARTBEAT_EVERY

            if changed:
                _print_snap(service, exchange, session, symbol, elapsed, tag="CHANGE")
                prev_state   = cur_state
                last_hb_time = now
            elif heartbeat:
                _print_snap(service, exchange, session, symbol, elapsed, tag="HB")
                last_hb_time = now

            if _is_cycle_done(service, exchange, session, symbol):
                print(f"\n[DONE] position=0 + no active orders — cycle complete  elapsed={elapsed:.0f}s")
                break

            time.sleep(SNAP_INTERVAL)

    except KeyboardInterrupt:
        elapsed = time.monotonic() - start_time
        print(f"\n[INTERRUPT] Ctrl+C — stopping  elapsed={elapsed:.0f}s")

    except Exception as e:
        print(f"\n[ERROR] {e}")
        raise

    finally:
        watcher.stop_all()
        market_data.stop()

        print("\n=== FINAL CLEANUP ===")
        key = (symbol, "LONG")
        rtp = service._reset_tp_order.pop(key, None)
        if rtp:
            try:
                exchange.cancel_order(symbol, rtp["order_id"])
                print(f"  cancelled Reset TP  order_id={rtp['order_id']}")
            except Exception as ex:
                print(f"  cancel Reset TP error (ignored): {ex}")
        for tp in service._grid_tp_orders.pop(key, []):
            try:
                exchange.cancel_order(symbol, tp["order_id"])
                print(f"  cancelled main TP  order_id={tp['order_id']}")
            except Exception:
                pass
        service._tp_update_mode.pop(key, None)
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
