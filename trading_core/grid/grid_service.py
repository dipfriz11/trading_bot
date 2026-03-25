from typing import List, Optional

from trading_core.grid.grid_models import GridSession


class GridService:

    def __init__(self, builder, runner, registry, exchange):
        self.builder = builder
        self.runner = runner
        self.registry = registry
        self.exchange = exchange

    def start_session(
        self,
        symbol: str,
        position_side: str,
        base_price: float,
        levels_count: int,
        step_percent: float,
        base_qty: float,
    ) -> GridSession:
        session = self.builder.build_session(
            symbol=symbol,
            position_side=position_side,
            base_price=base_price,
            levels_count=levels_count,
            step_percent=step_percent,
            base_qty=base_qty,
        )
        session = self.runner.place_session_orders(session)
        self.registry.save_session(session)
        return session

    def stop_session(self, symbol: str, position_side: str) -> Optional[GridSession]:
        session = self.registry.get_session(symbol, position_side)
        if session is None:
            return None
        for level in session.levels:
            if level.order_id and level.status == "placed":
                self.exchange.cancel_order(session.symbol, level.order_id)
                level.status = "canceled"
        session.status = "stopped"
        self.registry.remove_session(symbol, position_side)
        return session

    def get_session(self, symbol: str, position_side: str) -> Optional[GridSession]:
        return self.registry.get_session(symbol, position_side)

    def remove_session(self, symbol: str, position_side: str) -> None:
        self.registry.remove_session(symbol, position_side)

    def get_all_sessions(self) -> List[GridSession]:
        return self.registry.get_all_sessions()
