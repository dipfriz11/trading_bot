import sys
import time

from exchange.binance_exchange import BinanceExchange
from trading_core.grid.grid_builder import GridBuilder
from trading_core.grid.grid_runner import GridRunner
from trading_core.grid.grid_registry import GridRegistry
from trading_core.grid.grid_sizer import GridSizer
from trading_core.grid.grid_service import GridService

if __name__ == "__main__":

    symbol        = "SIRENUSDT"
    position_side = "SHORT"

    exchange = BinanceExchange()
    builder  = GridBuilder()
    runner   = GridRunner(exchange)
    registry = GridRegistry()
    sizer    = GridSizer()
    service  = GridService(builder, runner, registry, exchange, sizer)

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

    for pos in exchange.get_positions(symbol):
        if pos["positionSide"] == position_side:
            qty = abs(float(pos["positionAmt"]))
            if qty > 0:
                exchange.close_position(symbol, "buy", qty)
                print(f"  closed leftover SHORT position: qty={qty}")
            else:
                print("  no open SHORT position")
            break

    time.sleep(1.0)

    try:
        # ------------------------------------------------------------------
        # OPEN MARKET SHORT (~8.5 USDT)
        # ------------------------------------------------------------------
        print("\n=== OPEN MARKET SHORT (~8.5 USDT) ===")
        exchange.open_market_position(symbol, "sell", usdt_amount=8.5, leverage=1)
        time.sleep(1.0)

        entry_price = None
        opened_qty  = 0.0
        for pos in exchange.get_positions(symbol):
            if pos["positionSide"] == position_side:
                entry_price = float(pos["entryPrice"])
                opened_qty  = abs(float(pos["positionAmt"]))
                break

        if opened_qty == 0 or entry_price is None:
            print("FAIL: SHORT position not opened")
            sys.exit(1)

        print(f"  entry_price={entry_price}  qty={opened_qty}")

        # ------------------------------------------------------------------
        # START GRID SESSION (levels above market, won't fill)
        # ------------------------------------------------------------------
        current_price = exchange.get_price(symbol)
        first_price   = current_price * 1.050   # +5% above market
        last_price    = current_price * 1.080   # +8% above market

        print(f"\n=== START SHORT GRID SESSION ===")
        print(f"  current_price={current_price:.8f}")
        print(f"  level[1] first_price={first_price:.8f}  (+5% above, pending)")
        print(f"  level[2] last_price={last_price:.8f}   (+8% above, pending)")

        session = service.start_session(
            symbol=symbol,
            position_side=position_side,
            total_budget=24.0,
            levels_count=3,
            step_percent=1.0,
            orders_count=3,
            first_price=first_price,
            last_price=last_price,
            distribution_mode="step",
            distribution_value=1.0,
        )
        print(f"  session_id: {session.session_id}")
        for lvl in session.levels:
            print(f"  [{lvl.index}] price={lvl.price:.8f}  qty={lvl.qty}  status={lvl.status}")

        # ------------------------------------------------------------------
        # PLACE GRID TP ORDERS
        # TP1: -1.0% от entry, закрывает 50% позиции
        # TP2: -2.0% от entry, закрывает оставшиеся 50%
        # Оба ордера ниже рынка -> биржа примет как pending BUY limit
        # ------------------------------------------------------------------
        take_profits = [
            {"tp_percent": 1.0, "close_percent": 50},
            {"tp_percent": 2.0, "close_percent": 50},
        ]

        tp1_price = entry_price * (1 - 0.010)
        tp2_price = entry_price * (1 - 0.020)
        print(f"\n=== PLACE GRID TP ORDERS ===")
        print(f"  position: entry={entry_price}  qty={opened_qty}")
        print(f"  TP1: -1.0%  target={tp1_price:.8f}  close=50%")
        print(f"  TP2: -2.0%  target={tp2_price:.8f}  close=50%")

        service.place_grid_tp_orders(
            symbol=symbol,
            position_side=position_side,
            take_profits=take_profits,
        )

        # ------------------------------------------------------------------
        # CHECKS
        # ------------------------------------------------------------------
        print("\n=== CHECKS ===")
        passed = True

        # [1] state в GridService заполнен
        tp_state = service._grid_tp_orders.get((symbol, position_side), [])
        if len(tp_state) == len(take_profits):
            print(f"  PASS: _grid_tp_orders has {len(tp_state)} entries")
        else:
            print(f"  FAIL: _grid_tp_orders has {len(tp_state)}, expected {len(take_profits)}")
            passed = False

        # [2] цены соответствуют SHORT формуле: entry * (1 - tp_pct/100)
        for i, tp in enumerate(tp_state):
            tp_pct   = tp["tp_percent"]
            expected = entry_price * (1 - tp_pct / 100)
            diff_pct = abs(tp["price"] - expected) / expected * 100
            if diff_pct < 0.01:
                print(f"  PASS: TP[{i}] price={tp['price']:.8f}  expected={expected:.8f}  tp_percent={tp_pct}%")
            else:
                print(f"  FAIL: TP[{i}] price={tp['price']:.8f}  expected={expected:.8f}  diff={diff_pct:.4f}%")
                passed = False

        # [3] каждый TP ордер виден на бирже как NEW
        for i, tp in enumerate(tp_state):
            order_id = tp["order_id"]
            try:
                order     = exchange.get_order(symbol, order_id)
                ex_status = order.get("status")
                if ex_status == "NEW":
                    print(
                        f"  PASS: TP[{i}] order_id={order_id}"
                        f"  exchange_status={ex_status}"
                        f"  price={tp['price']:.8f}  qty={tp['qty']}"
                    )
                else:
                    print(
                        f"  FAIL: TP[{i}] order_id={order_id}"
                        f"  unexpected exchange_status={ex_status}"
                    )
                    passed = False
            except Exception as e:
                print(f"  FAIL: TP[{i}] get_order error: {e}")
                passed = False

        # [4] session живая
        current_session = service.get_session(symbol, position_side)
        if current_session is not None:
            print(f"  PASS: session still alive (session_id={current_session.session_id})")
        else:
            print("  FAIL: session gone after place_grid_tp_orders")
            passed = False

        if not passed:
            sys.exit(1)

    except Exception as e:
        print(f"\nERROR: {e}")
        raise

    finally:
        print("\n=== FINAL CLEANUP ===")

        tp_state = service._grid_tp_orders.get((symbol, position_side), [])
        for tp in tp_state:
            try:
                exchange.cancel_order(symbol, tp["order_id"])
                print(f"  cancelled TP order_id={tp['order_id']}")
            except Exception as e:
                print(f"  cancel TP order_id={tp['order_id']} error: {e}")
        service._grid_tp_orders.pop((symbol, position_side), None)

        leftover = service.get_session(symbol, position_side)
        if leftover is not None:
            service.stop_session(symbol, position_side)
            print("  stopped session")

        for pos in exchange.get_positions(symbol):
            if pos["positionSide"] == position_side:
                qty = abs(float(pos["positionAmt"]))
                if qty > 0:
                    exchange.close_position(symbol, "buy", qty)
                    print(f"  closed position: qty={qty}")
                break

    print("\nTEST DONE")
