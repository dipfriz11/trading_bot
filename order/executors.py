from order.order_request import OrderRequest


class MarketExecutor:
    """Тонкий прокси для market-ордеров."""

    def __init__(self, exchange):
        self.exchange = exchange

    def place(self, request: OrderRequest) -> dict:
        return self.exchange.place_market_order(
            symbol=request.symbol,
            side=request.side,
            quantity=request.quantity,
        )


class LimitExecutor:
    """Тонкий прокси для limit-ордеров."""

    def __init__(self, exchange):
        self.exchange = exchange

    def place(self, request: OrderRequest) -> dict:
        position_side = request.params.get("position_side")
        return self.exchange.place_limit_order(
            symbol=request.symbol,
            side=request.side,
            quantity=request.quantity,
            price=request.price,
            position_side=position_side,
        )

    def modify(self, order_id: int, request: OrderRequest) -> dict:
        position_side = request.params.get("position_side")
        return self.exchange.modify_order(
            symbol=request.symbol,
            order_id=order_id,
            side=request.side,
            quantity=request.quantity,
            price=request.price,
            position_side=position_side,
        )

    def cancel(self, symbol: str, order_id: int) -> dict:
        return self.exchange.cancel_order(symbol, order_id)
