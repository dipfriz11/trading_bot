# test_single_order_strategy_live.py
#
# Live test for SingleOrderStrategy market-entry path.
# Config from single_order_config.py — NOT from config.py (hedge path).
#
# Flow: Widget → SingleOrderStrategy.execute("buy")
#         → _execute_market_entry()
#         → on_position_confirmed()
#         → order_manager.place_tpsl()
#
# Verifies:
#   1. LONG position opened
#   2. TP/SL stored in order_manager.tpsl["LONG"]
#   3. Both visible in open algo orders on exchange

import sys
import time

from exchange.binance_exchange import BinanceExchange
from widget.widget import Widget
from single_order_config import SINGLE_ORDER_COINS


if __name__ == "__main__":

    symbol        = "SIRENUSDT"
    position_side = "LONG"

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
            if pos["positionSide"] == "LONG":
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

    # ------------------------------------------------------------------
    # SETUP: Widget + SingleOrderStrategy via single_order_config
    # ------------------------------------------------------------------
    print("\n=== SETUP: Widget + SingleOrderStrategy ===")

    coin_cfg = SINGLE_ORDER_COINS[symbol]
    widget_config = {
        "id":       f"test_{symbol.lower()}",
        "symbol":   symbol,
        "exchange": "binance",
        "market":   "futures",
        "strategy": "single_order",
        "config":   coin_cfg,
    }

    widget   = None
    strategy = None

    widget   = Widget(config=widget_config, exchange=exchange)
    widget.start()
    strategy = widget.strategy

    print(f"  strategy:    {type(strategy).__name__}")
    print(f"  entry_type:  {coin_cfg.get('entry_type')}")
    print(f"  usdt_amount: {coin_cfg.get('usdt_amount')}")
    print(f"  tp_percent:  {coin_cfg.get('tp_percent')}%  "
          f"sl_percent: {coin_cfg.get('sl_percent')}%")

    try:
        # ------------------------------------------------------------------
        # STEP 1: execute("buy") → market entry + TP/SL
        # ------------------------------------------------------------------
        print("\n=== STEP 1: strategy.execute('buy') ===")
        strategy.execute("buy")

        # ------------------------------------------------------------------
        # STEP 2: VERIFY LONG POSITION OPENED
        # ------------------------------------------------------------------
        print("\n=== STEP 2: VERIFY LONG POSITION ===")
        entry_price, opened_qty = get_long_position()
        pos_opened = opened_qty > 0
        print(f"  position opened: {pos_opened}  "
              f"entry_price={entry_price}  qty={opened_qty}")
        if not pos_opened:
            print("FAIL: LONG position not opened")
            sys.exit(1)
        print("  PASS: LONG position opened")

        # ------------------------------------------------------------------
        # STEP 3: VERIFY TP/SL IDS STORED IN ORDER MANAGER
        # ------------------------------------------------------------------
        print("\n=== STEP 3: VERIFY TP/SL IN ORDER MANAGER ===")
        tpsl_state = strategy.order_manager.tpsl.get(position_side)
        tp_algo_id = tpsl_state.get("tp_algo_id") if tpsl_state else None
        sl_algo_id = tpsl_state.get("sl_algo_id") if tpsl_state else None
        print(f"  tpsl state: {tpsl_state}")
        if not tp_algo_id or not sl_algo_id:
            print("FAIL: TP/SL not stored in order_manager.tpsl")
            sys.exit(1)
        print("  PASS: TP/SL IDs stored in order_manager")

        # ------------------------------------------------------------------
        # STEP 4: VERIFY BOTH VISIBLE ON EXCHANGE
        # ------------------------------------------------------------------
        print("\n=== STEP 4: VERIFY ORDERS VISIBLE ON EXCHANGE ===")
        open_algos = get_open_algos()
        tp_entry   = next((o for o in open_algos if o["algoId"] == tp_algo_id), None)
        sl_entry   = next((o for o in open_algos if o["algoId"] == sl_algo_id), None)
        tp_visible = tp_entry is not None
        sl_visible = sl_entry is not None
        print(f"  TP visible: {tp_visible}  "
              f"(algoId={tp_algo_id}  "
              f"orderType={tp_entry.get('orderType') if tp_entry else '—'})")
        print(f"  SL visible: {sl_visible}  "
              f"(algoId={sl_algo_id}  "
              f"orderType={sl_entry.get('orderType') if sl_entry else '—'})")
        if not tp_visible or not sl_visible:
            print("FAIL: TP or SL not visible in open algo orders")
            sys.exit(1)
        print("  PASS: both orders visible on exchange")

        # ------------------------------------------------------------------
        # STEP 5: CLEANUP
        # ------------------------------------------------------------------
        print("\n=== STEP 5: CLEANUP ===")
        strategy.order_manager.cancel_tpsl(position_side)
        print("  cancelled TP/SL via order_manager.cancel_tpsl()")

        _, current_qty = get_long_position()
        if current_qty > 0:
            exchange.close_position(symbol, "sell", current_qty)
            print(f"  closed LONG position: qty={current_qty}")
        else:
            print("  position already closed")

        time.sleep(1.0)
        _, final_qty = get_long_position()
        if final_qty == 0:
            print("  PASS: cleanup successful")
        else:
            print(f"  FAIL: position still open, qty={final_qty}")
            sys.exit(1)

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
    print("  [PASS] TP placed (TAKE_PROFIT limit, algoId)")
    print("  [PASS] SL placed (STOP_MARKET, algoId)")
    print("  [PASS] both orders visible on exchange")
    print("  [PASS] cleanup successful")
    print("\nTEST DONE")
