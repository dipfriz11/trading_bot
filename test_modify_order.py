import time

from exchange.binance_exchange import BinanceExchange
from order.order_manager import OrderManager

exchange = BinanceExchange()

config = {
    "trailing_entry": True   # нужен True, чтобы update_order не выходил сразу
}

manager = OrderManager(
    exchange=exchange,
    symbol="ANIMEUSDT",
    config=config
)

# --- Шаг 1: размещаем ордер ---
current_price = exchange.get_price("ANIMEUSDT")
entry_price = current_price * (1 - 1.5 / 100)   # -1.5% от рынка

print(f"Market price:  {current_price}")
print(f"Entry price:   {entry_price}")

manager.place_order(
    side="BUY",
    price=entry_price,
    quantity=1500
)

print(f"Order placed. order_id={manager.order_id}, price={manager.current_price}")

# --- Шаг 2: серия модификаций (5 раз) ---
print("\nStarting trailing test...")

for i in range(5):
    new_price = manager.current_price * 0.995

    print(f"\n[{i+1}/5] Updating order to new_price={new_price}")

    manager.update_order(new_price)

    print(f"After modify: order_id={manager.order_id}, price={manager.current_price}")

    time.sleep(2)   # пауза чтобы видеть движение на бирже

print("TEST DONE")

# --- Шаг 3: отмена ордера ---
try:
    if manager.order_id:
        print(f"\nCancelling order {manager.order_id}...")
        exchange.cancel_order("ANIMEUSDT", manager.order_id)
        print(f"Order cancelled: {manager.order_id}")
    else:
        print("No active order to cancel")
except Exception as e:
    print(f"Cancel failed: {e}")
