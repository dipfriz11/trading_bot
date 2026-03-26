from typing import List, Optional

from trading_core.grid.grid_models import GridSession


class GridService:

    def __init__(self, builder, runner, registry, exchange, sizer):
        self.builder = builder
        self.runner = runner
        self.registry = registry
        self.exchange = exchange
        self.sizer = sizer

    def start_session(
        self,
        symbol: str,
        position_side: str,
        total_budget: float,
        levels_count: int,
        step_percent: float,
        qty_mode: str = "fixed",
        qty_multiplier: float = 1.0,
        budget_mode: str = "usdt_total",
        coin_total: float = 0.0,
    ) -> GridSession:
        base_price = self.exchange.get_price(symbol)
        base_qty = self.sizer.calculate_base_qty(
            total_budget, base_price, levels_count, qty_mode, qty_multiplier, budget_mode, coin_total
        )
        session = self.builder.build_session(
            symbol=symbol,
            position_side=position_side,
            base_price=base_price,
            levels_count=levels_count,
            step_percent=step_percent,
            base_qty=base_qty,
            qty_mode=qty_mode,
            qty_multiplier=qty_multiplier,
        )

        metadata = self.exchange.get_symbol_metadata(symbol)
        min_qty = metadata["min_qty"]
        min_notional = metadata["min_notional"]
        for level in session.levels:
            rounded_qty, rounded_price = self.exchange.round_order_params(
                symbol, position_side, level.qty, level.price
            )
            if rounded_qty < min_qty:
                raise ValueError(
                    f"Level {level.index}: rounded_qty={rounded_qty} is below min_qty={min_qty}"
                )
            if rounded_qty * rounded_price < min_notional:
                raise ValueError(
                    f"Level {level.index}: notional={rounded_qty * rounded_price} is below min_notional={min_notional}"
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
