import time

from exchange.binance_exchange import BinanceExchange
from widget.widget import Widget

config = {
    "id": "test_widget",
    "symbol": "ANIMEUSDT",
    "exchange": "binance",
    "market": "futures",

    "strategy": "single_order",

    "margin_type": "cross",
    "position_mode": "hedge",
    "leverage": 1,

    "config": {
        "amount": 1500,
        "distance": 1.5,
        "trailing_entry": True
    }
}

exchange = BinanceExchange()

widget = Widget(config, exchange)

widget.start()

print("\n=== TEST BUY ===")
widget.on_signal("buy")

# даём поработать trailing
time.sleep(40)

print("\n=== TEST SELL ===")
widget.on_signal("sell")

# даём поработать trailing
time.sleep(40)

print("\nTEST DONE")
