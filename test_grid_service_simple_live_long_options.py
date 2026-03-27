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
    # 1) LONG / step / fixed
    # -------------------------------------------------------
    try:
        session = service.start_session(
            symbol=symbol,
            position_side="LONG",
            total_budget=300.0,
            levels_count=5,
            step_percent=1.0,
            qty_mode="fixed",
            orders_count=5,
            first_price=0.00463073,
            last_price=0.00453765,
            distribution_mode="step",
            distribution_value=1.0,
        )

        print(f"\n=== SCENARIO 1: LONG / step / fixed ===")
        print(f"session_id:     {session.session_id}")
        print(f"symbol:         {session.symbol}")
        print(f"position_side:  {session.position_side}")
        print(f"current market price: {exchange.get_price(symbol)}")
        print("levels:")
        for lvl in session.levels:
            print(f"  [{lvl.index}] price={lvl.price}  qty={lvl.qty}  status={lvl.status}  order_id={lvl.order_id}")
        prices = [lvl.price for lvl in session.levels]
        qtys = [lvl.qty for lvl in session.levels]
        gaps = [abs(prices[i] - prices[i + 1]) for i in range(len(prices) - 1)]
        print(f"prices: {prices}")
        print(f"gaps:   {gaps}")
        print(f"qtys:   {qtys}")

        input("\nПроверь ордера на бирже и нажми Enter для cleanup...")

        stopped = service.stop_session(symbol, "LONG")
        print(f"  stopped: status={stopped.status}")
        for lvl in stopped.levels:
            print(f"  [{lvl.index}] status={lvl.status}  order_id={lvl.order_id}")

    except Exception as e:
        print(f"\nSCENARIO 1 ERROR: {e}")

    finally:
        remaining = service.get_session(symbol, "LONG")
        if remaining is not None:
            print("\n=== SCENARIO 1 FALLBACK CLEANUP ===")
            stopped = service.stop_session(symbol, "LONG")
            print(f"  status: {stopped.status}")
            for lvl in stopped.levels:
                print(f"  [{lvl.index}] status={lvl.status}  order_id={lvl.order_id}")

    # -------------------------------------------------------
    # 2) LONG / density to end / fixed
    # -------------------------------------------------------
    try:
        session = service.start_session(
            symbol=symbol,
            position_side="LONG",
            total_budget=300.0,
            levels_count=5,
            step_percent=1.0,
            qty_mode="fixed",
            orders_count=5,
            first_price=0.00463073,
            last_price=0.00453765,
            distribution_mode="density",
            distribution_value=2.0,
        )

        print(f"\n=== SCENARIO 2: LONG / density to end / fixed ===")
        print(f"session_id:     {session.session_id}")
        print(f"symbol:         {session.symbol}")
        print(f"position_side:  {session.position_side}")
        print(f"current market price: {exchange.get_price(symbol)}")
        print("levels:")
        for lvl in session.levels:
            print(f"  [{lvl.index}] price={lvl.price}  qty={lvl.qty}  status={lvl.status}  order_id={lvl.order_id}")
        prices = [lvl.price for lvl in session.levels]
        qtys = [lvl.qty for lvl in session.levels]
        gaps = [abs(prices[i] - prices[i + 1]) for i in range(len(prices) - 1)]
        print(f"prices: {prices}")
        print(f"gaps:   {gaps}")
        print(f"qtys:   {qtys}")

        input("\nПроверь ордера на бирже и нажми Enter для cleanup...")

        stopped = service.stop_session(symbol, "LONG")
        print(f"  stopped: status={stopped.status}")
        for lvl in stopped.levels:
            print(f"  [{lvl.index}] status={lvl.status}  order_id={lvl.order_id}")

    except Exception as e:
        print(f"\nSCENARIO 2 ERROR: {e}")

    finally:
        remaining = service.get_session(symbol, "LONG")
        if remaining is not None:
            print("\n=== SCENARIO 2 FALLBACK CLEANUP ===")
            stopped = service.stop_session(symbol, "LONG")
            print(f"  status: {stopped.status}")
            for lvl in stopped.levels:
                print(f"  [{lvl.index}] status={lvl.status}  order_id={lvl.order_id}")

    # -------------------------------------------------------
    # 3) LONG / density to start / fixed
    # -------------------------------------------------------
    try:
        session = service.start_session(
            symbol=symbol,
            position_side="LONG",
            total_budget=300.0,
            levels_count=5,
            step_percent=1.0,
            qty_mode="fixed",
            orders_count=5,
            first_price=0.00463073,
            last_price=0.00453765,
            distribution_mode="density",
            distribution_value=0.5,
        )

        print(f"\n=== SCENARIO 3: LONG / density to start / fixed ===")
        print(f"session_id:     {session.session_id}")
        print(f"symbol:         {session.symbol}")
        print(f"position_side:  {session.position_side}")
        print(f"current market price: {exchange.get_price(symbol)}")
        print("levels:")
        for lvl in session.levels:
            print(f"  [{lvl.index}] price={lvl.price}  qty={lvl.qty}  status={lvl.status}  order_id={lvl.order_id}")
        prices = [lvl.price for lvl in session.levels]
        qtys = [lvl.qty for lvl in session.levels]
        gaps = [abs(prices[i] - prices[i + 1]) for i in range(len(prices) - 1)]
        print(f"prices: {prices}")
        print(f"gaps:   {gaps}")
        print(f"qtys:   {qtys}")

        input("\nПроверь ордера на бирже и нажми Enter для cleanup...")

        stopped = service.stop_session(symbol, "LONG")
        print(f"  stopped: status={stopped.status}")
        for lvl in stopped.levels:
            print(f"  [{lvl.index}] status={lvl.status}  order_id={lvl.order_id}")

    except Exception as e:
        print(f"\nSCENARIO 3 ERROR: {e}")

    finally:
        remaining = service.get_session(symbol, "LONG")
        if remaining is not None:
            print("\n=== SCENARIO 3 FALLBACK CLEANUP ===")
            stopped = service.stop_session(symbol, "LONG")
            print(f"  status: {stopped.status}")
            for lvl in stopped.levels:
                print(f"  [{lvl.index}] status={lvl.status}  order_id={lvl.order_id}")

    # -------------------------------------------------------
    # 4) LONG / step / multiplier
    # -------------------------------------------------------
    try:
        session = service.start_session(
            symbol=symbol,
            position_side="LONG",
            total_budget=300.0,
            levels_count=5,
            step_percent=1.0,
            qty_mode="multiplier",
            qty_multiplier=1.2,
            orders_count=5,
            first_price=0.00463073,
            last_price=0.00453765,
            distribution_mode="step",
            distribution_value=1.0,
        )

        print(f"\n=== SCENARIO 4: LONG / step / multiplier ===")
        print(f"session_id:     {session.session_id}")
        print(f"symbol:         {session.symbol}")
        print(f"position_side:  {session.position_side}")
        print(f"current market price: {exchange.get_price(symbol)}")
        print("levels:")
        for lvl in session.levels:
            print(f"  [{lvl.index}] price={lvl.price}  qty={lvl.qty}  status={lvl.status}  order_id={lvl.order_id}")
        prices = [lvl.price for lvl in session.levels]
        qtys = [lvl.qty for lvl in session.levels]
        gaps = [abs(prices[i] - prices[i + 1]) for i in range(len(prices) - 1)]
        print(f"prices: {prices}")
        print(f"gaps:   {gaps}")
        print(f"qtys:   {qtys}")

        input("\nПроверь ордера на бирже и нажми Enter для cleanup...")

        stopped = service.stop_session(symbol, "LONG")
        print(f"  stopped: status={stopped.status}")
        for lvl in stopped.levels:
            print(f"  [{lvl.index}] status={lvl.status}  order_id={lvl.order_id}")

    except Exception as e:
        print(f"\nSCENARIO 4 ERROR: {e}")

    finally:
        remaining = service.get_session(symbol, "LONG")
        if remaining is not None:
            print("\n=== SCENARIO 4 FALLBACK CLEANUP ===")
            stopped = service.stop_session(symbol, "LONG")
            print(f"  status: {stopped.status}")
            for lvl in stopped.levels:
                print(f"  [{lvl.index}] status={lvl.status}  order_id={lvl.order_id}")

    sys.exit(0)

    print("\nTEST DONE")
