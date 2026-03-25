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
    service = GridService(builder, runner, registry, exchange)

    symbol = "ANIMEUSDT"
    base_price = exchange.get_price(symbol)

    print(f"\nMarket price: {base_price}")

    session = None

    try:
        # --- Старт сессии ---
        session = service.start_session(
            symbol=symbol,
            position_side="LONG",
            base_price=base_price,
            levels_count=3,
            step_percent=1,
            base_qty=1200,
        )

        print(f"\n=== SESSION STARTED ===")
        print(f"session_id:  {session.session_id}")
        print(f"status:      {session.status}")
        print("levels:")
        for lvl in session.levels:
            print(f"  [{lvl.index}] price={lvl.price}  status={lvl.status}  order_id={lvl.order_id}")

        # --- Проверка registry до stop ---
        before_stop = service.get_session(symbol, "LONG")
        all_before = service.get_all_sessions()

        print(f"\n=== REGISTRY BEFORE STOP ===")
        print(f"get_session found:  {before_stop is not None}")
        print(f"total sessions:     {len(all_before)}")

        # --- Stop сессии ---
        stopped_session = service.stop_session(symbol, "LONG")

        print(f"\n=== SESSION STOPPED ===")
        print(f"session_id:  {stopped_session.session_id}")
        print(f"status:      {stopped_session.status}")
        print("levels:")
        for lvl in stopped_session.levels:
            print(f"  [{lvl.index}] price={lvl.price}  status={lvl.status}  order_id={lvl.order_id}")

        # --- Проверка registry после stop ---
        after_stop = service.get_session(symbol, "LONG")
        all_after = service.get_all_sessions()

        print(f"\n=== REGISTRY AFTER STOP ===")
        print(f"get_session found:  {after_stop is not None}")
        print(f"total sessions:     {len(all_after)}")

    finally:
        # --- Fallback cleanup ---
        remaining = service.get_session(symbol, "LONG")
        if remaining is not None:
            print("\n=== FALLBACK CLEANUP ===")
            service.stop_session(symbol, "LONG")
            print("  fallback stop_session called")

    print("\nTEST DONE")
