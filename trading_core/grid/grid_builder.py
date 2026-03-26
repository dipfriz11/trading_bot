from trading_core.grid.grid_models import GridLevel, GridSession


class GridBuilder:

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
    ) -> GridSession:

        session = GridSession(symbol=symbol, position_side=position_side)

        for i in range(levels_count):
            step = base_price * (step_percent / 100) * (i + 1)

            if position_side == "LONG":
                price = base_price - step
            else:
                price = base_price + step

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
