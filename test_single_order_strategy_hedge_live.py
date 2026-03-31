# test_single_order_strategy_hedge_live.py
#
# Live test: independent LONG + SHORT legs in hedge mode.
# Config from single_order_config.py (nested long/short).
#
# Steps:
#   1. execute("buy")  → LONG opened + LONG TP/SL placed
#   2. execute("sell") → SHORT opened + SHORT TP/SL placed
#   3. Verify LONG position
#   4. Verify SHORT position
#   5. Verify LONG TP/SL (TP > entry, SL < entry)
#   6. Verify SHORT TP/SL (TP < entry, SL > entry)
#   7. Verify all 4 algo orders visible on exchange
#   8. Independence: cancel LONG tpsl → SHORT still intact
#   9. Cleanup both legs

import sys
import time

from exchange.binance_exchange import BinanceExchange
from widget.widget import Widget
from single_order_config import SINGLE_ORDER_COINS


if __name__ == "__main__":

    symbol = "SIRENUSDT"

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
            if o.get("positionSide") in ("LONG", "SHORT"):
                cancel_algo(o["algoId"])
                print(f"  cancelled leftover {o.get('positionSide')} "
                      f"{o.get('orderType')} algoId={o['algoId']}")
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

    # ------------------------------------------------------------------
    # SETUP
    # ------------------------------------------------------------------
    print("\n=== SETUP: Widget + SingleOrderStrategy ===")

    coin_cfg = SINGLE_ORDER_COINS[symbol]
    widget_config = {
        "id":       f"test_{symbol.lower()}_hedge",
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

    print(f"  strategy: {type(strategy).__name__}")
    print(f"  long cfg: {coin_cfg.get('long')}")
    print(f"  short cfg: {coin_cfg.get('short')}")

    try:
        # ------------------------------------------------------------------
        # STEP 1: LONG entry
        # ------------------------------------------------------------------
        print("\n=== STEP 1: execute('buy') -> LONG ===")
        strategy.execute("buy")

        # ------------------------------------------------------------------
        # STEP 2: SHORT entry
        # ------------------------------------------------------------------
        print("\n=== STEP 2: execute('sell') -> SHORT ===")
        strategy.execute("sell")

        # ------------------------------------------------------------------
        # STEP 3: VERIFY LONG POSITION
        # ------------------------------------------------------------------
        print("\n=== STEP 3: VERIFY LONG POSITION ===")
        long_entry, long_qty = get_position("LONG")
        print(f"  LONG opened: {long_qty > 0}  entry={long_entry}  qty={long_qty}")
        if long_qty == 0:
            print("FAIL: LONG position not opened")
            sys.exit(1)
        print("  PASS: LONG position opened")

        # ------------------------------------------------------------------
        # STEP 4: VERIFY SHORT POSITION
        # ------------------------------------------------------------------
        print("\n=== STEP 4: VERIFY SHORT POSITION ===")
        short_entry, short_qty = get_position("SHORT")
        print(f"  SHORT opened: {short_qty > 0}  entry={short_entry}  qty={short_qty}")
        if short_qty == 0:
            print("FAIL: SHORT position not opened")
            sys.exit(1)
        print("  PASS: SHORT position opened")

        # ------------------------------------------------------------------
        # STEP 5: VERIFY LONG TP/SL
        # ------------------------------------------------------------------
        print("\n=== STEP 5: VERIFY LONG TP/SL ===")
        long_tpsl  = strategy.order_manager.tpsl.get("LONG")
        long_tp_id = long_tpsl.get("tp_algo_id") if long_tpsl else None
        long_sl_id = long_tpsl.get("sl_algo_id") if long_tpsl else None
        print(f"  LONG tpsl: {long_tpsl}")
        if not long_tp_id or not long_sl_id:
            print("FAIL: LONG TP/SL not in order_manager")
            sys.exit(1)
        print("  PASS: LONG TP/SL stored")

        # ------------------------------------------------------------------
        # STEP 6: VERIFY SHORT TP/SL
        # ------------------------------------------------------------------
        print("\n=== STEP 6: VERIFY SHORT TP/SL ===")
        short_tpsl  = strategy.order_manager.tpsl.get("SHORT")
        short_tp_id = short_tpsl.get("tp_algo_id") if short_tpsl else None
        short_sl_id = short_tpsl.get("sl_algo_id") if short_tpsl else None
        print(f"  SHORT tpsl: {short_tpsl}")
        if not short_tp_id or not short_sl_id:
            print("FAIL: SHORT TP/SL not in order_manager")
            sys.exit(1)
        print("  PASS: SHORT TP/SL stored")

        # ------------------------------------------------------------------
        # STEP 7: VERIFY ALL 4 ORDERS VISIBLE ON EXCHANGE
        # ------------------------------------------------------------------
        print("\n=== STEP 7: VERIFY ALL 4 ORDERS VISIBLE ===")
        open_algos  = get_open_algos()
        all_ids     = {long_tp_id, long_sl_id, short_tp_id, short_sl_id}
        visible_ids = {o["algoId"] for o in open_algos}

        for algo_id, label in [
            (long_tp_id,  "LONG  TP"),
            (long_sl_id,  "LONG  SL"),
            (short_tp_id, "SHORT TP"),
            (short_sl_id, "SHORT SL"),
        ]:
            entry   = next((o for o in open_algos if o["algoId"] == algo_id), None)
            visible = entry is not None
            trigger = float(entry.get("triggerPrice", 0)) if entry else None
            print(f"  {label}: visible={visible}  algoId={algo_id}  "
                  f"orderType={entry.get('orderType') if entry else '—'}  "
                  f"triggerPrice={trigger}")

        if not all_ids.issubset(visible_ids):
            print("FAIL: not all 4 orders visible on exchange")
            sys.exit(1)

        # проверка направления цен
        long_tp_price  = float(next(o for o in open_algos if o["algoId"] == long_tp_id)["triggerPrice"])
        long_sl_price  = float(next(o for o in open_algos if o["algoId"] == long_sl_id)["triggerPrice"])
        short_tp_price = float(next(o for o in open_algos if o["algoId"] == short_tp_id)["triggerPrice"])
        short_sl_price = float(next(o for o in open_algos if o["algoId"] == short_sl_id)["triggerPrice"])

        print(f"\n  LONG  entry={long_entry}  TP={long_tp_price} (>entry: {long_tp_price > long_entry})  "
              f"SL={long_sl_price} (<entry: {long_sl_price < long_entry})")
        print(f"  SHORT entry={short_entry}  TP={short_tp_price} (<entry: {short_tp_price < short_entry})  "
              f"SL={short_sl_price} (>entry: {short_sl_price > short_entry})")

        if not (long_tp_price > long_entry and long_sl_price < long_entry):
            print("FAIL: LONG TP/SL direction incorrect")
            sys.exit(1)
        if not (short_tp_price < short_entry and short_sl_price > short_entry):
            print("FAIL: SHORT TP/SL direction incorrect")
            sys.exit(1)

        print("  PASS: all 4 orders visible, price directions correct")

        # ------------------------------------------------------------------
        # STEP 8: INDEPENDENCE CHECK
        # ------------------------------------------------------------------
        print("\n=== STEP 8: INDEPENDENCE CHECK ===")
        print("  cancelling LONG TP/SL via cancel_tpsl('LONG')...")
        strategy.order_manager.cancel_tpsl("LONG")

        long_gone  = not strategy.order_manager.has_tpsl("LONG")
        short_alive = strategy.order_manager.has_tpsl("SHORT")
        print(f"  LONG  tpsl gone:  {long_gone}")
        print(f"  SHORT tpsl alive: {short_alive}")

        # проверяем на бирже что SHORT ордера ещё висят
        open_algos_after = get_open_algos()
        short_tp_still = any(o["algoId"] == short_tp_id for o in open_algos_after)
        short_sl_still = any(o["algoId"] == short_sl_id for o in open_algos_after)
        print(f"  SHORT TP still on exchange: {short_tp_still}")
        print(f"  SHORT SL still on exchange: {short_sl_still}")

        if not (long_gone and short_alive and short_tp_still and short_sl_still):
            print("FAIL: independence check failed")
            sys.exit(1)

        print("  PASS: cancel LONG tpsl leaves SHORT intact")

        # ------------------------------------------------------------------
        # STEP 9: CLEANUP
        # ------------------------------------------------------------------
        print("\n=== STEP 9: CLEANUP ===")

        strategy.order_manager.cancel_tpsl("SHORT")
        print("  cancelled SHORT TP/SL")

        for ps, close_side in [("LONG", "sell"), ("SHORT", "buy")]:
            _, qty = get_position(ps)
            if qty > 0:
                exchange.close_position(symbol, close_side, qty)
                print(f"  closed {ps} position: qty={qty}")
            else:
                print(f"  {ps} position already closed")

        time.sleep(1.0)

        long_final  = get_position("LONG")[1]
        short_final = get_position("SHORT")[1]
        if long_final == 0 and short_final == 0:
            print("  PASS: both positions closed")
        else:
            print(f"  FAIL: LONG qty={long_final}  SHORT qty={short_final}")
            sys.exit(1)

    except Exception as e:
        print(f"\nERROR: {e}")
        raise

    finally:
        print("\n=== FINAL CLEANUP ===")

        if strategy is not None:
            for ps in ("LONG", "SHORT"):
                if strategy.order_manager.has_tpsl(ps):
                    strategy.order_manager.cancel_tpsl(ps)
                    print(f"  cancelled leftover {ps} TP/SL")

        try:
            for o in get_open_algos():
                if o.get("positionSide") in ("LONG", "SHORT"):
                    cancel_algo(o["algoId"])
                    print(f"  fallback cancelled {o.get('positionSide')} "
                          f"{o.get('orderType')} algoId={o['algoId']}")
        except Exception as e:
            print(f"  fallback cleanup error: {e}")

        for ps, close_side in [("LONG", "sell"), ("SHORT", "buy")]:
            _, qty = get_position(ps)
            if qty > 0:
                exchange.close_position(symbol, close_side, qty)
                print(f"  closed remaining {ps}: qty={qty}")

    print("\n=== RESULTS ===")
    print("  [PASS] LONG opened")
    print("  [PASS] SHORT opened")
    print("  [PASS] LONG TP/SL visible on exchange")
    print("  [PASS] SHORT TP/SL visible on exchange")
    print("  [PASS] cancel LONG tpsl leaves SHORT intact")
    print("  [PASS] cleanup successful")
    print("\nTEST DONE")
