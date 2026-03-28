from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from trading_core.grid.grid_models import GridSession


@dataclass
class TrailingConfig:
    anchor_price: float
    trailing_step_percent: float
    first_offset_percent: float
    last_offset_percent: float
    total_budget: float
    orders_count: int
    distribution_mode: str
    distribution_value: float
    qty_mode: str
    qty_multiplier: float


class GridService:

    def __init__(self, builder, runner, registry, exchange, sizer):
        self.builder = builder
        self.runner = runner
        self.registry = registry
        self.exchange = exchange
        self.sizer = sizer
        self._trailing_configs: Dict[Tuple[str, str], TrailingConfig] = {}

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
        orders_count: Optional[int] = None,
        first_price: Optional[float] = None,
        last_price: Optional[float] = None,
        first_offset_percent: Optional[float] = None,
        last_offset_percent: Optional[float] = None,
        distribution_mode: Optional[str] = None,
        distribution_value: float = 1.0,
    ) -> GridSession:
        has_price_fields = first_price is not None or last_price is not None
        has_offset_fields = first_offset_percent is not None or last_offset_percent is not None

        if has_price_fields and has_offset_fields:
            raise ValueError(
                "Cannot specify both explicit price fields and offset fields simultaneously"
            )

        explicit_mode = all(
            value is not None
            for value in (orders_count, first_price, last_price, distribution_mode)
        )
        offset_mode = all(
            value is not None
            for value in (orders_count, first_offset_percent, last_offset_percent, distribution_mode)
        )

        if offset_mode:
            if first_offset_percent <= 0:
                raise ValueError(f"first_offset_percent must be > 0, got {first_offset_percent}")
            if last_offset_percent <= 0:
                raise ValueError(f"last_offset_percent must be > 0, got {last_offset_percent}")
            current_price = self.exchange.get_price(symbol)
            if position_side == "LONG":
                first_price = current_price * (1 - first_offset_percent / 100)
                last_price = current_price * (1 - last_offset_percent / 100)
            elif position_side == "SHORT":
                first_price = current_price * (1 + first_offset_percent / 100)
                last_price = current_price * (1 + last_offset_percent / 100)
            else:
                raise ValueError(f"Unsupported position_side: {position_side!r}")

        use_new_grid_mode = explicit_mode or offset_mode

        if use_new_grid_mode:
            base_price_for_sizer = first_price
            effective_levels_count = orders_count
        else:
            base_price_for_sizer = self.exchange.get_price(symbol)
            effective_levels_count = levels_count

        if use_new_grid_mode:
            if position_side == "LONG" and not (first_price > last_price):
                raise ValueError(
                    f"LONG grid requires first_price > last_price, got first_price={first_price}, last_price={last_price}"
                )
            if position_side == "SHORT" and not (first_price < last_price):
                raise ValueError(
                    f"SHORT grid requires first_price < last_price, got first_price={first_price}, last_price={last_price}"
                )

        base_qty = self.sizer.calculate_base_qty(
            total_budget, base_price_for_sizer, effective_levels_count, qty_mode, qty_multiplier, budget_mode, coin_total
        )
        session = self.builder.build_session(
            symbol=symbol,
            position_side=position_side,
            base_price=base_price_for_sizer,
            levels_count=effective_levels_count,
            step_percent=step_percent,
            base_qty=base_qty,
            qty_mode=qty_mode,
            qty_multiplier=qty_multiplier,
            orders_count=orders_count,
            first_price=first_price,
            last_price=last_price,
            distribution_mode=distribution_mode,
            distribution_value=distribution_value,
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

    def modify_session(
        self,
        symbol: str,
        position_side: str,
        total_budget: float,
        orders_count: int,
        distribution_mode: str,
        first_price: Optional[float] = None,
        last_price: Optional[float] = None,
        first_offset_percent: Optional[float] = None,
        last_offset_percent: Optional[float] = None,
        distribution_value: float = 1.0,
        qty_mode: str = "fixed",
        qty_multiplier: float = 1.0,
    ) -> GridSession:
        session = self.registry.get_session(symbol, position_side)
        if session is None:
            raise ValueError(f"Session not found for symbol={symbol!r}, position_side={position_side!r}")

        if orders_count != len(session.levels):
            raise ValueError(
                f"orders_count={orders_count} does not match existing session levels={len(session.levels)}"
            )

        if position_side not in ("LONG", "SHORT"):
            raise ValueError(f"Unsupported position_side: {position_side!r}")

        has_price_fields = first_price is not None or last_price is not None
        has_offset_fields = first_offset_percent is not None or last_offset_percent is not None

        if has_price_fields and has_offset_fields:
            raise ValueError(
                "Cannot specify both explicit price fields and offset fields simultaneously"
            )

        explicit_mode = first_price is not None and last_price is not None
        offset_mode = first_offset_percent is not None and last_offset_percent is not None

        if has_price_fields and not explicit_mode:
            raise ValueError("explicit mode requires both first_price and last_price")
        if has_offset_fields and not offset_mode:
            raise ValueError("offset mode requires both first_offset_percent and last_offset_percent")
        if not explicit_mode and not offset_mode:
            raise ValueError(
                "must specify either first_price + last_price or first_offset_percent + last_offset_percent"
            )

        if offset_mode:
            if first_offset_percent <= 0:
                raise ValueError(f"first_offset_percent must be > 0, got {first_offset_percent}")
            if last_offset_percent <= 0:
                raise ValueError(f"last_offset_percent must be > 0, got {last_offset_percent}")
            current_price = self.exchange.get_price(symbol)
            if position_side == "LONG":
                first_price = current_price * (1 - first_offset_percent / 100)
                last_price = current_price * (1 - last_offset_percent / 100)
            elif position_side == "SHORT":
                first_price = current_price * (1 + first_offset_percent / 100)
                last_price = current_price * (1 + last_offset_percent / 100)

        if position_side == "LONG" and not (first_price > last_price):
            raise ValueError(
                f"LONG grid requires first_price > last_price, got first_price={first_price}, last_price={last_price}"
            )
        if position_side == "SHORT" and not (first_price < last_price):
            raise ValueError(
                f"SHORT grid requires first_price < last_price, got first_price={first_price}, last_price={last_price}"
            )

        base_qty = self.sizer.calculate_base_qty(
            total_budget, first_price, orders_count, qty_mode, qty_multiplier
        )
        new_session = self.builder.build_session(
            symbol=symbol,
            position_side=position_side,
            base_price=first_price,
            levels_count=orders_count,
            step_percent=1.0,
            base_qty=base_qty,
            qty_mode=qty_mode,
            qty_multiplier=qty_multiplier,
            orders_count=orders_count,
            first_price=first_price,
            last_price=last_price,
            distribution_mode=distribution_mode,
            distribution_value=distribution_value,
        )

        metadata = self.exchange.get_symbol_metadata(symbol)
        min_qty = metadata["min_qty"]
        min_notional = metadata["min_notional"]
        for level in new_session.levels:
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

        session = self.runner.modify_session_orders(session, new_session.levels)
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
        self.disable_trailing(symbol, position_side)
        return session

    def get_session(self, symbol: str, position_side: str) -> Optional[GridSession]:
        return self.registry.get_session(symbol, position_side)

    def remove_session(self, symbol: str, position_side: str) -> None:
        self.registry.remove_session(symbol, position_side)
        self.disable_trailing(symbol, position_side)

    def get_all_sessions(self) -> List[GridSession]:
        return self.registry.get_all_sessions()

    def enable_trailing(
        self,
        symbol: str,
        position_side: str,
        trailing_step_percent: float,
        first_offset_percent: float,
        last_offset_percent: float,
        total_budget: float,
        orders_count: int,
        distribution_mode: str,
        distribution_value: float = 1.0,
        qty_mode: str = "fixed",
        qty_multiplier: float = 1.0,
    ) -> float:
        if self.registry.get_session(symbol, position_side) is None:
            raise ValueError(f"Session not found for symbol={symbol!r}, position_side={position_side!r}")
        session = self.registry.get_session(symbol, position_side)
        if orders_count != len(session.levels):
            raise ValueError(
                f"orders_count={orders_count} does not match existing session levels={len(session.levels)}"
            )
        if position_side not in ("LONG", "SHORT"):
            raise ValueError(f"Unsupported position_side: {position_side!r}")
        if trailing_step_percent <= 0:
            raise ValueError(f"trailing_step_percent must be > 0, got {trailing_step_percent}")
        if first_offset_percent <= 0:
            raise ValueError(f"first_offset_percent must be > 0, got {first_offset_percent}")
        if last_offset_percent <= 0:
            raise ValueError(f"last_offset_percent must be > 0, got {last_offset_percent}")
        if last_offset_percent <= first_offset_percent:
            raise ValueError(
                f"last_offset_percent must be > first_offset_percent, "
                f"got first={first_offset_percent}, last={last_offset_percent}"
            )
        anchor_price = self.exchange.get_price(symbol)
        self._trailing_configs[(symbol, position_side)] = TrailingConfig(
            anchor_price=anchor_price,
            trailing_step_percent=trailing_step_percent,
            first_offset_percent=first_offset_percent,
            last_offset_percent=last_offset_percent,
            total_budget=total_budget,
            orders_count=orders_count,
            distribution_mode=distribution_mode,
            distribution_value=distribution_value,
            qty_mode=qty_mode,
            qty_multiplier=qty_multiplier,
        )
        return anchor_price

    def check_trailing(self, symbol: str, position_side: str, price: float) -> Optional[GridSession]:
        if self.registry.get_session(symbol, position_side) is None:
            return None
        config = self._trailing_configs.get((symbol, position_side))
        if config is None:
            return None
        current_price = price
        if position_side == "LONG":
            triggered = current_price > config.anchor_price * (1 + config.trailing_step_percent / 100)
            first_price = current_price * (1 - config.first_offset_percent / 100)
            last_price  = current_price * (1 - config.last_offset_percent / 100)
        else:
            triggered = current_price < config.anchor_price * (1 - config.trailing_step_percent / 100)
            first_price = current_price * (1 + config.first_offset_percent / 100)
            last_price  = current_price * (1 + config.last_offset_percent / 100)
        if not triggered:
            return None
        session = self.modify_session(
            symbol=symbol,
            position_side=position_side,
            total_budget=config.total_budget,
            orders_count=config.orders_count,
            first_price=first_price,
            last_price=last_price,
            distribution_mode=config.distribution_mode,
            distribution_value=config.distribution_value,
            qty_mode=config.qty_mode,
            qty_multiplier=config.qty_multiplier,
        )
        config.anchor_price = current_price
        return session

    def disable_trailing(self, symbol: str, position_side: str) -> None:
        self._trailing_configs.pop((symbol, position_side), None)
