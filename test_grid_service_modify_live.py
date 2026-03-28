import sys

from trading_core.grid.grid_sizer import GridSizer
from exchange.binance_exchange import BinanceExchange
from trading_core.grid.grid_builder import GridBuilder
from trading_core.grid.grid_runner import GridRunner
from trading_core.grid.grid_registry import GridRegistry
from trading_core.grid.grid_service import GridService

if __name__ == "__main__":

    exchange = BinanceExchange()
    builder = GridBuilder()
    runner = GridRunner(exchange)
    registry = GridRegistry()
    sizer = GridSizer()
    service = GridService(builder, runner, registry, exchange, sizer)

    symbol = "ANIMEUSDT"

    # -------------------------------------------------------
    # LIVE: LONG modify
    # -------------------------------------------------------
    try:
        # --- START SESSION ---
        session = service.start_session(
            symbol=symbol,
            position_side="LONG",
            total_budget=300.0,
            levels_count=5,
            step_percent=1.0,
            qty_mode="fixed",
            orders_count=5,
            first_offset_percent=2.0,
            last_offset_percent=4.0,
            distribution_mode="step",
            distribution_value=1.0,
        )

        # --- BEFORE MODIFY ---
        current_price = exchange.get_price(symbol)
        order_ids_before = [lvl.order_id for lvl in session.levels]
        prices_before    = [lvl.price for lvl in session.levels]
        qtys_before      = [lvl.qty for lvl in session.levels]
        gaps_before      = [abs(prices_before[i] - prices_before[i + 1]) for i in range(len(prices_before) - 1)]

        print(f"\n=== BEFORE MODIFY ===")
        print(f"session_id:           {session.session_id}")
        print(f"current market price: {current_price}")
        print("levels:")
        for lvl in session.levels:
            print(f"  [{lvl.index}] order_id={lvl.order_id}  price={lvl.price}  qty={lvl.qty}  status={lvl.status}")
        print(f"order_ids_before: {order_ids_before}")
        print(f"prices_before:    {prices_before}")
        print(f"qtys_before:      {qtys_before}")
        print(f"gaps_before:      {gaps_before}")

        input("\nПроверь ордера на бирже ДО modify и нажми Enter...")

        # --- MODIFY SESSION ---
        session = service.modify_session(
            symbol=symbol,
            position_side="LONG",
            total_budget=200.0,
            orders_count=5,
            first_offset_percent=3.0,
            last_offset_percent=5.0,
            distribution_mode="step",
            distribution_value=1.0,
        )

        # --- AFTER MODIFY ---
        order_ids_after = [lvl.order_id for lvl in session.levels]
        prices_after    = [lvl.price for lvl in session.levels]
        qtys_after      = [lvl.qty for lvl in session.levels]
        gaps_after      = [abs(prices_after[i] - prices_after[i + 1]) for i in range(len(prices_after) - 1)]

        print(f"\n=== AFTER MODIFY ===")
        print("levels:")
        for lvl in session.levels:
            print(f"  [{lvl.index}] order_id={lvl.order_id}  price={lvl.price}  qty={lvl.qty}  status={lvl.status}")
        print(f"order_ids_after: {order_ids_after}")
        print(f"prices_after:    {prices_after}")
        print(f"qtys_after:      {qtys_after}")
        print(f"gaps_after:      {gaps_after}")

        # --- CHECKS ---
        print(f"\n=== CHECKS ===")

        if order_ids_before == order_ids_after:
            print(f"  PASS: order_ids preserved")
        else:
            print(f"  FAIL: order_ids changed")
            print(f"    before: {order_ids_before}")
            print(f"    after:  {order_ids_after}")
            sys.exit(1)

        if prices_before != prices_after:
            print(f"  PASS: prices changed")
        else:
            print(f"  FAIL: prices did not change")
            sys.exit(1)

        if qtys_before != qtys_after:
            print(f"  PASS: qtys changed")
        else:
            print(f"  FAIL: qtys did not change")
            sys.exit(1)

        if all(lvl.status == "placed" for lvl in session.levels):
            print(f"  PASS: all levels still placed")
        else:
            for lvl in session.levels:
                if lvl.status != "placed":
                    print(f"  FAIL: level [{lvl.index}] has status={lvl.status!r}")
            sys.exit(1)

        input("\nПроверь ордера на бирже ПОСЛЕ modify и нажми Enter для cleanup...")

        # --- STOP SESSION ---
        stopped = service.stop_session(symbol, "LONG")
        print(f"\n=== STOPPED ===")
        print(f"  status: {stopped.status}")
        for lvl in stopped.levels:
            print(f"  [{lvl.index}] status={lvl.status}  order_id={lvl.order_id}")

    except Exception as e:
        print(f"\nERROR: {e}")

    finally:
        remaining = service.get_session(symbol, "LONG")
        if remaining is not None:
            print("\n=== FALLBACK CLEANUP ===")
            stopped = service.stop_session(symbol, "LONG")
            print(f"  status: {stopped.status}")
            for lvl in stopped.levels:
                print(f"  [{lvl.index}] status={lvl.status}  order_id={lvl.order_id}")

    # -------------------------------------------------------
    # LIVE: SHORT modify
    # -------------------------------------------------------
    try:
        # --- START SESSION ---
        session = service.start_session(
            symbol=symbol,
            position_side="SHORT",
            total_budget=300.0,
            levels_count=5,
            step_percent=1.0,
            qty_mode="fixed",
            orders_count=5,
            first_offset_percent=2.0,
            last_offset_percent=4.0,
            distribution_mode="step",
            distribution_value=1.0,
        )

        # --- BEFORE MODIFY ---
        current_price = exchange.get_price(symbol)
        order_ids_before = [lvl.order_id for lvl in session.levels]
        prices_before    = [lvl.price for lvl in session.levels]
        qtys_before      = [lvl.qty for lvl in session.levels]
        gaps_before      = [abs(prices_before[i] - prices_before[i + 1]) for i in range(len(prices_before) - 1)]

        print(f"\n=== SHORT BEFORE MODIFY ===")
        print(f"session_id:           {session.session_id}")
        print(f"current market price: {current_price}")
        print("levels:")
        for lvl in session.levels:
            print(f"  [{lvl.index}] order_id={lvl.order_id}  price={lvl.price}  qty={lvl.qty}  status={lvl.status}")
        print(f"order_ids_before: {order_ids_before}")
        print(f"prices_before:    {prices_before}")
        print(f"qtys_before:      {qtys_before}")
        print(f"gaps_before:      {gaps_before}")

        input("\nПроверь SHORT ордера на бирже ДО modify и нажми Enter...")

        # --- MODIFY SESSION ---
        session = service.modify_session(
            symbol=symbol,
            position_side="SHORT",
            total_budget=200.0,
            orders_count=5,
            first_offset_percent=3.0,
            last_offset_percent=5.0,
            distribution_mode="step",
            distribution_value=1.0,
        )

        # --- AFTER MODIFY ---
        order_ids_after = [lvl.order_id for lvl in session.levels]
        prices_after    = [lvl.price for lvl in session.levels]
        qtys_after      = [lvl.qty for lvl in session.levels]
        gaps_after      = [abs(prices_after[i] - prices_after[i + 1]) for i in range(len(prices_after) - 1)]

        print(f"\n=== SHORT AFTER MODIFY ===")
        print("levels:")
        for lvl in session.levels:
            print(f"  [{lvl.index}] order_id={lvl.order_id}  price={lvl.price}  qty={lvl.qty}  status={lvl.status}")
        print(f"order_ids_after: {order_ids_after}")
        print(f"prices_after:    {prices_after}")
        print(f"qtys_after:      {qtys_after}")
        print(f"gaps_after:      {gaps_after}")

        # --- CHECKS ---
        print(f"\n=== SHORT CHECKS ===")

        if order_ids_before == order_ids_after:
            print(f"  PASS: order_ids preserved")
        else:
            print(f"  FAIL: order_ids changed")
            print(f"    before: {order_ids_before}")
            print(f"    after:  {order_ids_after}")
            sys.exit(1)

        if prices_before != prices_after:
            print(f"  PASS: prices changed")
        else:
            print(f"  FAIL: prices did not change")
            sys.exit(1)

        if qtys_before != qtys_after:
            print(f"  PASS: qtys changed")
        else:
            print(f"  FAIL: qtys did not change")
            sys.exit(1)

        if all(lvl.status == "placed" for lvl in session.levels):
            print(f"  PASS: all levels still placed")
        else:
            for lvl in session.levels:
                if lvl.status != "placed":
                    print(f"  FAIL: level [{lvl.index}] has status={lvl.status!r}")
            sys.exit(1)

        input("\nПроверь SHORT ордера на бирже ПОСЛЕ modify и нажми Enter для cleanup...")

        # --- STOP SESSION ---
        stopped = service.stop_session(symbol, "SHORT")
        print(f"\n=== SHORT STOPPED ===")
        print(f"  status: {stopped.status}")
        for lvl in stopped.levels:
            print(f"  [{lvl.index}] status={lvl.status}  order_id={lvl.order_id}")

    except Exception as e:
        print(f"\nSHORT ERROR: {e}")

    finally:
        remaining = service.get_session(symbol, "SHORT")
        if remaining is not None:
            print("\n=== SHORT FALLBACK CLEANUP ===")
            stopped = service.stop_session(symbol, "SHORT")
            print(f"  status: {stopped.status}")
            for lvl in stopped.levels:
                print(f"  [{lvl.index}] status={lvl.status}  order_id={lvl.order_id}")

    print("\nTEST DONE")
