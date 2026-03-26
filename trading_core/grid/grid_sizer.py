class GridSizer:

    def calculate_base_qty(
        self,
        total_budget: float,
        base_price: float,
        levels_count: int,
        qty_mode: str,
        qty_multiplier: float = 1.0,
        budget_mode: str = "usdt_total",
        coin_total: float = 0.0,
    ) -> float:
        if budget_mode == "usdt_total":
            effective_budget = total_budget
        elif budget_mode == "coin_total":
            effective_budget = coin_total * base_price
        else:
            raise ValueError(f"Unsupported budget_mode: {budget_mode!r}")

        if qty_mode == "fixed":
            return effective_budget / levels_count / base_price
        elif qty_mode == "multiplier":
            if qty_multiplier == 1.0:
                return effective_budget / levels_count / base_price
            sum_coeffs = sum(qty_multiplier ** i for i in range(levels_count))
            return effective_budget / sum_coeffs / base_price
        else:
            raise ValueError(f"Unsupported qty_mode: {qty_mode!r}")
