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
    service = GridService(builder, runner, registry)

    symbol = "ANIMEUSDT"
    base_price = exchange.get_price(symbol)

    print(f"\nMarket price: {base_price}")

    session = None

    try:
        # --- Запуск сессии через GridService ---
        session = service.start_session(
            symbol=symbol,
            position_side="LONG",
            base_price=base_price,
            levels_count=3,
            step_percent=1,
            base_qty=1200,
        )

        # --- Вывод результата ---
        print(f"\n=== LONG SESSION ===")
        print(f"session_id:     {session.session_id}")
        print(f"symbol:         {session.symbol}")
        print(f"position_side:  {session.position_side}")
        print(f"status:         {session.status}")
        print("levels:")
        for lvl in session.levels:
            print(f"  [{lvl.index}] price={lvl.price}  qty={lvl.qty}  status={lvl.status}")
            print(f"         order_id={lvl.order_id}  client_order_id={lvl.client_order_id}")

        # --- Проверка registry ---
        fetched = service.get_session(symbol, "LONG")
        all_sessions = service.get_all_sessions()

        print(f"\n=== REGISTRY CHECK ===")
        print(f"get_session found:      {fetched is not None}")
        print(f"fetched session_id:     {fetched.session_id if fetched else None}")
        print(f"total sessions:         {len(all_sessions)}")

    finally:
        # --- Отмена ордеров ---
        print("\n=== Cancelling orders ===")
        if session is None:
            print("  session was not created, nothing to cancel")
        else:
            for lvl in session.levels:
                if not lvl.order_id:
                    print(f"  [{lvl.index}] no order_id, skipping")
                    continue
                print(f"  [{lvl.index}] Cancelling order_id={lvl.order_id}")
                exchange.cancel_order(symbol, lvl.order_id)
                print(f"  [{lvl.index}] Cancelled")

    print("\nTEST DONE")
