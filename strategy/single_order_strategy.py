from order.order_manager import OrderManager


class SingleOrderStrategy:

    def __init__(self, widget):
        self.widget = widget
        self.exchange = widget.exchange
        self.config = widget.config
        self.symbol = widget.symbol

        self.order_manager = OrderManager(
            exchange=self.exchange,
            symbol=self.symbol,
            config=self.config
        )

    def execute(self, side: str):
        amount = self.config["amount"]
        distance = self.config["distance"]

        price = self.exchange.get_price(self.symbol)

        if side == "buy":
            target_price = price * (1 - distance / 100)
            order_side = "BUY"
        else:
            target_price = price * (1 + distance / 100)
            order_side = "SELL"

        print(f"[{self.symbol}] placing order | side={order_side} price={target_price}")

        # размещаем ордер через OrderRequest → executor
        from order.order_request import OrderRequest
        request = OrderRequest(
            symbol=self.symbol,
            side=order_side,
            order_type="limit",
            quantity=amount,
            price=target_price,
            params={}
        )
        self.order_manager.place_request(request)

        distance = self.config.get("distance", 1.5)
        self.order_manager.start_trailing_loop(distance)
