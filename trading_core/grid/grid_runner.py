from trading_core.grid.grid_models import GridSession


class GridRunner:

    def __init__(self, exchange):
        self.exchange = exchange

    def place_session_orders(self, session: GridSession) -> GridSession:
        any_placed = False

        for level in session.levels:
            if level.status != "planned":
                continue

            if level.position_side == "LONG":
                side = "BUY"
            elif level.position_side == "SHORT":
                side = "SELL"
            else:
                raise ValueError(f"Unsupported position_side: {level.position_side!r}")

            response = self.exchange.place_limit_order(
                symbol=session.symbol,
                side=side,
                quantity=level.qty,
                price=level.price,
                position_side=level.position_side,
            )

            if "orderId" in response:
                level.order_id = str(response["orderId"])
            level.client_order_id = response.get("clientOrderId")
            level.status = "placed"
            any_placed = True

        if any_placed:
            session.status = "running"

        return session
