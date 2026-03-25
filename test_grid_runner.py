from exchange.binance_exchange import BinanceExchange
from trading_core.grid.grid_builder import GridBuilder
from trading_core.grid.grid_runner import GridRunner

if __name__ == "__main__":

    exchange = BinanceExchange()
    builder = GridBuilder()
    runner = GridRunner(exchange)

    symbol = "ANIMEUSDT"
    base_price = exchange.get_price(symbol)

    print(f"\nMarket price: {base_price}")

    long_session = None

    try:
        # --- Строим LONG session ---
        long_session = builder.build_session(
            symbol=symbol,
            position_side="LONG",
            base_price=base_price,
            levels_count=3,
            step_percent=1,
            base_qty=1200,
        )

        print("\n[LONG] Placing grid orders...")
        runner.place_session_orders(long_session)

        # --- Вывод результата ---
        print(f"\n=== LONG SESSION ===")
        print(f"session_id:     {long_session.session_id}")
        print(f"symbol:         {long_session.symbol}")
        print(f"position_side:  {long_session.position_side}")
        print(f"status:         {long_session.status}")
        print("levels:")
        for lvl in long_session.levels:
            print(f"  [{lvl.index}] price={lvl.price}  qty={lvl.qty}  status={lvl.status}")
            print(f"         order_id={lvl.order_id}  client_order_id={lvl.client_order_id}")

    finally:
        # --- Отмена ордеров ---
        print("\n=== Cancelling orders ===")
        if long_session is None:
            print("  session was not created, nothing to cancel")
        else:
            for lvl in long_session.levels:
                if not lvl.order_id:
                    print(f"  [{lvl.index}] no order_id, skipping")
                    continue
                print(f"  [{lvl.index}] Cancelling order_id={lvl.order_id}")
                exchange.cancel_order(symbol, lvl.order_id)
                print(f"  [{lvl.index}] Cancelled")

    print("\nTEST DONE")
