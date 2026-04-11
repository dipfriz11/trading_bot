class BaseExchange:
    def get_price(self, symbol: str) -> float:
        raise NotImplementedError

    def get_symbol_info(self, symbol: str) -> dict:
        raise NotImplementedError

    def change_leverage(self, symbol: str, leverage: int):
        raise NotImplementedError

    def place_market_order(self, symbol: str, side: str, quantity: float):
        raise NotImplementedError

    def open_market_position(self, symbol: str, side: str, usdt_amount: float):
        raise NotImplementedError
    
    def open_limit_position(self, symbol: str, side: str, usdt_amount: float, price: float):
        raise NotImplementedError

    def get_positions(self, symbol: str):
        raise NotImplementedError

    def has_open_position(self, symbol: str) -> bool:
        raise NotImplementedError

    def get_funding(self, symbol: str, start_time: int):
        raise NotImplementedError
    
    def calculate_fee(self, order_type: str, notional: float) -> float:
        raise NotImplementedError

    def get_symbol_metadata(self, symbol: str) -> dict:
        raise NotImplementedError

    def round_order_params(self, symbol: str, side: str, quantity: float, price: float) -> tuple:
        raise NotImplementedError

    def normalize_qty(self, symbol: str, qty: float) -> float:
        raise NotImplementedError

    def normalize_price(self, symbol: str, side: str, price: float) -> float:
        raise NotImplementedError

    def close_position(self, symbol: str, side: str, quantity: float) -> dict:
        raise NotImplementedError