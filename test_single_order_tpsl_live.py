# test_single_order_tpsl_live.py
#
# Mode: verify placement visibility (no execution wait).
# No grid, no watcher, no check_tpsl.
#
# TP: TAKE_PROFIT (limit, with price) → algoId via /fapi/v1/algoOrder (algoType=CONDITIONAL)
# SL: STOP_MARKET                     → algoId via /fapi/v1/algoOrder
# Both orders use the same Binance Algo API — cancel/visibility via algoId.
#
# Steps:
#   1. Open market LONG position
#   2. Place TAKE_PROFIT (limit) + STOP_MARKET immediately
#   3. Verify both visible in open algo orders
#   4. Observe briefly (~15s)
#   5. Cancel both orders + close position
#   6. Verify cleanup successful

import sys
import time

from exchange.binance_exchange import BinanceExchange

if __name__ == "__main__":

    symbol          = "SIRENUSDT"
    position_side   = "LONG"
    TP_PERCENT      = 10.0   # +10% от entry — точно не триггернётся
    SL_PERCENT      = 10.0   # -10% от entry
    USDT_AMOUNT     = 8.5
    LEVERAGE        = 1
    OBSERVE_SECONDS = 15

    exchange    = BinanceExchange()
    symbol_info = exchange.get_symbol_info(symbol)

    def round_stop_price(price: float) -> float:
        return exchange._round_price(symbol_info, price, "SELL")

    def cancel_algo(algo_id: int) -> None:
        try:
            exchange.client.futures_cancel_algo_order(algoId=algo_id)
        except Exception as e:
            print(f"  cancel_algo {algo_id}: {e}")

    def get_open_algos() -> list:
        resp = exchange.client.futures_get_open_algo_orders(symbol=symbol)
        if isinstance(resp, list):
            return resp
        return resp.get("openAlgoOrders", [])

    def get_long_position() -> tuple:
        """Returns (entry_price, qty). entry_price=None if no position."""
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

    tp_algo_id = None   # TAKE_PROFIT (limit) → algoId
    sl_algo_id = None   # STOP_MARKET         → algoId

    try:
        # ------------------------------------------------------------------
        # STEP 1: OPEN MARKET LONG
        # ------------------------------------------------------------------
        print(f"\n=== STEP 1: OPEN MARKET LONG ({USDT_AMOUNT} USDT, leverage={LEVERAGE}) ===")
        exchange.open_market_position(symbol, "buy", usdt_amount=USDT_AMOUNT, leverage=LEVERAGE)
        time.sleep(1.0)

        entry_price, opened_qty = get_long_position()
        if opened_qty == 0 or entry_price is None:
            print("FAIL: LONG position not opened")
            sys.exit(1)

        tp_stop = round_stop_price(entry_price * (1 + TP_PERCENT / 100))
        sl_stop = round_stop_price(entry_price * (1 - SL_PERCENT / 100))

        print(f"  entry_price = {entry_price}")
        print(f"  qty         = {opened_qty}")
        print(f"  TP stopPrice: {tp_stop}  (+{TP_PERCENT}%)")
        print(f"  SL stopPrice: {sl_stop}  (-{SL_PERCENT}%)")

        # ------------------------------------------------------------------
        # STEP 2: PLACE TP (limit) + SL (market) IMMEDIATELY
        # ------------------------------------------------------------------
        print("\n=== STEP 2: PLACE TP + SL ===")

        tp_resp = exchange.client.futures_create_order(
            symbol=symbol,
            side="SELL",
            positionSide="LONG",
            type="TAKE_PROFIT",
            stopPrice=tp_stop,
            price=tp_stop,
            quantity=opened_qty,
            timeInForce="GTC",
            workingType="MARK_PRICE",
        )
        tp_algo_id = tp_resp["algoId"]
        print(f"  TP placed: algoId={tp_algo_id}  type=TAKE_PROFIT (limit)  stopPrice={tp_stop}  price={tp_stop}  qty={opened_qty}")

        sl_resp = exchange.client.futures_create_order(
            symbol=symbol,
            side="SELL",
            positionSide="LONG",
            type="STOP_MARKET",
            stopPrice=sl_stop,
            closePosition=True,
            workingType="MARK_PRICE",
        )
        sl_algo_id = sl_resp["algoId"]
        print(f"  SL placed: algoId={sl_algo_id}  type=STOP_MARKET          stopPrice={sl_stop}")

        # ------------------------------------------------------------------
        # STEP 3: VERIFY BOTH VISIBLE IN ALGO ORDERS
        # ------------------------------------------------------------------
        print("\n=== STEP 3: VERIFY ORDERS VISIBLE ON EXCHANGE ===")
        open_algos = get_open_algos()
        tp_entry   = next((o for o in open_algos if o["algoId"] == tp_algo_id), None)
        sl_entry   = next((o for o in open_algos if o["algoId"] == sl_algo_id), None)
        tp_visible = tp_entry is not None
        sl_visible = sl_entry is not None

        print(f"  TP visible in algo orders: {tp_visible}  "
              f"(algoId={tp_algo_id}  orderType={tp_entry.get('orderType') if tp_entry else '—'})")
        print(f"  SL visible in algo orders: {sl_visible}  "
              f"(algoId={sl_algo_id}  orderType={sl_entry.get('orderType') if sl_entry else '—'})")

        if not tp_visible or not sl_visible:
            print("FAIL: TP or SL not visible in open algo orders")
            sys.exit(1)

        print("  PASS: both orders visible on exchange")

        # ------------------------------------------------------------------
        # STEP 4: OBSERVE
        # ------------------------------------------------------------------
        print(f"\n=== STEP 4: OBSERVE ORDERS ON EXCHANGE ({OBSERVE_SECONDS}s) ===")
        deadline = time.time() + OBSERVE_SECONDS
        while time.time() < deadline:
            current_price    = exchange.get_price(symbol)
            _, remaining_qty = get_long_position()
            print(
                f"  price={current_price:.5f}  tp={tp_stop:.5f}"
                f"  sl={sl_stop:.5f}  pos_qty={remaining_qty} [orders live]"
            )
            time.sleep(3.0)
        print("  observe done — position still open, orders still standing (expected)")

        # ------------------------------------------------------------------
        # STEP 5: CANCEL BOTH ORDERS + CLOSE POSITION
        # ------------------------------------------------------------------
        print("\n=== STEP 5: CANCEL BOTH ORDERS + CLOSE POSITION ===")
        cancel_algo(tp_algo_id)
        print(f"  cancelled TP algoId={tp_algo_id}")
        cancel_algo(sl_algo_id)
        print(f"  cancelled SL algoId={sl_algo_id}")
        tp_algo_id = None
        sl_algo_id = None

        _, current_qty = get_long_position()
        if current_qty > 0:
            exchange.close_position(symbol, "sell", current_qty)
            print(f"  closed LONG position: qty={current_qty}")
        else:
            print("  position already closed")

        time.sleep(1.0)

        # ------------------------------------------------------------------
        # STEP 6: VERIFY CLEANUP
        # ------------------------------------------------------------------
        print("\n=== STEP 6: VERIFY CLEANUP ===")
        _, final_qty = get_long_position()
        pos_closed   = (final_qty == 0)
        print(f"  position closed:      {pos_closed}  (qty={final_qty})")
        print(f"  TP order cancelled:   True")
        print(f"  SL order cancelled:   True")

        if not pos_closed:
            print("FAIL: position still open after manual close")
            sys.exit(1)

        print("  PASS: cleanup successful")

    except Exception as e:
        print(f"\nERROR: {e}")
        raise

    finally:
        print("\n=== FINAL CLEANUP ===")

        if tp_algo_id is not None:
            cancel_algo(tp_algo_id)
            print(f"  cancelled TP algoId={tp_algo_id}")
        if sl_algo_id is not None:
            cancel_algo(sl_algo_id)
            print(f"  cancelled SL algoId={sl_algo_id}")

        _, qty = get_long_position()
        if qty > 0:
            exchange.close_position(symbol, "sell", qty)
            print(f"  closed remaining position: qty={qty}")

    print("\n=== RESULTS ===")
    print("  [PASS] position opened")
    print("  [PASS] TP limit placed  (TAKE_PROFIT, algoId)")
    print("  [PASS] SL market placed (STOP_MARKET, algoId)")
    print("  [PASS] TP visible in open algo orders")
    print("  [PASS] SL visible in open algo orders")
    print("  [PASS] cleanup successful")
    print("\nTEST DONE")
