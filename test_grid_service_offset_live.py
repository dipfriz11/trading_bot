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
    # VALIDATION: mixed price + offset → ValueError
    # -------------------------------------------------------
    print("=== VALIDATION: mixed price + offset ===")
    try:
        service.start_session(
            symbol=symbol,
            position_side="LONG",
            total_budget=300.0,
            levels_count=5,
            step_percent=1.0,
            qty_mode="fixed",
            orders_count=5,
            first_price=0.00463073,
            first_offset_percent=0.5,
            distribution_mode="step",
            distribution_value=1.0,
        )
        print("  FAIL — expected ValueError, got no exception")
        sys.exit(1)
    except ValueError as e:
        print(f"  PASS — ValueError: {e}")
    except Exception as e:
        print(f"  FAIL — unexpected {type(e).__name__}: {e}")
        sys.exit(1)

    # -------------------------------------------------------
    # VALIDATION: invalid position_side → ValueError
    # -------------------------------------------------------
    print("=== VALIDATION: invalid position_side ===")
    try:
        service.start_session(
            symbol=symbol,
            position_side="BOTH",
            total_budget=300.0,
            levels_count=5,
            step_percent=1.0,
            qty_mode="fixed",
            orders_count=5,
            first_offset_percent=0.5,
            last_offset_percent=1.5,
            distribution_mode="step",
            distribution_value=1.0,
        )
        print("  FAIL — expected ValueError, got no exception")
        sys.exit(1)
    except ValueError as e:
        print(f"  PASS — ValueError: {e}")
    except Exception as e:
        print(f"  FAIL — unexpected {type(e).__name__}: {e}")
        sys.exit(1)

    # -------------------------------------------------------
    # LIVE: LONG offset
    # -------------------------------------------------------
    try:
        long_session = service.start_session(
            symbol=symbol,
            position_side="LONG",
            total_budget=300.0,
            levels_count=5,
            step_percent=1.0,
            qty_mode="fixed",
            orders_count=5,
            first_offset_percent=0.5,
            last_offset_percent=1.5,
            distribution_mode="step",
            distribution_value=1.0,
        )

        print(f"\n=== LONG OFFSET SESSION ===")
        print(f"session_id:     {long_session.session_id}")
        print(f"first_price:    {long_session.levels[0].price}")
        print(f"last_price:     {long_session.levels[-1].price}")
        print("levels:")
        for lvl in long_session.levels:
            print(f"  [{lvl.index}] price={lvl.price}  qty={lvl.qty}  status={lvl.status}  order_id={lvl.order_id}")
        prices = [lvl.price for lvl in long_session.levels]
        qtys = [lvl.qty for lvl in long_session.levels]
        gaps = [abs(prices[i] - prices[i + 1]) for i in range(len(prices) - 1)]
        current_price = exchange.get_price(symbol)
        print(f"\ncurrent market price: {current_price}")
        print(f"prices: {prices}")
        print(f"gaps:   {gaps}")
        print(f"qtys:   {qtys}")

        if not (long_session.levels[0].price < current_price):
            print(f"  FAIL: first_price={long_session.levels[0].price} is not < current_price={current_price}")
            sys.exit(1)
        if not (long_session.levels[-1].price < long_session.levels[0].price):
            print(f"  FAIL: last_price={long_session.levels[-1].price} is not < first_price={long_session.levels[0].price}")
            sys.exit(1)
        print("  PASS: first_price < current_price, last_price < first_price")

        input("\nПроверь LONG ордера на бирже и нажми Enter для cleanup...")

        stopped = service.stop_session(symbol, "LONG")
        print(f"\n=== LONG STOPPED ===")
        print(f"  status: {stopped.status}")
        for lvl in stopped.levels:
            print(f"  [{lvl.index}] status={lvl.status}  order_id={lvl.order_id}")

    except Exception as e:
        print(f"\nLONG ERROR: {e}")

    finally:
        remaining = service.get_session(symbol, "LONG")
        if remaining is not None:
            print("\n=== LONG FALLBACK CLEANUP ===")
            stopped = service.stop_session(symbol, "LONG")
            print(f"  status: {stopped.status}")
            for lvl in stopped.levels:
                print(f"  [{lvl.index}] status={lvl.status}  order_id={lvl.order_id}")

    # -------------------------------------------------------
    # LIVE: SHORT offset
    # -------------------------------------------------------
    try:
        short_session = service.start_session(
            symbol=symbol,
            position_side="SHORT",
            total_budget=300.0,
            levels_count=5,
            step_percent=1.0,
            qty_mode="fixed",
            orders_count=5,
            first_offset_percent=0.5,
            last_offset_percent=1.5,
            distribution_mode="step",
            distribution_value=1.0,
        )

        print(f"\n=== SHORT OFFSET SESSION ===")
        print(f"session_id:     {short_session.session_id}")
        print(f"first_price:    {short_session.levels[0].price}")
        print(f"last_price:     {short_session.levels[-1].price}")
        print("levels:")
        for lvl in short_session.levels:
            print(f"  [{lvl.index}] price={lvl.price}  qty={lvl.qty}  status={lvl.status}  order_id={lvl.order_id}")
        prices = [lvl.price for lvl in short_session.levels]
        qtys = [lvl.qty for lvl in short_session.levels]
        gaps = [abs(prices[i] - prices[i + 1]) for i in range(len(prices) - 1)]
        current_price = exchange.get_price(symbol)
        print(f"\ncurrent market price: {current_price}")
        print(f"prices: {prices}")
        print(f"gaps:   {gaps}")
        print(f"qtys:   {qtys}")

        if not (short_session.levels[0].price > current_price):
            print(f"  FAIL: first_price={short_session.levels[0].price} is not > current_price={current_price}")
            sys.exit(1)
        if not (short_session.levels[-1].price > short_session.levels[0].price):
            print(f"  FAIL: last_price={short_session.levels[-1].price} is not > first_price={short_session.levels[0].price}")
            sys.exit(1)
        print("  PASS: first_price > current_price, last_price > first_price")

        input("\nПроверь SHORT ордера на бирже и нажми Enter для cleanup...")

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
