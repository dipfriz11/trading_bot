from typing import List, Optional

from trading_core.grid.grid_models import CustomGridLevelConfig, GridLevel, GridSession


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

    def build_custom_session(
        self,
        symbol: str,
        position_side: str,
        custom_levels: List[CustomGridLevelConfig],
        reference_price: float,
        total_budget: float,
    ) -> GridSession:
        if position_side not in ("LONG", "SHORT"):
            raise ValueError(f"Unsupported position_side: {position_side!r}")
        if reference_price <= 0:
            raise ValueError(f"reference_price must be > 0, got {reference_price}")
        if total_budget <= 0:
            raise ValueError(f"total_budget must be > 0, got {total_budget}")
        if not custom_levels:
            raise ValueError("custom_levels must not be empty")

        ordered_levels = sorted(custom_levels, key=lambda level: level.index)
        actual_indexes = [level.index for level in ordered_levels]
        expected_indexes = list(range(1, len(ordered_levels) + 1))
        if actual_indexes != expected_indexes:
            raise ValueError(
                f"custom_levels indexes must be contiguous starting from 1, got {actual_indexes}"
            )

        sum_weights = sum(level.size_weight for level in ordered_levels)
        if sum_weights <= 0:
            raise ValueError(f"sum(size_weight) must be > 0, got {sum_weights}")

        session = GridSession(symbol=symbol, position_side=position_side)
        prev_price: Optional[float] = None

        for idx, level_cfg in enumerate(ordered_levels):
            is_first = idx == 0

            if is_first and level_cfg.price_mode == "offset_from_previous":
                raise ValueError("first custom level cannot use price_mode='offset_from_previous'")
            if not is_first and level_cfg.price_mode == "offset_from_reference":
                raise ValueError("non-first custom levels cannot use price_mode='offset_from_reference'")

            if level_cfg.price_mode == "fixed_price":
                level_price = level_cfg.price_value
            else:
                if level_cfg.price_mode == "offset_from_reference":
                    base_price = reference_price
                else:
                    base_price = prev_price
                    if base_price is None:
                        raise ValueError("offset_from_previous requires previous level price")

                if position_side == "LONG":
                    level_price = base_price * (1 - level_cfg.price_value / 100)
                else:
                    level_price = base_price * (1 + level_cfg.price_value / 100)

            if level_price <= 0:
                raise ValueError(
                    f"custom level[{level_cfg.index}] computed non-positive price={level_price}"
                )

            level_quote = total_budget * level_cfg.size_weight / sum_weights
            level_qty = level_quote / level_price
            if level_qty <= 0:
                raise ValueError(
                    f"custom level[{level_cfg.index}] computed non-positive qty={level_qty}"
                )

            session.levels.append(
                GridLevel(
                    index=level_cfg.index,
                    price=level_price,
                    qty=level_qty,
                    position_side=position_side,
                    status="planned",
                    use_reset_tp=level_cfg.use_reset_tp,
                    reset_tp_percent=level_cfg.reset_tp_percent,
                    reset_tp_close_percent=level_cfg.reset_tp_close_percent,
                )
            )

            prev_price = level_price

        return session

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
        level_reset_configs: Optional[List[dict]] = None,
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

            reset_cfg = level_reset_configs[i] if level_reset_configs and i < len(level_reset_configs) else {}
            level = GridLevel(
                index=i + 1,
                price=price,
                qty=qty,
                position_side=position_side,
                status="planned",
                use_reset_tp=reset_cfg.get("use_reset_tp", False),
                reset_tp_percent=reset_cfg.get("reset_tp_percent"),
                reset_tp_close_percent=reset_cfg.get("reset_tp_close_percent"),
            )
            session.levels.append(level)

        return session
