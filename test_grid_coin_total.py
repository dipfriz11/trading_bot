from trading_core.grid.grid_sizer import GridSizer
from exchange.binance_exchange import BinanceExchange
from trading_core.grid.grid_builder import GridBuilder
from trading_core.grid.grid_runner import GridRunner
from trading_core.grid.grid_registry import GridRegistry
from trading_core.grid.grid_service import GridService

COIN_TOTAL_CONFIG = {
    "symbol": "ANIMEUSDT",
    "position_side": "LONG",
    "budget_mode": "coin_total",
    "total_budget": 0.0,
    "coin_total": 14000,
    "levels_count": 3,
    "step_percent": 1,
    "qty_mode": "multiplier",
    "qty_multiplier": 2.0,
}

if __name__ == "__main__":

    exchange = BinanceExchange()
    builder = GridBuilder()
    runner = GridRunner(exchange)
    registry = GridRegistry()
    sizer = GridSizer()
    service = GridService(builder, runner, registry, exchange, sizer)

    symbol = COIN_TOTAL_CONFIG["symbol"]
    position_side = COIN_TOTAL_CONFIG["position_side"]

    session = None

    try:
        # --- Старт сессии ---
        session = service.start_session(
            symbol=symbol,
            position_side=position_side,
            total_budget=COIN_TOTAL_CONFIG["total_budget"],
            levels_count=COIN_TOTAL_CONFIG["levels_count"],
            step_percent=COIN_TOTAL_CONFIG["step_percent"],
            qty_mode=COIN_TOTAL_CONFIG["qty_mode"],
            qty_multiplier=COIN_TOTAL_CONFIG["qty_multiplier"],
            budget_mode=COIN_TOTAL_CONFIG["budget_mode"],
            coin_total=COIN_TOTAL_CONFIG["coin_total"],
        )

        print(f"\n=== COIN_TOTAL SESSION STARTED ===")
        print(f"session_id:  {session.session_id}")
        print(f"status:      {session.status}")
        print("levels:")
        for lvl in session.levels:
            print(f"  [{lvl.index}] price={lvl.price}  qty={lvl.qty}  status={lvl.status}  order_id={lvl.order_id}")

        # --- Проверка registry до stop ---
        before_stop = service.get_session(symbol, position_side)
        all_before = service.get_all_sessions()

        print(f"\n=== REGISTRY BEFORE STOP ===")
        print(f"get_session found:  {before_stop is not None}")
        print(f"total sessions:     {len(all_before)}")

        # --- Stop сессии ---
        stopped_session = service.stop_session(symbol, position_side)

        print(f"\n=== SESSION STOPPED ===")
        print(f"session_id:  {stopped_session.session_id}")
        print(f"status:      {stopped_session.status}")
        print("levels:")
        for lvl in stopped_session.levels:
            print(f"  [{lvl.index}] price={lvl.price}  qty={lvl.qty}  status={lvl.status}  order_id={lvl.order_id}")

        # --- Проверка registry после stop ---
        after_stop = service.get_session(symbol, position_side)
        all_after = service.get_all_sessions()

        print(f"\n=== REGISTRY AFTER STOP ===")
        print(f"get_session found:  {after_stop is not None}")
        print(f"total sessions:     {len(all_after)}")

    finally:
        # --- Fallback cleanup ---
        remaining = service.get_session(symbol, position_side)
        if remaining is not None:
            print("\n=== FALLBACK CLEANUP ===")
            service.stop_session(symbol, position_side)
            print("  fallback stop_session called")

    print("\nTEST DONE")
