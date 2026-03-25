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
    ) -> GridSession:

        session = GridSession(symbol=symbol, position_side=position_side)

        for i in range(levels_count):
            step = base_price * (step_percent / 100) * (i + 1)

            if position_side == "LONG":
                price = base_price - step
            else:
                price = base_price + step

            level = GridLevel(
                index=i + 1,
                price=price,
                qty=base_qty,
                position_side=position_side,
                status="planned",
            )
            session.levels.append(level)

        return session
