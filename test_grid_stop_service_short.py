from test_grid_config import GRID_CONFIG
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

    symbol = GRID_CONFIG["symbol"]
    position_side = "SHORT"

    session = None

    try:
        # --- Старт сессии ---
        session = service.start_session(
            symbol=symbol,
            position_side=position_side,
            total_budget=GRID_CONFIG["total_budget"],
            levels_count=GRID_CONFIG["levels_count"],
            step_percent=GRID_CONFIG["step_percent"],
            qty_mode=GRID_CONFIG["qty_mode"],
            qty_multiplier=GRID_CONFIG["qty_multiplier"],
            budget_mode=GRID_CONFIG["budget_mode"],
        )

        print(f"\n=== SHORT SESSION STARTED ===")
        print(f"session_id:  {session.session_id}")
        print(f"status:      {session.status}")
        print("levels:")
        for lvl in session.levels:
            print(f"  [{lvl.index}] price={lvl.price}  status={lvl.status}  order_id={lvl.order_id}")

        # --- Проверка registry до stop ---
        before_stop = service.get_session(symbol, "SHORT")
        all_before = service.get_all_sessions()

        print(f"\n=== REGISTRY BEFORE STOP ===")
        print(f"get_session found:  {before_stop is not None}")
        print(f"total sessions:     {len(all_before)}")

        # --- Stop сессии ---
        stopped_session = service.stop_session(symbol, "SHORT")

        print(f"\n=== SHORT SESSION STOPPED ===")
        print(f"session_id:  {stopped_session.session_id}")
        print(f"status:      {stopped_session.status}")
        print("levels:")
        for lvl in stopped_session.levels:
            print(f"  [{lvl.index}] price={lvl.price}  status={lvl.status}  order_id={lvl.order_id}")

        # --- Проверка registry после stop ---
        after_stop = service.get_session(symbol, "SHORT")
        all_after = service.get_all_sessions()

        print(f"\n=== REGISTRY AFTER STOP ===")
        print(f"get_session found:  {after_stop is not None}")
        print(f"total sessions:     {len(all_after)}")

    finally:
        # --- Fallback cleanup ---
        remaining = service.get_session(symbol, "SHORT")
        if remaining is not None:
            print("\n=== FALLBACK CLEANUP ===")
            service.stop_session(symbol, "SHORT")
            print("  fallback stop_session called")

    print("\nTEST DONE")
