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
    # LONG
    # -------------------------------------------------------
    try:
        long_session = service.start_session(
            symbol=symbol,
            position_side="LONG",
            total_budget=1000.0,
            levels_count=3,
            step_percent=1.0,
            qty_mode="fixed",
            orders_count=3,
            first_price=0.00463073,
            last_price=0.00458419,
            distribution_mode="step",
            distribution_value=1.0,
        )

        print(f"\n=== LONG SESSION ===")
        print(f"session_id:     {long_session.session_id}")
        print(f"symbol:         {long_session.symbol}")
        print(f"position_side:  {long_session.position_side}")
        print(f"first_price:    {long_session.levels[0].price}")
        print(f"last_price:     {long_session.levels[-1].price}")
        print("levels:")
        for lvl in long_session.levels:
            print(f"  [{lvl.index}] price={lvl.price}  qty={lvl.qty}  status={lvl.status}  order_id={lvl.order_id}")

        current_price = exchange.get_price(symbol)
        print(f"\ncurrent market price: {current_price}")

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
    # SHORT
    # -------------------------------------------------------
    try:
        short_session = service.start_session(
            symbol=symbol,
            position_side="SHORT",
            total_budget=1000.0,
            levels_count=3,
            step_percent=1.0,
            qty_mode="fixed",
            orders_count=3,
            first_price=0.00467727,
            last_price=0.00472381,
            distribution_mode="step",
            distribution_value=1.0,
        )

        print(f"\n=== SHORT SESSION ===")
        print(f"session_id:     {short_session.session_id}")
        print(f"symbol:         {short_session.symbol}")
        print(f"position_side:  {short_session.position_side}")
        print(f"first_price:    {short_session.levels[0].price}")
        print(f"last_price:     {short_session.levels[-1].price}")
        print("levels:")
        for lvl in short_session.levels:
            print(f"  [{lvl.index}] price={lvl.price}  qty={lvl.qty}  status={lvl.status}  order_id={lvl.order_id}")

        current_price = exchange.get_price(symbol)
        print(f"\ncurrent market price: {current_price}")

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
