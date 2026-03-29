import time

from exchange.binance_exchange import BinanceExchange
from widget.widget import Widget
from trading_core.market_data.market_data_service import MarketDataService

config = {
    "id": "test_widget_hedge",
    "symbol": "PLAYUSDT",
    "exchange": "binance",
    "market": "futures",

    "strategy": "single_order",

    "margin_type": "cross",
    "position_mode": "hedge",
    "leverage": 1,

    "config": {
        "amount": 150,
        "distance": 1.5,
        "trailing_entry": True
    }
}

exchange = BinanceExchange()
market_data = MarketDataService(exchange.client)

widget = Widget(config, exchange)
widget.market_data = market_data

widget.start()

try:
    print("\n=== TEST BUY (LONG leg) ===")
    widget.on_signal("buy")

    # даём LONG trailing поработать
    time.sleep(5)

    print("\n=== TEST SELL (SHORT leg — LONG must stay alive) ===")
    widget.on_signal("sell")

    # обе ноги трейлятся одновременно
    time.sleep(40)

    print("\n=== WIDGET STOP ===")
    widget.stop()
    time.sleep(3)
    print("=== POST-STOP (no trailing lines expected below) ===")
    time.sleep(5)

finally:
    market_data.stop()
