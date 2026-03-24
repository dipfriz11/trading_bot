from exchange.binance_exchange import BinanceExchange
from order.order_manager import OrderManager
from order.order_request import OrderRequest

exchange = BinanceExchange()

config = {
    "trailing_entry": False
}

manager = OrderManager(
    exchange=exchange,
    symbol="ANIMEUSDT",
    config=config
)

price = exchange.get_price("ANIMEUSDT")
print(f"\nMarket price: {price}")

# --- LONG ордер ---
long_price = round(price * (1 - 1.5 / 100), 6)
long_request = OrderRequest(
    symbol="ANIMEUSDT",
    side="BUY",
    order_type="limit",
    quantity=1500,
    price=long_price,
    params={"position_side": "LONG"}
)

print(f"\n[LONG] placing order @ {long_price}")
manager.place_request(long_request)
print(f"[LONG] order_id={manager.orders.get('LONG', {}).get('order_id')}")

# --- SHORT ордер ---
short_price = round(price * (1 + 1.5 / 100), 6)
short_request = OrderRequest(
    symbol="ANIMEUSDT",
    side="SELL",
    order_type="limit",
    quantity=1500,
    price=short_price,
    params={"position_side": "SHORT"}
)

print(f"\n[SHORT] placing order @ {short_price}")
manager.place_request(short_request)
print(f"[SHORT] order_id={manager.orders.get('SHORT', {}).get('order_id')}")

# --- Проверка self.orders ---
print("\n=== self.orders ===")
for ps, entry in manager.orders.items():
    print(f"  {ps}: {entry}")

# --- Отмена обоих ордеров ---
print("\n=== Cancelling orders ===")
for ps, entry in manager.orders.items():
    oid = entry.get("order_id")
    if not oid:
        print(f"  {ps}: no order_id, skipping")
        continue
    print(f"  Cancelling {ps} order_id={oid}")
    exchange.cancel_order("ANIMEUSDT", oid)
    print(f"  Cancelled {ps}")

print("\nTEST DONE")
