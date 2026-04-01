# test_multi_tp_single_live.py
#
# Live test: SingleOrderStrategy market LONG entry, multi-TP + single SL (v1).
# За основу взят test_single_order_strategy_live.py.
#
# Flow: Widget → SingleOrderStrategy.execute("buy")
#         → _execute_market_entry()
#         → on_position_confirmed()
#         → order_manager.place_multi_tpsl()
#
# Verifies:
#   1. LONG position opened
#   2. order_manager.tpsl["LONG"] содержит tps (2 шт.) + sl
#   3. Все algo ids видны на бирже
#   4. Cleanup: cancel_tpsl + close position

import sys
import time

from exchange.binance_exchange import BinanceExchange
from widget.widget import Widget

if __name__ == "__main__":

    symbol        = "SIRENUSDT"
    position_side = "LONG"

    # inline конфиг — не зависит от single_order_config.py
    coin_cfg = {
        "entry_type": "market",
        "leverage":   1,
        "long": {
            "usdt_amount": 8.5,
            "sl_percent":  10.0,   # -10% — точно не триггернётся
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

    def get_long_position() -> tuple:
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
            if o.get("positionSide") == position_side:
                cancel_algo(o["algoId"])
                print(f"  cancelled leftover {o.get('orderType')} algoId={o['algoId']}")
    except Exception as e:
        print(f"  algo pre-cleanup skipped: {e}")

    _, leftover_qty = get_long_position()
    if leftover_qty > 0:
        exchange.close_position(symbol, "sell", leftover_qty)
        print(f"  closed leftover LONG position: qty={leftover_qty}")
    else:
        print("  no leftover LONG position")

    time.sleep(1.0)

    widget   = None
    strategy = None

    # ------------------------------------------------------------------
    # SETUP
    # ------------------------------------------------------------------
    print("\n=== SETUP: Widget + SingleOrderStrategy ===")

    widget_config = {
        "id":       f"test_multi_tp_{symbol.lower()}",
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
        # STEP 1: execute("buy") → market entry + multi-TP/SL
        # ------------------------------------------------------------------
        print("\n=== STEP 1: strategy.execute('buy') ===")
        strategy.execute("buy")

        # ------------------------------------------------------------------
        # STEP 2: VERIFY LONG POSITION OPENED
        # ------------------------------------------------------------------
        print("\n=== STEP 2: VERIFY LONG POSITION ===")
        entry_price, opened_qty = get_long_position()
        if opened_qty == 0:
            print("FAIL: LONG position not opened")
            sys.exit(1)
        print(f"  PASS: entry_price={entry_price}  qty={opened_qty}")

        # ------------------------------------------------------------------
        # STEP 3: VERIFY STATE IN ORDER MANAGER
        # ------------------------------------------------------------------
        print("\n=== STEP 3: VERIFY TPSL STATE IN ORDER MANAGER ===")
        tpsl_state = strategy.order_manager.tpsl.get(position_side)
        print(f"  tpsl_state: {tpsl_state}")

        if not tpsl_state or "tps" not in tpsl_state:
            print("FAIL: multi-TP state not found in order_manager.tpsl")
            sys.exit(1)
        if len(tpsl_state["tps"]) != 2:
            print(f"FAIL: expected 2 TPs, got {len(tpsl_state['tps'])}")
            sys.exit(1)
        if not tpsl_state.get("sl", {}).get("algo_id"):
            print("FAIL: SL algo_id missing in state")
            sys.exit(1)
        print("  PASS: 2 TPs + SL stored in order_manager")

        # ------------------------------------------------------------------
        # STEP 4: VERIFY ALL ALGO IDS VISIBLE ON EXCHANGE
        # ------------------------------------------------------------------
        print("\n=== STEP 4: VERIFY ORDERS VISIBLE ON EXCHANGE ===")
        open_algos    = get_open_algos()
        open_algo_ids = {o["algoId"] for o in open_algos}

        for i, tp in enumerate(tpsl_state["tps"]):
            visible = tp["algo_id"] in open_algo_ids
            print(f"  TP[{i}] algoId={tp['algo_id']}  "
                  f"tp_percent={tp['tp_percent']}%  "
                  f"close_percent={tp['close_percent']}%  "
                  f"qty={tp['qty']}  visible={visible}")
            if not visible:
                print(f"FAIL: TP[{i}] not visible on exchange")
                sys.exit(1)

        sl_aid     = tpsl_state["sl"]["algo_id"]
        sl_visible = sl_aid in open_algo_ids
        print(f"  SL  algoId={sl_aid}  visible={sl_visible}")
        if not sl_visible:
            print("FAIL: SL not visible on exchange")
            sys.exit(1)

        print("  PASS: all orders visible on exchange")

        # ------------------------------------------------------------------
        # STEP 5: CLEANUP
        # ------------------------------------------------------------------
        print("\n=== STEP 5: CLEANUP ===")
        strategy.order_manager.cancel_tpsl(position_side)
        print("  cancelled multi-TP/SL via order_manager.cancel_tpsl()")

        _, current_qty = get_long_position()
        if current_qty > 0:
            exchange.close_position(symbol, "sell", current_qty)
            print(f"  closed LONG position: qty={current_qty}")

        time.sleep(1.0)
        _, final_qty = get_long_position()
        if final_qty != 0:
            print(f"FAIL: position still open, qty={final_qty}")
            sys.exit(1)
        print("  PASS: cleanup successful")

    except Exception as e:
        print(f"\nERROR: {e}")
        raise

    finally:
        print("\n=== FINAL CLEANUP ===")
        if strategy is not None and strategy.order_manager.has_tpsl(position_side):
            strategy.order_manager.cancel_tpsl(position_side)
            print("  cancelled leftover TP/SL via order_manager")
        try:
            for o in get_open_algos():
                if o.get("positionSide") == position_side:
                    cancel_algo(o["algoId"])
                    print(f"  fallback cancelled {o.get('orderType')} algoId={o['algoId']}")
        except Exception as e:
            print(f"  fallback cleanup error: {e}")
        _, qty = get_long_position()
        if qty > 0:
            exchange.close_position(symbol, "sell", qty)
            print(f"  closed remaining position: qty={qty}")

    print("\n=== RESULTS ===")
    print("  [PASS] LONG position opened via strategy.execute('buy')")
    print("  [PASS] 2 x TAKE_PROFIT (limit, algoId) placed")
    print("  [PASS] 1 x STOP_MARKET (algoId) placed")
    print("  [PASS] all orders visible on exchange")
    print("  [PASS] cleanup successful")
    print("\nTEST DONE")
