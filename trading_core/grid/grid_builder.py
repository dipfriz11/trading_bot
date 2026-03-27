from typing import List, Optional

from trading_core.grid.grid_models import GridLevel, GridSession


class GridBuilder:

    def _build_grid_prices(
        self,
        first_price: float,
        last_price: float,
        orders_count: int,
        distribution_mode: str,
        distribution_value: float,
    ) -> List[float]:
        if orders_count < 2:
            raise ValueError(f"orders_count must be >= 2, got {orders_count}")

        if first_price <= 0:
            raise ValueError(f"first_price must be > 0, got {first_price}")

        if last_price <= 0:
            raise ValueError(f"last_price must be > 0, got {last_price}")

        if first_price == last_price:
            raise ValueError("first_price and last_price must be different")

        if distribution_value <= 0:
            raise ValueError(
                f"distribution_value must be > 0, got {distribution_value}"
            )

        if distribution_mode not in ("step", "density"):
            raise ValueError(
                f"Unsupported distribution_mode: {distribution_mode!r}"
            )

        prices = []

        for i in range(orders_count):
            t = i / (orders_count - 1)

            if distribution_mode == "step":
                u = t
            else:
                u = t ** (1 / distribution_value)

            price = first_price + (last_price - first_price) * u
            prices.append(price)

        prices[0] = first_price
        prices[-1] = last_price

        return prices

    def build_session(
        self,
        symbol: str,
        position_side: str,
        base_price: float,
        levels_count: int,
        step_percent: float,
        base_qty: float,
        qty_mode: str = "fixed",
        qty_multiplier: float = 1.0,
        orders_count: Optional[int] = None,
        first_price: Optional[float] = None,
        last_price: Optional[float] = None,
        distribution_mode: Optional[str] = None,
        distribution_value: float = 1.0,
    ) -> GridSession:

        session = GridSession(symbol=symbol, position_side=position_side)

        use_new_grid_mode = all(
            value is not None
            for value in (orders_count, first_price, last_price, distribution_mode)
        )

        if use_new_grid_mode:
            prices = self._build_grid_prices(
                first_price, last_price, orders_count, distribution_mode, distribution_value
            )
        else:
            prices = []
            for i in range(levels_count):
                step = base_price * (step_percent / 100) * (i + 1)
                if position_side == "LONG":
                    price = base_price - step
                else:
                    price = base_price + step
                prices.append(price)

        for i, price in enumerate(prices):
            if qty_mode == "fixed":
                qty = base_qty
            elif qty_mode == "multiplier":
                qty = base_qty * (qty_multiplier ** i)
            else:
                raise ValueError(f"Unsupported qty_mode: {qty_mode!r}")

            level = GridLevel(
                index=i + 1,
                price=price,
                qty=qty,
                position_side=position_side,
                status="planned",
            )
            session.levels.append(level)

        return session
