from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from trading_core.grid.grid_models import GridSession


@dataclass
class TpSlConfig:
    sl_percent: float
    tp_percent: Optional[float] = None          # single TP: 3.0 → 3%
    take_profits: Optional[List[dict]] = None   # multi-TP: [{"tp_percent": X}, ...]


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
        self._tpsl_configs: Dict[Tuple[str, str], TpSlConfig] = {}
        self._grid_tp_orders: Dict[Tuple[str, str], List[dict]] = {}
        self._base_position_qty: Dict[Tuple[str, str], float] = {}
        self._tp_update_mode: Dict[Tuple[str, str], str] = {}
        self._sl_orders: Dict[Tuple[str, str], int] = {}

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
        sl_algo_id = self._sl_orders.pop((symbol, position_side), None)
        if sl_algo_id is not None:
            try:
                self.exchange.cancel_algo_order(sl_algo_id)
                print(f"[GridSL] {symbol}/{position_side}  SL cancelled in stop_session  algoId={sl_algo_id}")
            except Exception as e:
                print(f"[GridSL] {symbol}/{position_side}  SL cancel error in stop_session (algoId={sl_algo_id}): {e}")
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

    # ------------------------------------------------------------------
    # TP / SL
    # ------------------------------------------------------------------

    def enable_tpsl(
        self,
        symbol: str,
        position_side: str,
        sl_percent: float,
        tp_percent: Optional[float] = None,
        take_profits: Optional[List[dict]] = None,
    ) -> None:
        if tp_percent is None and take_profits is None:
            raise ValueError("enable_tpsl: provide either tp_percent or take_profits")
        if tp_percent is not None and take_profits is not None:
            raise ValueError("enable_tpsl: provide either tp_percent or take_profits, not both")
        if take_profits is not None:
            if not take_profits:
                raise ValueError("enable_tpsl: take_profits must not be empty")
            for i, tp in enumerate(take_profits):
                if "tp_percent" not in tp:
                    raise ValueError(
                        f"enable_tpsl: take_profits[{i}] missing 'tp_percent'"
                    )
                if tp["tp_percent"] <= 0:
                    raise ValueError(
                        f"enable_tpsl: take_profits[{i}]['tp_percent'] must be > 0, "
                        f"got {tp['tp_percent']}"
                    )
            take_profits = sorted(take_profits, key=lambda x: x["tp_percent"])
        if self.registry.get_session(symbol, position_side) is None:
            print(f"[TpSl] skip enable: session not found for {symbol}/{position_side}")
            return
        self._tpsl_configs[(symbol, position_side)] = TpSlConfig(
            sl_percent=sl_percent,
            tp_percent=tp_percent,
            take_profits=take_profits,
        )

        entry_price: float = 0.0
        for pos in self.exchange.get_positions(symbol):
            if pos["positionSide"] == position_side:
                entry_price = float(pos["entryPrice"])
                break

        if entry_price > 0:
            if position_side == "LONG":
                sl_price = entry_price * (1 - sl_percent / 100)
            else:
                sl_price = entry_price * (1 + sl_percent / 100)
            try:
                algo_id = self.exchange.place_stop_market_order(symbol, position_side, sl_price)
                self._sl_orders[(symbol, position_side)] = algo_id
                print(
                    f"[GridSL] {symbol}/{position_side}"
                    f"  SL placed  algoId={algo_id}"
                    f"  stopPrice={sl_price:.8f}  (entry={entry_price:.8f}, -{sl_percent}%)"
                )
            except Exception as e:
                print(f"[GridSL] {symbol}/{position_side}  failed to place SL: {e}")
        else:
            print(f"[GridSL] {symbol}/{position_side}  skip SL placement: entry_price=0")

    def disable_tpsl(self, symbol: str, position_side: str) -> None:
        algo_id = self._sl_orders.pop((symbol, position_side), None)
        if algo_id is not None:
            try:
                self.exchange.cancel_algo_order(algo_id)
                print(f"[GridSL] {symbol}/{position_side}  SL cancelled  algoId={algo_id}")
            except Exception as e:
                print(f"[GridSL] {symbol}/{position_side}  SL cancel error (algoId={algo_id}): {e}")
        self._tpsl_configs.pop((symbol, position_side), None)

    def update_sl_after_averaging(self, symbol: str, position_side: str) -> None:
        config = self._tpsl_configs.get((symbol, position_side))
        if config is None:
            return

        old_algo_id = self._sl_orders.pop((symbol, position_side), None)
        if old_algo_id is not None:
            try:
                self.exchange.cancel_algo_order(old_algo_id)
                print(f"[GridSL] {symbol}/{position_side}  old SL cancelled  algoId={old_algo_id}")
            except Exception as e:
                print(f"[GridSL] {symbol}/{position_side}  old SL cancel error (algoId={old_algo_id}): {e}")

        new_entry: float = 0.0
        for pos in self.exchange.get_positions(symbol):
            if pos["positionSide"] == position_side:
                new_entry = float(pos["entryPrice"])
                break

        if new_entry <= 0:
            print(f"[GridSL] {symbol}/{position_side}  skip SL update: entryPrice=0")
            return

        if position_side == "LONG":
            new_sl_price = new_entry * (1 - config.sl_percent / 100)
        else:
            new_sl_price = new_entry * (1 + config.sl_percent / 100)

        try:
            new_algo_id = self.exchange.place_stop_market_order(symbol, position_side, new_sl_price)
            self._sl_orders[(symbol, position_side)] = new_algo_id
            print(
                f"[GridSL] {symbol}/{position_side}"
                f"  new SL placed after averaging  algoId={new_algo_id}"
                f"  stopPrice={new_sl_price:.8f}  (entry={new_entry:.8f}, -{config.sl_percent}%)"
            )
        except Exception as e:
            print(f"[GridSL] {symbol}/{position_side}  failed to place new SL after averaging: {e}")

    def set_tp_update_mode(self, symbol: str, position_side: str, mode: str) -> None:
        """mode: 'fixed' | 'reprice'"""
        if mode not in ("fixed", "reprice"):
            raise ValueError(f"set_tp_update_mode: unknown mode {mode!r}, expected 'fixed' or 'reprice'")
        self._tp_update_mode[(symbol, position_side)] = mode

    def check_grid_fills(self, symbol: str, position_side: str) -> list:
        session = self.registry.get_session(symbol, position_side)
        if session is None:
            return []

        current_qty = 0.0
        for pos in self.exchange.get_positions(symbol):
            if pos["positionSide"] == position_side:
                current_qty = abs(float(pos["positionAmt"]))
                break

        filled_levels = []
        for level in session.levels:
            if level.status != "placed" or not level.order_id:
                continue
            try:
                order = self.exchange.get_order(symbol, int(level.order_id))
                order_status = order.get("status")
                if order_status == "FILLED":
                    level.status = "filled"
                    filled_levels.append(level)
                elif order_status in ("CANCELED", "EXPIRED"):
                    # Order was replaced on exchange (e.g. drag on chart = cancel+new).
                    # Detect fill via position increase: if position grew enough to
                    # account for this level on top of all already-filled levels.
                    base_qty = self._base_position_qty.get((symbol, position_side), 0.0)
                    filled_so_far = sum(
                        lvl.qty for lvl in session.levels if lvl.status == "filled"
                    )
                    expected_without_this = base_qty + filled_so_far
                    if current_qty >= expected_without_this + level.qty * 0.9:
                        level.status = "filled"
                        filled_levels.append(level)
                        print(
                            f"[GridFills] {symbol}/{position_side}"
                            f"  level[{level.index}] detected via position delta"
                            f"  (order CANCELED, position {current_qty} >= {expected_without_this + level.qty * 0.9:.4f})"
                        )
                    # else: position not yet updated — leave as "placed", retry on next tick
            except Exception as e:
                print(f"[GridFills] error checking order {level.order_id}: {e}")
        return filled_levels

    def check_tp_fills(self, symbol: str, position_side: str) -> list:
        existing = self._grid_tp_orders.get((symbol, position_side), [])
        if not existing:
            return []

        current_qty = 0.0
        for pos in self.exchange.get_positions(symbol):
            if pos["positionSide"] == position_side:
                current_qty = abs(float(pos["positionAmt"]))
                break

        base_qty = self._base_position_qty.get((symbol, position_side), 0.0)

        filled_tps = []
        closed_so_far = 0.0

        for tp in existing:
            try:
                order = self.exchange.get_order(symbol, tp["order_id"])
                order_status = order.get("status")
                if order_status == "FILLED":
                    filled_tps.append(tp)
                    closed_so_far += tp["qty"]
                elif order_status in ("CANCELED", "EXPIRED"):
                    # TP was replaced on exchange (e.g. drag on chart = cancel+new at
                    # market price). Detect fill via position decrease: if position
                    # dropped enough to account for this TP on top of already-confirmed
                    # fills in this pass.
                    expected_floor = base_qty - closed_so_far - tp["qty"] * 0.9
                    if current_qty <= expected_floor:
                        filled_tps.append(tp)
                        closed_so_far += tp["qty"]
                        print(
                            f"[GridTP] {symbol}/{position_side}"
                            f"  TP detected via position delta"
                            f"  (order CANCELED, position {current_qty} <= {expected_floor:.4f})"
                        )
                    # else: position not yet updated — leave as is, retry on next tick
            except Exception as e:
                print(f"[GridTP] error checking TP order {tp['order_id']}: {e}")

        if filled_tps:
            filled_ids = {tp["order_id"] for tp in filled_tps}
            self._grid_tp_orders[(symbol, position_side)] = [
                tp for tp in existing if tp["order_id"] not in filled_ids
            ]
            self._base_position_qty[(symbol, position_side)] = current_qty

        return filled_tps

    def place_grid_tp_orders(
        self,
        symbol: str,
        position_side: str,
        take_profits: list,
    ) -> list:
        from decimal import Decimal

        if self.registry.get_session(symbol, position_side) is None:
            raise ValueError(
                f"place_grid_tp_orders: no active grid session for {symbol}/{position_side}"
            )

        if not take_profits:
            raise ValueError("place_grid_tp_orders: take_profits must not be empty")
        for i, tp in enumerate(take_profits):
            if tp.get("tp_percent", 0) <= 0:
                raise ValueError(
                    f"place_grid_tp_orders: take_profits[{i}]['tp_percent'] must be > 0"
                )
            if tp.get("close_percent", 0) <= 0:
                raise ValueError(
                    f"place_grid_tp_orders: take_profits[{i}]['close_percent'] must be > 0"
                )
        total_close = sum(tp["close_percent"] for tp in take_profits)
        if abs(total_close - 100) > 1e-8:
            raise ValueError(
                f"place_grid_tp_orders: sum of close_percent must be 100, got {total_close}"
            )

        existing = self._grid_tp_orders.get((symbol, position_side))
        if existing:
            raise ValueError(
                f"place_grid_tp_orders: grid TP orders already exist for {symbol}/{position_side}"
                f" — cancel them before placing new ones"
            )

        basis_price  = 0.0
        position_qty = 0.0
        for pos in self.exchange.get_positions(symbol):
            if pos["positionSide"] == position_side:
                basis_price  = float(pos["entryPrice"])
                position_qty = abs(float(pos["positionAmt"]))
                break

        if position_qty <= 0:
            raise ValueError(
                f"place_grid_tp_orders: no open {position_side} position for {symbol}"
            )
        if basis_price <= 0:
            raise ValueError(
                f"place_grid_tp_orders: invalid entryPrice={basis_price}"
            )

        self._base_position_qty[(symbol, position_side)] = position_qty

        metadata   = self.exchange.get_symbol_metadata(symbol)
        step       = Decimal(str(metadata["step_size"]))
        qty_dec    = Decimal(str(position_qty))
        close_side = "SELL" if position_side == "LONG" else "BUY"

        sorted_tps = sorted(take_profits, key=lambda x: x["tp_percent"])
        placed     = []
        allocated  = Decimal("0")

        for i, tp_cfg in enumerate(sorted_tps):
            tp_pct    = tp_cfg["tp_percent"]
            close_pct = tp_cfg["close_percent"]

            if position_side == "LONG":
                tp_price = basis_price * (1 + tp_pct / 100)
            else:
                tp_price = basis_price * (1 - tp_pct / 100)

            if i < len(sorted_tps) - 1:
                raw    = qty_dec * Decimal(str(close_pct)) / Decimal("100")
                tp_qty = float((raw // step) * step)
                allocated += Decimal(str(tp_qty))
            else:
                remainder = qty_dec - allocated
                tp_qty    = float((remainder // step) * step)

            if tp_qty <= 0:
                raise ValueError(
                    f"place_grid_tp_orders: take_profits[{i}] computed qty={tp_qty} <= 0"
                )

            response = self.exchange.place_limit_order(
                symbol=symbol,
                side=close_side,
                quantity=tp_qty,
                price=tp_price,
                position_side=position_side,
            )

            entry = {
                "order_id":      int(response["orderId"]),
                "tp_percent":    tp_pct,
                "close_percent": close_pct,
                "price":         tp_price,
                "qty":           tp_qty,
            }
            placed.append(entry)
            print(
                f"[GridTP] {symbol}/{position_side}"
                f"  TP[{i}] tp_percent={tp_pct}%"
                f"  price={tp_price:.8f}"
                f"  qty={tp_qty}"
                f"  order_id={entry['order_id']}"
            )

        self._grid_tp_orders[(symbol, position_side)] = placed
        return placed

    def update_grid_tp_orders_fixed(self, symbol: str, position_side: str):
        from decimal import Decimal

        existing = self._grid_tp_orders.get((symbol, position_side))
        if not existing:
            return None

        position_qty = 0.0
        for pos in self.exchange.get_positions(symbol):
            if pos["positionSide"] == position_side:
                position_qty = abs(float(pos["positionAmt"]))
                break

        if position_qty <= 0:
            print(f"[GridTP] {symbol}/{position_side}  no open position, skip TP update")
            return None

        for tp in existing:
            try:
                self.exchange.cancel_order(symbol, tp["order_id"])
                print(f"[GridTP] {symbol}/{position_side}  cancelled order_id={tp['order_id']}")
            except Exception as e:
                print(f"[GridTP] cancel error order_id={tp['order_id']}: {e}")

        metadata   = self.exchange.get_symbol_metadata(symbol)
        step       = Decimal(str(metadata["step_size"]))
        qty_dec    = Decimal(str(position_qty))
        close_side = "SELL" if position_side == "LONG" else "BUY"

        placed    = []
        allocated = Decimal("0")

        for i, tp_cfg in enumerate(existing):
            close_pct = tp_cfg["close_percent"]
            tp_price  = tp_cfg["price"]          # fixed: цена не меняется

            if i < len(existing) - 1:
                raw    = qty_dec * Decimal(str(close_pct)) / Decimal("100")
                tp_qty = float((raw // step) * step)
                allocated += Decimal(str(tp_qty))
            else:
                remainder = qty_dec - allocated
                tp_qty    = float((remainder // step) * step)

            if tp_qty <= 0:
                print(f"[GridTP] {symbol}/{position_side}  TP[{i}] qty={tp_qty} <= 0, skip")
                continue

            response = self.exchange.place_limit_order(
                symbol=symbol,
                side=close_side,
                quantity=tp_qty,
                price=tp_price,
                position_side=position_side,
            )

            entry = {
                "order_id":      int(response["orderId"]),
                "tp_percent":    tp_cfg["tp_percent"],
                "close_percent": close_pct,
                "price":         tp_price,
                "qty":           tp_qty,
            }
            placed.append(entry)
            print(
                f"[GridTP] {symbol}/{position_side}"
                f"  TP[{i}] tp_percent={tp_cfg['tp_percent']}%"
                f"  price={tp_price:.8f} (fixed)"
                f"  qty={tp_qty} (was {tp_cfg['qty']})"
                f"  order_id={entry['order_id']}"
            )

        self._grid_tp_orders[(symbol, position_side)] = placed

        if len(placed) != len(existing):
            print(
                f"[GridTP] {symbol}/{position_side}"
                f"  WARNING: placed {len(placed)}/{len(existing)} TP orders — incomplete"
            )

        return placed

    def update_grid_tp_orders_reprice(self, symbol: str, position_side: str):
        from decimal import Decimal

        existing = self._grid_tp_orders.get((symbol, position_side))
        if not existing:
            return None

        basis_price  = 0.0
        position_qty = 0.0
        for pos in self.exchange.get_positions(symbol):
            if pos["positionSide"] == position_side:
                basis_price  = float(pos["entryPrice"])
                position_qty = abs(float(pos["positionAmt"]))
                break

        if position_qty <= 0:
            print(f"[GridTP] {symbol}/{position_side}  no open position, skip TP reprice")
            return None

        for tp in existing:
            try:
                self.exchange.cancel_order(symbol, tp["order_id"])
                print(f"[GridTP] {symbol}/{position_side}  cancelled order_id={tp['order_id']}")
            except Exception as e:
                print(f"[GridTP] cancel error order_id={tp['order_id']}: {e}")

        metadata   = self.exchange.get_symbol_metadata(symbol)
        step       = Decimal(str(metadata["step_size"]))
        qty_dec    = Decimal(str(position_qty))
        close_side = "SELL" if position_side == "LONG" else "BUY"

        placed    = []
        allocated = Decimal("0")

        for i, tp_cfg in enumerate(existing):
            close_pct = tp_cfg["close_percent"]
            tp_pct    = tp_cfg["tp_percent"]

            if position_side == "LONG":
                tp_price = basis_price * (1 + tp_pct / 100)
            else:
                tp_price = basis_price * (1 - tp_pct / 100)

            if i < len(existing) - 1:
                raw    = qty_dec * Decimal(str(close_pct)) / Decimal("100")
                tp_qty = float((raw // step) * step)
                allocated += Decimal(str(tp_qty))
            else:
                remainder = qty_dec - allocated
                tp_qty    = float((remainder // step) * step)

            if tp_qty <= 0:
                print(f"[GridTP] {symbol}/{position_side}  TP[{i}] qty={tp_qty} <= 0, skip")
                continue

            response = self.exchange.place_limit_order(
                symbol=symbol,
                side=close_side,
                quantity=tp_qty,
                price=tp_price,
                position_side=position_side,
            )

            entry = {
                "order_id":      int(response["orderId"]),
                "tp_percent":    tp_pct,
                "close_percent": close_pct,
                "price":         tp_price,
                "qty":           tp_qty,
            }
            placed.append(entry)
            print(
                f"[GridTP] {symbol}/{position_side}"
                f"  TP[{i}] tp_percent={tp_pct}%"
                f"  price={tp_price:.8f} (from avg={basis_price:.8f})"
                f"  qty={tp_qty} (was {tp_cfg['qty']})"
                f"  order_id={entry['order_id']}"
            )

        self._grid_tp_orders[(symbol, position_side)] = placed

        if len(placed) != len(existing):
            print(
                f"[GridTP] {symbol}/{position_side}"
                f"  WARNING: placed {len(placed)}/{len(existing)} TP orders — incomplete"
            )

        return placed

    def close_leg(self, symbol: str, position_side: str) -> dict | None:
        positions = self.exchange.get_positions(symbol)
        for pos in positions:
            if pos["positionSide"] == position_side:
                qty = abs(float(pos["positionAmt"]))
                if qty == 0:
                    return None
                close_side = "sell" if position_side == "LONG" else "buy"
                return self.exchange.close_position(symbol, close_side, qty)
        return None

    def check_tpsl(self, symbol: str, position_side: str, price: float) -> Optional[str]:
        if self.registry.get_session(symbol, position_side) is None:
            return None

        config = self._tpsl_configs.get((symbol, position_side))
        if config is None:
            return None

        basis_price: float = 0.0
        qty: float = 0.0
        for pos in self.exchange.get_positions(symbol):
            if pos["positionSide"] == position_side:
                basis_price = float(pos["entryPrice"])
                qty         = abs(float(pos["positionAmt"]))
                break

        if qty <= 0:
            return None
        if basis_price <= 0:
            return None

        # SL — один уровень, всегда
        if position_side == "LONG":
            sl_hit = price <= basis_price * (1 - config.sl_percent / 100)
        else:
            sl_hit = price >= basis_price * (1 + config.sl_percent / 100)

        # TP — single или multi-level
        if config.take_profits is not None:
            tp_hit = False
            for tp_cfg in config.take_profits:
                tp_pct = tp_cfg["tp_percent"]
                if position_side == "LONG":
                    tp_hit = price >= basis_price * (1 + tp_pct / 100)
                else:
                    tp_hit = price <= basis_price * (1 - tp_pct / 100)
                if tp_hit:
                    break
        else:
            if position_side == "LONG":
                tp_hit = price >= basis_price * (1 + config.tp_percent / 100)
            else:
                tp_hit = price <= basis_price * (1 - config.tp_percent / 100)

        hit = "tp" if tp_hit else ("sl" if sl_hit else None)

        if hit is None:
            return None

        print(f"[TpSl] {symbol}/{position_side} hit={hit}  price={price}  basis={basis_price}")
        self.stop_session(symbol, position_side)
        self.close_leg(symbol, position_side)
        self.disable_tpsl(symbol, position_side)
        return hit
