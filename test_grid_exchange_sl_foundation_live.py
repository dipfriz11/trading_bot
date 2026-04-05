import sys
import time

from exchange.binance_exchange import BinanceExchange
from trading_core.grid.grid_builder import GridBuilder
from trading_core.grid.grid_runner import GridRunner
from trading_core.grid.grid_registry import GridRegistry
from trading_core.grid.grid_sizer import GridSizer
from trading_core.grid.grid_service import GridService

SL_PCT = 5.0
TP_PCT = 100.0   # placeholder — unreachable, keeps enable_tpsl happy

if __name__ == "__main__":

    symbol        = "SIRENUSDT"
    position_side = "LONG"

    exchange = BinanceExchange()
    builder  = GridBuilder()
    runner   = GridRunner(exchange)
    registry = GridRegistry()
    sizer    = GridSizer()
    service  = GridService(builder, runner, registry, exchange, sizer)

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------
    def get_open_algos(sym: str) -> list:
        resp = exchange.client.futures_get_open_algo_orders(symbol=sym)
        if isinstance(resp, list):
            return resp
        return resp.get("openAlgoOrders", [])

    # ------------------------------------------------------------------
    # PRE-CLEANUP
    # ------------------------------------------------------------------
    print("\n=== PRE-CLEANUP ===")

    leftover = service.get_session(symbol, position_side)
    if leftover is not None:
        service.stop_session(symbol, position_side)
        print("  stopped leftover LONG grid session")
    else:
        print("  no leftover LONG grid session")

    try:
        open_algos = get_open_algos(symbol)
        cancelled = 0
        for o in open_algos:
            if o.get("positionSide") == position_side:
                exchange.cancel_algo_order(o["algoId"])
                print(f"  cancelled leftover algo {o.get('orderType')} algoId={o['algoId']}")
                cancelled += 1
        if cancelled == 0:
            print("  no leftover algo orders")
    except Exception as e:
        print(f"  algo cleanup skipped: {e}")

    for pos in exchange.get_positions(symbol):
        if pos["positionSide"] == position_side:
            qty = abs(float(pos["positionAmt"]))
            if qty > 0:
                exchange.close_position(symbol, "sell", qty)
                print(f"  closed leftover LONG position: qty={qty}")
            else:
                print("  no open LONG position")
            break

    time.sleep(1.0)

    try:
        # ------------------------------------------------------------------
        # [1] OPEN LONG POSITION
        # ------------------------------------------------------------------
        print("\n=== OPEN LONG POSITION ===")
        t0 = time.time()
        exchange.open_market_position(symbol, "buy", usdt_amount=8.5, leverage=5)
        time.sleep(1.0)

        entry_price = None
        long_qty    = 0.0
        for pos in exchange.get_positions(symbol):
            if pos["positionSide"] == position_side:
                long_qty    = abs(float(pos["positionAmt"]))
                entry_price = float(pos["entryPrice"])
                break

        t_position_opened = time.time()
        print(f"  entry={entry_price}  qty={long_qty}")
        print(f"  [TIMING] position opened in {t_position_opened - t0:.2f}s")

        if long_qty == 0 or entry_price is None:
            print("FAIL: LONG position not opened")
            sys.exit(1)

        # ------------------------------------------------------------------
        # [2] START GRID SESSION
        # ------------------------------------------------------------------
        print("\n=== START GRID SESSION ===")
        t1 = time.time()
        current_price = exchange.get_price(symbol)
        print(f"  current_price={current_price:.8f}")

        session = service.start_session(
            symbol=symbol,
            position_side=position_side,
            total_budget=15.0,
            levels_count=2,
            step_percent=1.0,
            orders_count=2,
            first_price=current_price * 0.950,
            last_price=current_price * 0.920,
            distribution_mode="step",
            distribution_value=1.0,
        )
        t_session_started = time.time()
        print(f"  session_id={session.session_id}")
        for lvl in session.levels:
            print(f"    [{lvl.index}] price={lvl.price:.8f}  qty={lvl.qty}  status={lvl.status}")
        print(f"  [TIMING] session started in {t_session_started - t1:.2f}s")

        # ------------------------------------------------------------------
        # [3+4] ENABLE TPSL
        # ------------------------------------------------------------------
        print("\n=== ENABLE TPSL ===")
        expected_sl_price = entry_price * (1 - SL_PCT / 100)
        print(f"  entry_price={entry_price:.8f}")
        print(f"  expected SL stopPrice={expected_sl_price:.8f}  (entry * {1 - SL_PCT/100:.4f})")

        t2 = time.time()
        service.enable_tpsl(symbol, position_side, sl_percent=SL_PCT, tp_percent=TP_PCT)
        t_tpsl_enabled = time.time()
        print(f"  [TIMING] tpsl enabled in {t_tpsl_enabled - t2:.2f}s")

        stored_algo_id   = service._sl_orders.get((symbol, position_side))
        stored_tpsl_conf = service._tpsl_configs.get((symbol, position_side))
        print(f"  algoId in _sl_orders:  {stored_algo_id}")
        print(f"  _tpsl_configs stored:  {stored_tpsl_conf is not None}")

        # ------------------------------------------------------------------
        # [5+6] VERIFY SL ON EXCHANGE
        # ------------------------------------------------------------------
        print("\n=== VERIFY SL ON EXCHANGE ===")
        t3 = time.time()
        open_algos = get_open_algos(symbol)
        t_sl_detected = time.time()

        sl_algo = None
        for o in open_algos:
            if o.get("algoId") == stored_algo_id:
                sl_algo = o
                break

        if sl_algo is not None:
            exchange_stop_price = float(sl_algo.get("triggerPrice", 0))
            print(f"  SL found on exchange: algoId={sl_algo['algoId']}")
            print(f"  orderType={sl_algo.get('orderType')}  positionSide={sl_algo.get('positionSide')}")
            print(f"  triggerPrice on exchange={exchange_stop_price:.8f}")
            print(f"  [TIMING] SL detected on exchange in {t_sl_detected - t3:.2f}s")
        else:
            print(f"  SL NOT found on exchange for algoId={stored_algo_id}")
            print(f"  open algos for {symbol}: {open_algos}")

        # ------------------------------------------------------------------
        # [7+8] DISABLE TPSL → SL must be cancelled
        # ------------------------------------------------------------------
        print("\n=== WAITING 15s — check SL on exchange now ===")
        for i in range(15, 0, -1):
            print(f"  disabling in {i}s ...", flush=True)
            time.sleep(1.0)

        print("\n=== DISABLE TPSL ===")
        t4 = time.time()
        service.disable_tpsl(symbol, position_side)
        t_sl_cancelled = time.time()
        print(f"  [TIMING] disable_tpsl in {t_sl_cancelled - t4:.2f}s")

        sl_orders_after = service._sl_orders.get((symbol, position_side))

        time.sleep(0.5)
        open_algos_after = get_open_algos(symbol)
        sl_still_open = any(o.get("algoId") == stored_algo_id for o in open_algos_after)

        # ------------------------------------------------------------------
        # CHECKS
        # ------------------------------------------------------------------
        print("\n=== CHECKS ===")
        passed = True

        # [1] position opened
        if long_qty > 0 and entry_price is not None:
            print(f"  PASS [1]: LONG position opened  entry={entry_price:.8f}  qty={long_qty}")
        else:
            print("  FAIL [1]: LONG position not opened")
            passed = False

        # [2] session created
        if session is not None:
            print(f"  PASS [2]: LONG session created  session_id={session.session_id}")
        else:
            print("  FAIL [2]: LONG session not created")
            passed = False

        # [3] _tpsl_configs was written (read before disable_tpsl)
        if stored_tpsl_conf is not None and stored_tpsl_conf.sl_percent == SL_PCT:
            print(f"  PASS [3]: _tpsl_configs stored  sl_percent={stored_tpsl_conf.sl_percent}%")
        else:
            print(f"  FAIL [3]: _tpsl_configs not stored or wrong sl_percent")
            passed = False

        # [4] algoId stored in _sl_orders
        if stored_algo_id is not None:
            print(f"  PASS [4]: _sl_orders stored algoId={stored_algo_id}")
        else:
            print("  FAIL [4]: algoId not stored in _sl_orders")
            passed = False

        # [5] exchange-native SL appeared on Binance
        if sl_algo is not None:
            print(f"  PASS [5]: SL visible on exchange  algoId={stored_algo_id}")
        else:
            print(f"  FAIL [5]: SL not visible on exchange  algoId={stored_algo_id}")
            passed = False

        # [6] triggerPrice matches formula
        if sl_algo is not None:
            exchange_stop_price = float(sl_algo.get("triggerPrice", 0))
            tolerance = entry_price * 0.0005   # 0.05% — tick rounding tolerance
            if abs(exchange_stop_price - expected_sl_price) <= tolerance:
                print(
                    f"  PASS [6]: triggerPrice={exchange_stop_price:.8f}"
                    f"  expected={expected_sl_price:.8f}"
                    f"  diff={abs(exchange_stop_price - expected_sl_price):.8f}"
                )
            else:
                print(
                    f"  FAIL [6]: triggerPrice={exchange_stop_price:.8f}"
                    f"  expected={expected_sl_price:.8f}"
                    f"  diff={abs(exchange_stop_price - expected_sl_price):.8f}"
                )
                passed = False
        else:
            print("  SKIP [6]: cannot check triggerPrice — SL not found on exchange")
            passed = False

        # [7] disable_tpsl cancelled the SL on exchange
        if not sl_still_open:
            print(f"  PASS [7]: SL no longer in open algo orders after disable_tpsl")
        else:
            print(f"  FAIL [7]: SL still visible in open algo orders after disable_tpsl")
            passed = False

        # [8] _sl_orders cleaned up
        if sl_orders_after is None:
            print(f"  PASS [8]: _sl_orders cleared after disable_tpsl")
        else:
            print(f"  FAIL [8]: _sl_orders still has entry after disable_tpsl: {sl_orders_after}")
            passed = False

        if not passed:
            sys.exit(1)

    except Exception as e:
        print(f"\nERROR: {e}")
        raise

    finally:
        print("\n=== FINAL CLEANUP ===")

        try:
            open_algos = get_open_algos(symbol)
            for o in open_algos:
                if o.get("positionSide") == position_side:
                    try:
                        exchange.cancel_algo_order(o["algoId"])
                        print(f"  cancelled algo algoId={o['algoId']}")
                    except Exception as e:
                        print(f"  cancel algo algoId={o['algoId']}: {e}")
        except Exception as e:
            print(f"  algo cleanup error: {e}")

        try:
            leftover = service.get_session(symbol, position_side)
            if leftover is not None:
                service.stop_session(symbol, position_side)
                print("  stopped LONG session")
        except Exception as e:
            print(f"  stop_session error (ignored): {e}")

        for pos in exchange.get_positions(symbol):
            if pos["positionSide"] == position_side:
                qty = abs(float(pos["positionAmt"]))
                if qty > 0:
                    exchange.close_position(symbol, "sell", qty)
                    print(f"  closed LONG position: qty={qty}")
                break

    print("\nTEST DONE")
