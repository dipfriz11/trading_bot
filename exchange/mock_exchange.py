import random
from .base_exchange import BaseExchange
from logger_config import setup_logger

logger = setup_logger()


class MockExchange(BaseExchange):

    def __init__(self):
        logger.info("MockExchange initialized")

    def get_price(self, symbol: str) -> float:
        # Генерируем случайную цену
        price = round(random.uniform(100, 3000), 2)
        logger.info(f"[MOCK] Price for {symbol}: {price}")
        return price

    def get_symbol_info(self, symbol: str) -> dict:
        # Упрощённые фильтры
        return {
            "filters": [
                {"filterType": "MIN_NOTIONAL", "notional": "5"},
                {"filterType": "LOT_SIZE", "stepSize": "0.001"},
            ]
        }

    def change_leverage(self, symbol: str, leverage: int):
        logger.info(f"[MOCK] Set leverage {leverage} for {symbol}")

    def place_market_order(self, symbol: str, side: str, quantity: float):
        logger.info(f"[MOCK] MARKET ORDER {side.upper()} {symbol} qty={quantity}")
        return {
            "mock": True,
            "symbol": symbol,
            "side": side,
            "quantity": quantity
        }

    def open_market_position(self, symbol: str, side: str, usdt_amount: float):
        logger.info(f"[MOCK] Opening position: {side.upper()} {symbol} for {usdt_amount} USDT")

        price = self.get_price(symbol)
        quantity = round(usdt_amount / price, 6)

        return self.place_market_order(symbol, side, quantity)