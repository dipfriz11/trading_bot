import sys
import time

from exchange.binance_exchange import BinanceExchange
from trading_core.grid.grid_builder import GridBuilder
from trading_core.grid.grid_runner import GridRunner
from trading_core.grid.grid_registry import GridRegistry
from trading_core.grid.grid_sizer import GridSizer
from trading_core.grid.grid_service import GridService

# NOTE: watcher и check_tpsl не используются.
# TP/SL — биржевые TAKE_PROFIT_MARKET / STOP_MARKET через Binance Algo Order API.
# python-binance роутит эти типы в /fapi/v1/algoOrder → возвращает algoId.

if __name__ == "__main__":

    symbol        = "SIRENUSDT"
    position_side = "LONG"
    TP_PERCENT    = 2.0   # +2.0% от entry — видно на бирже, не триггерится сразу
    SL_PERCENT    = 2.0   # -2.0% от entry

    exchange = BinanceExchange()
    builder  = GridBuilder()
    runner   = GridRunner(exchange)
    registry = GridRegistry()
    sizer    = GridSizer()
    service  = GridService(builder, runner, registry, exchange, sizer)

    symbol_info = exchange.get_symbol_info(symbol)

    def round_stop_price(price: float) -> float:
        return exchange._round_price(symbol_info, price, "SELL")

    def cancel_algo(algo_id: int) -> None:
        exchange.client.futures_cancel_algo_order(algoId=algo_id)

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
        print("  stopped leftover grid session")
    else:
        print("  no leftover grid session")

    try:
        open_algos = get_open_algos(symbol)
        cancelled = 0
        for o in open_algos:
            if o.get("positionSide") == position_side:
                cancel_algo(o["algoId"])
                print(f"  cancelled leftover algo {o.get('orderType')} algoId={o['algoId']}")
                cancelled += 1
        if cancelled == 0:
            print("  no leftover algo TP/SL orders")
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

    tp_algo_id = None
    sl_algo_id = None

    try:
        # ------------------------------------------------------------------
        # OPEN MARKET LONG (~8.5 USDT)
        # ------------------------------------------------------------------
        print("\n=== OPEN MARKET LONG (~8.5 USDT) ===")
        exchange.open_market_position(symbol, "buy", usdt_amount=8.5, leverage=1)
        time.sleep(1.0)

        entry_price = None
        opened_qty  = 0.0
        for pos in exchange.get_positions(symbol):
            if pos["positionSide"] == position_side:
                entry_price = float(pos["entryPrice"])
                opened_qty  = abs(float(pos["positionAmt"]))
                break

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
        # PLACE TP + SL IMMEDIATELY — до сетки, позиция защищена первой
        # ------------------------------------------------------------------
        print("\n=== PLACE TP + SL ORDERS ON EXCHANGE (Algo API) ===")

        tp_resp = exchange.client.futures_create_order(
            symbol=symbol,
            side="SELL",
            positionSide="LONG",
            type="TAKE_PROFIT_MARKET",
            stopPrice=tp_stop,
            closePosition=True,
            workingType="MARK_PRICE",
        )
        tp_algo_id = tp_resp["algoId"]
        print(f"  TP placed: algoId={tp_algo_id}  type=TAKE_PROFIT_MARKET  stopPrice={tp_stop}")

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
        print(f"  SL placed: algoId={sl_algo_id}  type=STOP_MARKET  stopPrice={sl_stop}")

        # проверяем видимость через futures_get_open_algo_orders
        open_algos = get_open_algos(symbol)
        tp_visible  = any(o["algoId"] == tp_algo_id for o in open_algos)
        sl_visible  = any(o["algoId"] == sl_algo_id for o in open_algos)
        print(f"\n  TP visible in open algo orders: {tp_visible}")
        print(f"  SL visible in open algo orders: {sl_visible}")

        if not tp_visible or not sl_visible:
            print("FAIL: TP или SL не видны в открытых algo-ордерах")
            sys.exit(1)

        print("  PASS: оба ордера видны на бирже")

        # ------------------------------------------------------------------
        # START LONG GRID SESSION — после того как защита уже стоит
        # ------------------------------------------------------------------
        print("\n=== START LONG GRID SESSION ===")
        session = service.start_session(
            symbol=symbol,
            position_side=position_side,
            total_budget=24.0,
            levels_count=3,
            step_percent=1.0,
            qty_mode="fixed",
            orders_count=3,
            first_offset_percent=2.0,
            last_offset_percent=4.0,
            distribution_mode="step",
            distribution_value=1.0,
        )
        print(f"  session_id: {session.session_id}")
        for lvl in session.levels:
            print(f"  [{lvl.index}] price={lvl.price:.5f}  qty={lvl.qty}  status={lvl.status}")

        # ------------------------------------------------------------------
        # WAIT: естественное исполнение TP (до 120s)
        # признак: positionAmt == 0
        # ------------------------------------------------------------------
        print(f"\n=== ОЖИДАЕМ ИСПОЛНЕНИЯ TP (до 120s) ===")
        print(f"  mark price должен достичь: {tp_stop}")

        deadline = time.time() + 120
        executed = False

        while time.time() < deadline:
            current_price = exchange.get_price(symbol)
            remaining_qty = 0.0
            for pos in exchange.get_positions(symbol):
                if pos["positionSide"] == position_side:
                    remaining_qty = abs(float(pos["positionAmt"]))
                    break
            print(f"  price={current_price:.5f}  tp_stop={tp_stop:.5f}  "
                  f"diff={current_price - tp_stop:+.5f}  pos_qty={remaining_qty}")
            if remaining_qty == 0:
                executed = True
                service.stop_session(symbol, position_side)
                print("  grid session stopped after TP fill")
                try:
                    cancel_algo(sl_algo_id)
                    sl_algo_id = None
                    print("  SL algo order cancelled")
                except Exception as e:
                    print(f"  SL cancel: {e}")
                break
            time.sleep(3.0)

        # ------------------------------------------------------------------
        # CHECKS
        # ------------------------------------------------------------------
        print("\n=== CHECKS ===")
        passed = True

        if executed:
            print("  PASS: TP исполнен биржей — позиция закрыта algo-ордером")
        else:
            print("  FAIL: TP не исполнен за 120s")
            passed = False

        if service.get_session(symbol, position_side) is None:
            print("  PASS: grid session остановлена после TP fill")
        else:
            print("  FAIL: grid session не остановлена после TP fill")
            passed = False

        if not passed:
            sys.exit(1)

    except Exception as e:
        print(f"\nERROR: {e}")
        raise

    finally:
        print("\n=== FINAL CLEANUP ===")

        for aid, label in [(tp_algo_id, "TP"), (sl_algo_id, "SL")]:
            if aid is not None:
                try:
                    cancel_algo(aid)
                    print(f"  cancelled {label} algoId={aid}")
                except Exception as e:
                    print(f"  cancel {label} algoId={aid}: {e}")

        leftover = service.get_session(symbol, position_side)
        if leftover is not None:
            service.stop_session(symbol, position_side)
            print("  stopped grid session in cleanup")

        for pos in exchange.get_positions(symbol):
            if pos["positionSide"] == position_side:
                qty = abs(float(pos["positionAmt"]))
                if qty > 0:
                    exchange.close_position(symbol, "sell", qty)
                    print(f"  closed position in cleanup: qty={qty}")
                break

    print("\nTEST DONE")
