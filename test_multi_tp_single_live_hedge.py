# test_multi_tp_single_live_hedge.py
#
# Live test: SingleOrderStrategy hedge mode — одновременно LONG + SHORT,
# у каждой ноги свои 2 TP + 1 SL.
#
# Flow:
#   strategy.execute("buy")  → LONG  + place_multi_tpsl("LONG")
#   strategy.execute("sell") → SHORT + place_multi_tpsl("SHORT")
#
# Verifies:
#   1. LONG позиция открылась
#   2. SHORT позиция открылась
#   3. order_manager.tpsl содержит отдельный state для LONG и SHORT
#   4. Все algo-ордера обеих ног видны на бирже
#   5. cancel_tpsl("LONG") не ломает SHORT state и его algo-ордера
#   6. Финальный cleanup полностью чистый

import sys
import time

from exchange.binance_exchange import BinanceExchange
from widget.widget import Widget

if __name__ == "__main__":

    symbol = "SIRENUSDT"

    coin_cfg = {
        "entry_type": "market",
        "leverage":   1,
        "long": {
            "usdt_amount": 8.5,
            "sl_percent":  10.0,
            "take_profits": [
                {"tp_percent": 5.0,  "close_percent": 50},
                {"tp_percent": 10.0, "close_percent": 50},
            ],
        },
        "short": {
            "usdt_amount": 8.5,
            "sl_percent":  10.0,
            "take_profits": [
                {"tp_percent": 5.0,  "close_percent": 50},
                {"tp_percent": 10.0, "close_percent": 50},
            ],
        },
    }

    exchange = BinanceExchange()

    def get_open_algos() -> list:
        resp = exchange.client.futures_get_open_algo_orders(symbol=symbol)
        if isinstance(resp, list):
            return resp
        return resp.get("openAlgoOrders", [])

    def cancel_algo(algo_id: int) -> None:
        try:
            exchange.client.futures_cancel_algo_order(algoId=algo_id)
        except Exception as e:
            print(f"  cancel_algo {algo_id}: {e}")

    def get_position(position_side: str) -> tuple:
        for pos in exchange.get_positions(symbol):
            if pos["positionSide"] == position_side:
                qty = abs(float(pos["positionAmt"]))
                ep  = float(pos["entryPrice"]) if qty > 0 else None
                return ep, qty
        return None, 0.0

    # ------------------------------------------------------------------
    # PRE-CLEANUP
    # ------------------------------------------------------------------
    print("\n=== PRE-CLEANUP ===")

    try:
        for o in get_open_algos():
            cancel_algo(o["algoId"])
            print(f"  cancelled leftover {o.get('orderType')} "
                  f"{o.get('positionSide')} algoId={o['algoId']}")
    except Exception as e:
        print(f"  algo pre-cleanup skipped: {e}")

    for ps, close_side in [("LONG", "sell"), ("SHORT", "buy")]:
        _, qty = get_position(ps)
        if qty > 0:
            exchange.close_position(symbol, close_side, qty)
            print(f"  closed leftover {ps} position: qty={qty}")
        else:
            print(f"  no leftover {ps} position")

    time.sleep(1.0)

    widget   = None
    strategy = None

    # ------------------------------------------------------------------
    # SETUP
    # ------------------------------------------------------------------
    print("\n=== SETUP: Widget + SingleOrderStrategy ===")

    widget_config = {
        "id":       f"test_hedge_multi_tp_{symbol.lower()}",
        "symbol":   symbol,
        "exchange": "binance",
        "market":   "futures",
        "strategy": "single_order",
        "config":   coin_cfg,
    }
    widget   = Widget(config=widget_config, exchange=exchange)
    widget.start()
    strategy = widget.strategy
    print(f"  strategy: {type(strategy).__name__}")

    try:
        # ------------------------------------------------------------------
        # STEP 1: LONG entry
        # ------------------------------------------------------------------
        print("\n=== STEP 1: strategy.execute('buy') — LONG ===")
        strategy.execute("buy")

        # ------------------------------------------------------------------
        # STEP 2: SHORT entry
        # ------------------------------------------------------------------
        print("\n=== STEP 2: strategy.execute('sell') — SHORT ===")
        strategy.execute("sell")

        # ------------------------------------------------------------------
        # STEP 3: VERIFY BOTH POSITIONS OPENED
        # ------------------------------------------------------------------
        print("\n=== STEP 3: VERIFY BOTH POSITIONS ===")
        long_ep,  long_qty  = get_position("LONG")
        short_ep, short_qty = get_position("SHORT")

        print(f"  LONG:  entry_price={long_ep}  qty={long_qty}")
        print(f"  SHORT: entry_price={short_ep}  qty={short_qty}")

        if long_qty == 0:
            print("FAIL: LONG position not opened")
            sys.exit(1)
        if short_qty == 0:
            print("FAIL: SHORT position not opened")
            sys.exit(1)
        print("  PASS: both positions opened")

        # ------------------------------------------------------------------
        # STEP 4: VERIFY SEPARATE STATE IN ORDER MANAGER
        # ------------------------------------------------------------------
        print("\n=== STEP 4: VERIFY TPSL STATE IN ORDER MANAGER ===")
        long_state  = strategy.order_manager.tpsl.get("LONG")
        short_state = strategy.order_manager.tpsl.get("SHORT")

        print(f"  LONG  state: {long_state}")
        print(f"  SHORT state: {short_state}")

        for label, state in [("LONG", long_state), ("SHORT", short_state)]:
            if not state or "tps" not in state:
                print(f"FAIL: multi-TP state missing for {label}")
                sys.exit(1)
            if len(state["tps"]) != 2:
                print(f"FAIL: {label} expected 2 TPs, got {len(state['tps'])}")
                sys.exit(1)
            if not state.get("sl", {}).get("algo_id"):
                print(f"FAIL: {label} SL algo_id missing")
                sys.exit(1)
        print("  PASS: separate state for LONG and SHORT in order_manager")

        # ------------------------------------------------------------------
        # STEP 5: VERIFY ALL ALGO IDS VISIBLE ON EXCHANGE
        # ------------------------------------------------------------------
        print("\n=== STEP 5: VERIFY ALL ORDERS VISIBLE ON EXCHANGE ===")
        open_algos    = get_open_algos()
        open_algo_ids = {o["algoId"] for o in open_algos}

        for label, state in [("LONG", long_state), ("SHORT", short_state)]:
            for i, tp in enumerate(state["tps"]):
                visible = tp["algo_id"] in open_algo_ids
                print(f"  {label} TP[{i}] algoId={tp['algo_id']}  "
                      f"tp_percent={tp['tp_percent']}%  qty={tp['qty']}  "
                      f"visible={visible}")
                if not visible:
                    print(f"FAIL: {label} TP[{i}] not visible on exchange")
                    sys.exit(1)
            sl_aid     = state["sl"]["algo_id"]
            sl_visible = sl_aid in open_algo_ids
            print(f"  {label} SL  algoId={sl_aid}  visible={sl_visible}")
            if not sl_visible:
                print(f"FAIL: {label} SL not visible on exchange")
                sys.exit(1)

        print("  PASS: all algo orders visible on exchange")

        # ------------------------------------------------------------------
        # STEP 6: CANCEL LONG TPSL — VERIFY SHORT STILL INTACT
        # ------------------------------------------------------------------
        print("\n=== STEP 6: CANCEL LONG TPSL — VERIFY SHORT UNAFFECTED ===")
        strategy.order_manager.cancel_tpsl("LONG")
        print("  cancelled LONG TP/SL via cancel_tpsl('LONG')")

        open_algos    = get_open_algos()
        open_algo_ids = {o["algoId"] for o in open_algos}

        # LONG algo-ордера должны исчезнуть
        for i, tp in enumerate(long_state["tps"]):
            still_up = tp["algo_id"] in open_algo_ids
            print(f"  LONG TP[{i}] algoId={tp['algo_id']}  still_visible={still_up}  (expected False)")
            if still_up:
                print(f"FAIL: LONG TP[{i}] still visible after cancel")
                sys.exit(1)

        # SHORT algo-ордера должны остаться
        for i, tp in enumerate(short_state["tps"]):
            visible = tp["algo_id"] in open_algo_ids
            print(f"  SHORT TP[{i}] algoId={tp['algo_id']}  visible={visible}  (expected True)")
            if not visible:
                print(f"FAIL: SHORT TP[{i}] disappeared after LONG cancel")
                sys.exit(1)
        sl_still = short_state["sl"]["algo_id"] in open_algo_ids
        print(f"  SHORT SL algoId={short_state['sl']['algo_id']}  visible={sl_still}  (expected True)")
        if not sl_still:
            print("FAIL: SHORT SL disappeared after LONG cancel")
            sys.exit(1)

        print("  PASS: SHORT state unaffected by LONG cancel")

        # ------------------------------------------------------------------
        # STEP 7: CANCEL SHORT TPSL + CLOSE BOTH POSITIONS
        # ------------------------------------------------------------------
        print("\n=== STEP 7: CANCEL SHORT TPSL + CLOSE BOTH POSITIONS ===")
        strategy.order_manager.cancel_tpsl("SHORT")
        print("  cancelled SHORT TP/SL via cancel_tpsl('SHORT')")

        _, lq = get_position("LONG")
        if lq > 0:
            exchange.close_position(symbol, "sell", lq)
            print(f"  closed LONG position: qty={lq}")

        _, sq = get_position("SHORT")
        if sq > 0:
            exchange.close_position(symbol, "buy", sq)
            print(f"  closed SHORT position: qty={sq}")

        time.sleep(1.0)

        # ------------------------------------------------------------------
        # STEP 8: VERIFY FULL CLEANUP
        # ------------------------------------------------------------------
        print("\n=== STEP 8: VERIFY FULL CLEANUP ===")
        _, lq_final = get_position("LONG")
        _, sq_final = get_position("SHORT")
        remaining   = get_open_algos()

        print(f"  LONG  remaining qty:  {lq_final}")
        print(f"  SHORT remaining qty:  {sq_final}")
        print(f"  open algo orders:     {len(remaining)}")

        if lq_final != 0 or sq_final != 0 or len(remaining) != 0:
            print("FAIL: cleanup incomplete")
            sys.exit(1)
        print("  PASS: full cleanup successful")

    except Exception as e:
        print(f"\nERROR: {e}")
        raise

    finally:
        print("\n=== FINAL CLEANUP ===")
        for ps in ("LONG", "SHORT"):
            if strategy is not None and strategy.order_manager.has_tpsl(ps):
                strategy.order_manager.cancel_tpsl(ps)
                print(f"  cancelled leftover {ps} TP/SL via order_manager")
        try:
            for o in get_open_algos():
                cancel_algo(o["algoId"])
                print(f"  fallback cancelled {o.get('orderType')} "
                      f"{o.get('positionSide')} algoId={o['algoId']}")
        except Exception as e:
            print(f"  fallback cleanup error: {e}")
        for ps, close_side in [("LONG", "sell"), ("SHORT", "buy")]:
            _, qty = get_position(ps)
            if qty > 0:
                exchange.close_position(symbol, close_side, qty)
                print(f"  closed remaining {ps}: qty={qty}")

    print("\n=== RESULTS ===")
    print("  [PASS] LONG position opened")
    print("  [PASS] SHORT position opened")
    print("  [PASS] separate tpsl state for LONG and SHORT")
    print("  [PASS] all algo orders visible on exchange")
    print("  [PASS] cancel LONG did not affect SHORT")
    print("  [PASS] full cleanup successful")
    print("\nTEST DONE")
