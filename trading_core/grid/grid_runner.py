from typing import List

from trading_core.grid.grid_models import GridLevel, GridSession


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

            level.qty   = self.exchange.normalize_qty(session.symbol, level.qty)
            level.price = self.exchange.normalize_price(session.symbol, side, level.price)

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

    def modify_session_orders(self, session: GridSession, new_levels: List[GridLevel]) -> GridSession:
        if len(session.levels) != len(new_levels):
            raise ValueError(
                f"levels count mismatch: session has {len(session.levels)}, new_levels has {len(new_levels)}"
            )

        for level, new_level in zip(session.levels, new_levels):
            if level.status != "placed":
                continue

            if not level.order_id:
                raise ValueError(
                    f"Level {level.index}: status='placed' but order_id is missing"
                )

            if level.position_side == "LONG":
                side = "BUY"
            elif level.position_side == "SHORT":
                side = "SELL"
            else:
                raise ValueError(f"Unsupported position_side: {level.position_side!r}")

            try:
                response = self.exchange.modify_order(
                    symbol=session.symbol,
                    order_id=int(level.order_id),
                    side=side,
                    quantity=new_level.qty,
                    price=new_level.price,
                    position_side=level.position_side,
                )
                level.price = new_level.price
                level.qty = new_level.qty
                level.client_order_id = response.get("clientOrderId", level.client_order_id)
            except Exception as _e:
                print(f"[GridRunner] modify_session_orders: level[{level.index}] modify_order error (reconcile next tick): {_e}")

        return session
