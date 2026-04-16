from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from trading_core.grid.grid_models import GridLevel, GridSession


@dataclass
class TpSlConfig:
    sl_percent: float
    tp_percent: Optional[float] = None          # single TP: 3.0 → 3%
    take_profits: Optional[List[dict]] = None   # multi-TP: [{"tp_percent": X}, ...]
    sl_mode: str = "avg_entry"                  # "avg_entry" | "extreme_order"


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
        self._reset_tp_order: Dict[Tuple[str, str], dict] = {}
        self._grid_build_config: Dict[Tuple[str, str], dict] = {}
        self._grid_tp_config: Dict[Tuple[str, str], List[dict]] = {}

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
        level_reset_configs: Optional[List[dict]] = None,
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

        if offset_mode:
            self._grid_build_config[(symbol, position_side)] = {
                "orders_count":         orders_count,
                "first_offset_percent": first_offset_percent,
                "last_offset_percent":  last_offset_percent,
                "distribution_mode":    distribution_mode,
                "distribution_value":   distribution_value,
                "level_reset_configs":  level_reset_configs or [],
            }

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
            level_reset_configs=level_reset_configs,
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
        if offset_mode:
            self._grid_build_config[(symbol, position_side)]["slot_qtys"] = [
                l.qty for l in sorted(session.levels, key=lambda l: l.index)
            ]
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
        sl_mode: str = "avg_entry",
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
            sl_mode=sl_mode,
        )

        if sl_mode == "extreme_order":
            session = self.registry.get_session(symbol, position_side)
            placed = [l for l in (session.levels if session else []) if l.status == "placed"]
            if not placed:
                print(f"[GridSL] {symbol}/{position_side}  skip SL: no placed levels for extreme_order")
                return
            basis = min(l.price for l in placed) if position_side == "LONG" else max(l.price for l in placed)
            sl_price = basis * (1 - sl_percent / 100) if position_side == "LONG" else basis * (1 + sl_percent / 100)
            # No position yet — arm virtually; real SL placed after first fill
            _pos_qty = 0.0
            for _p in self.exchange.get_positions(symbol):
                if _p["positionSide"] == position_side:
                    _pos_qty = abs(float(_p["positionAmt"]))
                    break
            if _pos_qty <= 0:
                print(
                    f"[GridSL] {symbol}/{position_side}  extreme_order SL armed virtually"
                    f"  preview_basis={basis:.8f}  preview_sl={sl_price:.8f}  (no position yet)"
                )
                return
            sl_basis_label = f"extreme={basis:.8f}"
        else:
            basis = 0.0
            for pos in self.exchange.get_positions(symbol):
                if pos["positionSide"] == position_side:
                    basis = float(pos["entryPrice"])
                    break
            if basis <= 0:
                print(f"[GridSL] {symbol}/{position_side}  skip SL placement: entry_price=0")
                return
            sl_price = basis * (1 - sl_percent / 100) if position_side == "LONG" else basis * (1 + sl_percent / 100)
            sl_basis_label = f"entry={basis:.8f}"
        try:
            algo_id = self.exchange.place_stop_market_order(symbol, position_side, sl_price)
            self._sl_orders[(symbol, position_side)] = algo_id
            print(f"[GridSL] {symbol}/{position_side}  SL placed  algoId={algo_id}  stopPrice={sl_price:.8f}  ({sl_basis_label}, -{sl_percent}%)")
        except Exception as e:
            print(f"[GridSL] {symbol}/{position_side}  failed to place SL: {e}")

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
        if config.sl_mode == "extreme_order":
            # First-time placement: if no SL placed yet and position now exists, place at extreme
            if (symbol, position_side) not in self._sl_orders:
                _pos_qty = 0.0
                for _p in self.exchange.get_positions(symbol):
                    if _p["positionSide"] == position_side:
                        _pos_qty = abs(float(_p["positionAmt"]))
                        break
                if _pos_qty > 0:
                    self._update_sl_from_extreme(symbol, position_side)
            return  # extreme_order SL not tied to avg entry after first placement

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

    def _update_sl_from_extreme(self, symbol: str, position_side: str) -> None:
        config = self._tpsl_configs.get((symbol, position_side))
        if config is None:
            return
        session = self.registry.get_session(symbol, position_side)
        placed = [l for l in (session.levels if session else []) if l.status == "placed"]
        if not placed:
            print(f"[GridSL] {symbol}/{position_side}  skip extreme SL update: no placed levels")
            return
        basis = min(l.price for l in placed) if position_side == "LONG" else max(l.price for l in placed)
        new_sl_price = basis * (1 - config.sl_percent / 100) if position_side == "LONG" else basis * (1 + config.sl_percent / 100)
        old_algo_id = self._sl_orders.pop((symbol, position_side), None)
        if old_algo_id is not None:
            try:
                self.exchange.cancel_algo_order(old_algo_id)
                print(f"[GridSL] {symbol}/{position_side}  extreme SL cancelled  algoId={old_algo_id}")
            except Exception as e:
                print(f"[GridSL] {symbol}/{position_side}  extreme SL cancel error: {e}")
        try:
            new_algo_id = self.exchange.place_stop_market_order(symbol, position_side, new_sl_price)
            self._sl_orders[(symbol, position_side)] = new_algo_id
            print(f"[GridSL] {symbol}/{position_side}  extreme SL updated  algoId={new_algo_id}  stopPrice={new_sl_price:.8f}  (extreme={basis:.8f}, -{config.sl_percent}%)")
        except Exception as e:
            print(f"[GridSL] {symbol}/{position_side}  extreme SL place error: {e}")

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
        current_entry = 0.0
        for pos in self.exchange.get_positions(symbol):
            if pos["positionSide"] == position_side:
                current_qty = abs(float(pos["positionAmt"]))
                current_entry = float(pos.get("entryPrice", 0))
                break

        base_qty = self._base_position_qty.get((symbol, position_side), 0.0)
        placed_count = sum(1 for l in session.levels if l.status == "placed")
        filled_count = sum(1 for l in session.levels if l.status == "filled")
        print(
            f"[GRID-FILL] {symbol}/{position_side}  check_grid_fills enter"
            f"  current_qty={current_qty}  entry={current_entry:.8f}"
            f"  base_qty={base_qty}  session placed={placed_count} filled={filled_count}"
        )

        filled_levels = []
        for level in session.levels:
            if level.status != "placed" or not level.order_id:
                continue
            try:
                order = self.exchange.get_order(symbol, int(level.order_id))
                order_status = order.get("status")
                print(
                    f"[ORDER-PAYLOAD] {symbol}/{position_side}  level[{level.index}]"
                    f"  order_id={level.order_id}  status={order_status}"
                    f"  side={order.get('side')}  origQty={order.get('origQty')}"
                    f"  executedQty={order.get('executedQty')}  avgPrice={order.get('avgPrice')}"
                    f"  cumQuote={order.get('cumQuote')}  updateTime={order.get('updateTime')}"
                )
                if order_status == "FILLED":
                    level.status = "filled"
                    filled_levels.append(level)
                    print(
                        f"[GRID-FILL] {symbol}/{position_side}"
                        f"  level[{level.index}] FILLED (order status=FILLED)"
                        f"  order_id={level.order_id}  price={level.price}"
                    )
                elif order_status in ("CANCELED", "EXPIRED"):
                    # Order was replaced on exchange (e.g. drag on chart = cancel+new).
                    # Detect fill via position increase: if position grew enough to
                    # account for this level on top of all already-filled levels.
                    #
                    # For rebuilt levels (slot_index set): use slot-based threshold so
                    # historical fills from previous Reset TP cycles don't inflate needed.
                    # For original levels (slot_index=None): legacy filled_so_far logic.
                    _cfg = self._grid_build_config.get((symbol, position_side))
                    _slot_qtys = _cfg.get("slot_qtys") if _cfg else None
                    if level.slot_index is not None and _slot_qtys:
                        needed = base_qty + sum(_slot_qtys[0:level.slot_index]) * 0.9
                    else:
                        filled_so_far = sum(
                            lvl.qty for lvl in session.levels if lvl.status == "filled"
                        )
                        needed = base_qty + filled_so_far + level.qty * 0.9
                    if current_qty >= needed:
                        level.status = "filled"
                        filled_levels.append(level)
                        print(
                            f"[GridFills] {symbol}/{position_side}"
                            f"  level[{level.index}] detected via position delta"
                            f"  (order CANCELED, position {current_qty} >= {needed:.4f})"
                        )
                    elif current_qty < level.qty * 0.5:
                        # Position too small to contain this fill — cleanup cancel, no retry.
                        level.status = "canceled"
                        print(
                            f"[GridFills] {symbol}/{position_side}"
                            f"  level[{level.index}] cleanup cancel"
                            f"  current_qty={current_qty} < {level.qty * 0.5:.4f}"
                            f"  (position closed or near-zero, not a fill)"
                        )
                    else:
                        # Order is confirmed CANCELED on exchange but position hasn't
                        # reached the fill threshold for this slot. The live order is
                        # gone. Keeping the level in "placed" would pollute covered_slots
                        # in rebuild_pending_tail (false coverage — rebuild skips the slot
                        # but no live order exists). Cleanup-cancel now so the next
                        # rebuild_pending_tail correctly sees the slot as uncovered and
                        # re-places it.
                        level.status = "canceled"
                        _fsf = sum(lvl.qty for lvl in session.levels if lvl.status == "filled")
                        print(
                            f"[GridFills] {symbol}/{position_side}"
                            f"  level[{level.index}] cleanup cancel"
                            f"  (CANCELED order, position {current_qty:.4f} < needed {needed:.4f})"
                            f"  order_id={level.order_id}"
                            f"  slot_index={level.slot_index}  filled_so_far={_fsf:.4f}"
                            f"  → slot will be re-placed by next rebuild"
                        )
            except Exception as e:
                print(f"[GridFills] error checking order {level.order_id}: {e}")

        print(
            f"[GRID-FILL] {symbol}/{position_side}  check_grid_fills done"
            f"  filled_this_tick={[l.index for l in filled_levels]}"
        )
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

    def check_reset_tp_fill(self, symbol: str, position_side: str) -> Optional[dict]:
        entry = self._reset_tp_order.get((symbol, position_side))
        if not entry:
            print(f"[GRID-RESET-TP] {symbol}/{position_side}  check_reset_tp_fill: no active reset TP → skip")
            return None

        print(
            f"[ResetFill] {symbol}/{position_side}"
            f"  checking order_id={entry['order_id']}"
            f"  position_qty_at_placement={entry.get('position_qty_at_placement')}"
        )
        order_id = entry["order_id"]
        try:
            order = self.exchange.get_order(symbol, order_id)
            order_status = order.get("status")
        except Exception as e:
            print(f"[ResetTP] error checking order {order_id}: {e}")
            return None

        print(
            f"[ORDER-PAYLOAD] {symbol}/{position_side}  reset_tp order_id={order_id}"
            f"  status={order_status}  side={order.get('side')}"
            f"  origQty={order.get('origQty')}  executedQty={order.get('executedQty')}"
            f"  avgPrice={order.get('avgPrice')}  cumQuote={order.get('cumQuote')}"
            f"  price={order.get('price')}  updateTime={order.get('updateTime')}"
        )
        print(
            f"[GRID-RESET-TP] {symbol}/{position_side}"
            f"  order_id={order_id}  status={order_status}"
            f"  reset_tp_price={entry.get('price')}  reset_tp_qty={entry.get('qty')}"
        )

        if order_status == "FILLED":
            print(
                f"[ResetTP] {symbol}/{position_side}"
                f"  Reset TP FILLED  order_id={order_id}"
                f"  price={entry.get('price')}  qty={entry.get('qty')}"
            )
            self._reset_tp_order.pop((symbol, position_side), None)
            result = dict(entry)
            result["joint_levels"] = []
            result["detection_mode"] = "solo_filled"
            print(f"[GRID-RESET-TP] {symbol}/{position_side}  detection_mode=solo_filled")
            return result

        if order_status == "NEW":
            # Order still shows NEW but may have been drag-replaced and filled under
            # a different order_id. Detect via position decrease.
            position_qty_at_placement = entry.get("position_qty_at_placement", 0.0)
            if position_qty_at_placement > 0:
                _curr_qty = 0.0
                for _pos in self.exchange.get_positions(symbol):
                    if _pos["positionSide"] == position_side:
                        _curr_qty = abs(float(_pos["positionAmt"]))
                        break
                expected_floor = position_qty_at_placement - entry["qty"] * 0.9
                if _curr_qty <= expected_floor:
                    print(
                        f"[ResetTP] {symbol}/{position_side}"
                        f"  Reset TP detected via position delta (order still NEW)"
                        f"  current_qty={_curr_qty}  expected_floor<={expected_floor:.4f}"
                    )
                    try:
                        self.exchange.cancel_order(symbol, entry["order_id"])
                        print(f"[ResetTP] {symbol}/{position_side}  cancelled Reset TP order_id={entry['order_id']} (new_position_delta)")
                    except Exception as _e:
                        print(f"[ResetTP] {symbol}/{position_side}  cancel reset tp error (ignored): {_e}")
                    self._reset_tp_order.pop((symbol, position_side), None)
                    result = dict(entry)
                    result["joint_levels"] = []
                    result["detection_mode"] = "new_position_delta"
                    print(f"[GRID-RESET-TP] {symbol}/{position_side}  detection_mode=new_position_delta")
                    return result
                else:
                    print(
                        f"[GRID-RESET-TP] {symbol}/{position_side}"
                        f"  order NEW, position not decreased enough"
                        f"  current_qty={_curr_qty}  expected_floor<={expected_floor:.4f}"
                        f"  → waiting for fill or cancel"
                    )

        if order_status in ("CANCELED", "EXPIRED"):
            # drag on chart = cancel + fill at market price; detect via position decrease
            position_qty_at_placement = entry.get("position_qty_at_placement", 0.0)
            if position_qty_at_placement > 0:
                current_qty = 0.0
                for pos in self.exchange.get_positions(symbol):
                    if pos["positionSide"] == position_side:
                        current_qty = abs(float(pos["positionAmt"]))
                        break
                expected_floor = position_qty_at_placement - entry["qty"] * 0.9
                if current_qty <= expected_floor:
                    print(
                        f"[ResetTP] {symbol}/{position_side}"
                        f"  Reset TP detected via position delta"
                        f"  (order CANCELED, position {current_qty} <= {expected_floor:.4f})"
                    )
                    self._reset_tp_order.pop((symbol, position_side), None)
                    result = dict(entry)
                    result["joint_levels"] = []
                    result["detection_mode"] = "solo_cancel_position"
                    print(f"[GRID-RESET-TP] {symbol}/{position_side}  detection_mode=solo_cancel_position")
                    return result
                else:
                    print(
                        f"[GRID-RESET-TP] {symbol}/{position_side}"
                        f"  order CANCELED but position NOT decreased enough"
                        f"  current_qty={current_qty}  expected_floor<={expected_floor:.4f}"
                        f"  position_qty_at_placement={position_qty_at_placement}  reset_qty={entry['qty']}"
                        f"  → reset TP NOT detected (false cancel or race)"
                    )
                    # ── combined detection ────────────────────────────────────────
                    # Solo check failed. If Reset TP sold AND a grid level bought
                    # simultaneously, net position = at_placement - reset_qty + level_qty.
                    # Verify by checking the candidate level's order is also CANCELED.
                    session = self.registry.get_session(symbol, position_side)
                    if session:
                        for lvl in session.levels:
                            if lvl.status != "placed" or not lvl.order_id:
                                continue
                            combined_expected = position_qty_at_placement - entry["qty"] + lvl.qty
                            tolerance = lvl.qty * 0.1
                            if abs(current_qty - combined_expected) > tolerance:
                                continue
                            print(
                                f"[GRID-RESET-TP] {symbol}/{position_side}"
                                f"  combined detection candidate: level[{lvl.index}]"
                                f"  combined_expected={combined_expected:.4f}"
                                f"  current_qty={current_qty}  tolerance={tolerance:.4f}"
                                f"  formula: {position_qty_at_placement} - {entry['qty']} + {lvl.qty:.4f} = {combined_expected:.4f}"
                            )
                            try:
                                lvl_order = self.exchange.get_order(symbol, int(lvl.order_id))
                                lvl_status = lvl_order.get("status")
                            except Exception as e:
                                print(f"[GRID-RESET-TP] {symbol}/{position_side}  combined check get_order error level[{lvl.index}]: {e}")
                                continue
                            if lvl_status not in ("CANCELED", "EXPIRED"):
                                print(
                                    f"[GRID-RESET-TP] {symbol}/{position_side}"
                                    f"  combined candidate level[{lvl.index}] order not CANCELED (status={lvl_status}) → skip"
                                )
                                continue
                            print(
                                f"[GRID-RESET-TP] {symbol}/{position_side}"
                                f"  detection_mode=combined_cancel_position_match"
                                f"  reset_tp={order_id}  joint_level[{lvl.index}] order_id={lvl.order_id}"
                                f"  position_match: {current_qty:.4f} ≈ {combined_expected:.4f}"
                            )
                            self._reset_tp_order.pop((symbol, position_side), None)
                            result = dict(entry)
                            result["joint_levels"] = [lvl]
                            result["detection_mode"] = "combined_cancel_position_match"
                            return result
                    # ── end combined detection ────────────────────────────────────

        return None

    def place_reset_tp_complex(self, symbol: str, position_side: str, filled_level) -> Optional[dict]:
        if not filled_level.use_reset_tp:
            print(f"[GRID-RESET-TP] {symbol}/{position_side}  place_reset_tp_complex: level.use_reset_tp=False → skip")
            return None
        if filled_level.reset_tp_percent is None:
            print(f"[GRID-RESET-TP] {symbol}/{position_side}  place_reset_tp_complex: reset_tp_percent=None → skip")
            return None
        if filled_level.reset_tp_close_percent is None:
            print(f"[GRID-RESET-TP] {symbol}/{position_side}  place_reset_tp_complex: reset_tp_close_percent=None → skip")
            return None

        print(
            f"[GRID-RESET-TP] {symbol}/{position_side}  place_reset_tp_complex enter"
            f"  triggered_by=level[{filled_level.index}]"
            f"  reset_tp_percent={filled_level.reset_tp_percent}"
            f"  reset_tp_close_percent={filled_level.reset_tp_close_percent}"
        )

        # cancel existing Reset TP if already active (only one allowed at a time)
        existing_reset = self._reset_tp_order.get((symbol, position_side))
        if existing_reset:
            try:
                self.exchange.cancel_order(symbol, existing_reset["order_id"])
                print(f"[ResetTP] {symbol}/{position_side}  cancelled existing Reset TP order_id={existing_reset['order_id']}")
            except Exception as e:
                print(f"[ResetTP] cancel existing Reset TP error order_id={existing_reset['order_id']}: {e}")
            self._reset_tp_order.pop((symbol, position_side), None)

        # Determine target_rebuild_count: inherit from replaced Reset TP or count fresh
        if existing_reset and existing_reset.get("target_rebuild_count") is not None:
            target_rebuild_count = existing_reset["target_rebuild_count"]
            print(f"[GRID-RESET-TP] {symbol}/{position_side}  target_rebuild_count={target_rebuild_count} (inherited)")
        else:
            _sess = self.registry.get_session(symbol, position_side)
            target_rebuild_count = sum(1 for l in (_sess.levels if _sess else []) if l.status == "placed")
            print(f"[GRID-RESET-TP] {symbol}/{position_side}  target_rebuild_count={target_rebuild_count} (fresh count)")

        existing = self._grid_tp_orders.get((symbol, position_side), [])
        print(
            f"[ResetTpDbg] {symbol}/{position_side}"
            f"  existing_main_tp={'empty' if not existing else [t['order_id'] for t in existing]}"
            f"  reset_tp_percent={filled_level.reset_tp_percent}"
            f"  reset_tp_close_percent={filled_level.reset_tp_close_percent}"
        )

        entry_price  = 0.0
        position_qty = 0.0
        for pos in self.exchange.get_positions(symbol):
            if pos["positionSide"] == position_side:
                entry_price  = float(pos["entryPrice"])
                position_qty = abs(float(pos["positionAmt"]))
                break

        print(
            f"[GRID-RESET-TP] {symbol}/{position_side}  position snapshot"
            f"  entry={entry_price:.8f}  position_qty={position_qty}"
            f"  existing_main_tp={[t['order_id'] for t in existing]}"
        )

        if position_qty <= 0:
            print(f"[ResetTP] {symbol}/{position_side}  no open position, skip")
            return None
        if entry_price <= 0:
            print(f"[ResetTP] {symbol}/{position_side}  invalid entryPrice={entry_price}, skip")
            return None

        # cancel existing Main TP orders
        for tp in existing:
            try:
                self.exchange.cancel_order(symbol, tp["order_id"])
                print(f"[ResetTP] {symbol}/{position_side}  cancelled Main TP order_id={tp['order_id']}")
            except Exception as e:
                print(f"[ResetTP] cancel error order_id={tp['order_id']}: {e}")
        self._grid_tp_orders[(symbol, position_side)] = []

        from decimal import Decimal
        metadata   = self.exchange.get_symbol_metadata(symbol)
        step       = Decimal(str(metadata["step_size"]))
        qty_dec    = Decimal(str(position_qty))
        close_side = "SELL" if position_side == "LONG" else "BUY"

        # Reset TP qty
        raw_reset = qty_dec * Decimal(str(filled_level.reset_tp_close_percent)) / Decimal("100")
        reset_qty = float((raw_reset // step) * step)
        if reset_qty <= 0:
            print(f"[ResetTP] {symbol}/{position_side}  reset_qty={reset_qty} <= 0, skip")
            return None

        # Main TP qty = remainder
        allocated = Decimal(str(reset_qty))
        remainder = qty_dec - allocated
        main_qty  = float((remainder // step) * step)

        # Reset TP price
        if position_side == "LONG":
            reset_tp_price = entry_price * (1 + filled_level.reset_tp_percent / 100)
        else:
            reset_tp_price = entry_price * (1 - filled_level.reset_tp_percent / 100)

        # place Reset TP
        reset_response = self.exchange.place_limit_order(
            symbol=symbol,
            side=close_side,
            quantity=reset_qty,
            price=reset_tp_price,
            position_side=position_side,
        )
        reset_entry = {
            "order_id":                  int(reset_response["orderId"]),
            "reset_tp_percent":          filled_level.reset_tp_percent,
            "close_percent":             filled_level.reset_tp_close_percent,
            "price":                     reset_tp_price,
            "qty":                       reset_qty,
            "position_qty_at_placement": position_qty,
            "target_rebuild_count":      target_rebuild_count,
        }
        self._reset_tp_order[(symbol, position_side)] = reset_entry
        print(
            f"[ResetTP] {symbol}/{position_side}"
            f"  Reset TP placed  order_id={reset_entry['order_id']}"
            f"  price={reset_tp_price:.8f}  qty={reset_qty}"
        )
        print(
            f"[GRID-RESET-TP] {symbol}/{position_side}  _reset_tp_order saved"
            f"  order_id={reset_entry['order_id']}"
            f"  price={reset_tp_price:.8f}  qty={reset_qty}"
            f"  position_qty_at_placement={position_qty}"
            f"  target_rebuild_count={target_rebuild_count}"
        )

        # place Main TP — price from existing tp_percent × new entryPrice (reprice pattern)
        if not existing:
            print(f"[ResetTP] {symbol}/{position_side}  no existing Main TP config, skip Main TP")
            return {"reset_tp": reset_entry, "main_tp": None}

        if main_qty <= 0:
            print(f"[ResetTP] {symbol}/{position_side}  main_qty={main_qty} <= 0, skip Main TP")
            return {"reset_tp": reset_entry, "main_tp": None}

        last_tp_cfg = existing[-1]
        if last_tp_cfg.get("tp_percent") is None:
            print(f"[ResetTP] {symbol}/{position_side}  last Main TP has no tp_percent, skip Main TP")
            return {"reset_tp": reset_entry, "main_tp": None}

        main_tp_pct = last_tp_cfg["tp_percent"]
        if position_side == "LONG":
            main_tp_price = entry_price * (1 + main_tp_pct / 100)
        else:
            main_tp_price = entry_price * (1 - main_tp_pct / 100)

        main_response = self.exchange.place_limit_order(
            symbol=symbol,
            side=close_side,
            quantity=main_qty,
            price=main_tp_price,
            position_side=position_side,
        )
        main_entry = {
            "order_id":      int(main_response["orderId"]),
            "tp_percent":    main_tp_pct,
            "close_percent": last_tp_cfg.get("close_percent"),
            "price":         main_tp_price,
            "qty":           main_qty,
        }
        self._grid_tp_orders[(symbol, position_side)] = [main_entry]
        print(
            f"[ResetTP] {symbol}/{position_side}"
            f"  Main TP placed  order_id={main_entry['order_id']}"
            f"  price={main_tp_price:.8f}  qty={main_qty}"
        )
        print(
            f"[GRID-RESET-TP] {symbol}/{position_side}  _grid_tp_orders saved (post-reset)"
            f"  order_id={main_entry['order_id']}"
            f"  price={main_tp_price:.8f}  qty={main_qty}"
        )

        return {"reset_tp": reset_entry, "main_tp": main_entry}

    def reconcile_position_decrease(
        self,
        symbol: str,
        position_side: str,
        curr_qty: float,
        released_qty: float,
    ) -> Optional[list]:
        """
        Pure computation — no side effects, no REST calls.
        Given current position qty and how much was released by an event,
        returns target slot indices to restore (extreme first), or None.
        """
        cfg = self._grid_build_config.get((symbol, position_side))
        if cfg is None:
            return None

        slot_qtys    = cfg.get("slot_qtys")
        orders_count = cfg["orders_count"]
        if not slot_qtys:
            return None

        # State: how many slots are covered by current position
        remaining          = curr_qty
        levels_in_position = 0
        for sq in slot_qtys:
            if remaining >= sq * 0.9:
                remaining          -= sq
                levels_in_position += 1
            else:
                break

        # Candidate tail (extreme first = highest index)
        full_tail = list(range(orders_count, levels_in_position, -1))
        if not full_tail:
            return None

        # Budget: how many slots the released qty covers
        rem    = released_qty
        budget = 0
        for sq in slot_qtys:
            if rem >= sq * 0.9:
                rem    -= sq
                budget += 1
            else:
                break

        if budget <= 0:
            return None

        target = full_tail[:budget]
        print(
            f"[Reconcile] {symbol}/{position_side}"
            f"  curr_qty={curr_qty}  released_qty={released_qty}"
            f"  levels_in_pos={levels_in_position}  budget={budget}"
            f"  target_slots={target}"
        )
        return target

    def rebuild_pending_tail(self, symbol: str, position_side: str, target_slots: list = None) -> Optional[list]:
        print(f"[RebuildV2] {symbol}/{position_side}  enter")
        session = self.registry.get_session(symbol, position_side)
        if session is None:
            print(f"[RebuildV2] {symbol}/{position_side}  no session -> skip")
            return None

        cfg = self._grid_build_config.get((symbol, position_side))
        if cfg is None:
            print(f"[RebuildV2] {symbol}/{position_side}  no build config -> skip")
            return None

        entry_price  = 0.0
        position_qty = 0.0
        for pos in self.exchange.get_positions(symbol):
            if pos["positionSide"] == position_side:
                entry_price  = float(pos["entryPrice"])
                position_qty = abs(float(pos["positionAmt"]))
                break

        if entry_price <= 0:
            print(f"[RebuildV2] {symbol}/{position_side}  invalid entry={entry_price} -> skip")
            return None

        orders_count      = cfg["orders_count"]
        first_offset_pct  = cfg["first_offset_percent"]
        last_offset_pct   = cfg["last_offset_percent"]
        distribution_mode = cfg["distribution_mode"]
        distribution_val  = cfg["distribution_value"]

        # Per-slot qty template: normalized at session start, fixed for the whole cycle
        slot_qtys = cfg.get("slot_qtys")
        if slot_qtys is None:
            # Fallback for sessions without slot_qtys (started before this fix)
            fallback_qty = next(
                (l.qty for l in session.levels if l.status in ("placed", "filled")), 0.0
            )
            if fallback_qty <= 0:
                print(f"[RebuildV2] {symbol}/{position_side}  cannot derive slot qtys -> skip")
                return None
            slot_qtys = [fallback_qty] * orders_count

        placed_levels = [l for l in session.levels if l.status == "placed"]
        if target_slots is not None:
            # Reconcile-driven: caller already computed the target
            tail_indices = target_slots
            print(
                f"[RebuildV2] {symbol}/{position_side}"
                f"  target_slots={tail_indices}  (reconcile-driven)"
            )
        elif placed_levels:
            _rem = position_qty
            _lvl_in_pos = 0
            for _sq in slot_qtys:
                if _rem >= _sq * 0.5:
                    _rem -= _sq
                    _lvl_in_pos += 1
                else:
                    break
            tail_indices = list(range(orders_count, _lvl_in_pos, -1))
            print(
                f"[RebuildV2] {symbol}/{position_side}"
                f"  position_qty={position_qty}  placed_count={len(placed_levels)}"
                f"  levels_in_pos={_lvl_in_pos}  orders_count={orders_count}  tail={tail_indices}"
            )
        else:
            # Fallback: derive from position qty when no placed levels exist
            remaining_qty      = position_qty
            levels_in_position = 0
            for sq in slot_qtys:
                if remaining_qty >= sq * 0.5:
                    remaining_qty      -= sq
                    levels_in_position += 1
                else:
                    break
            tail_indices = list(range(orders_count, levels_in_position, -1))
            print(
                f"[RebuildV2] {symbol}/{position_side}"
                f"  position_qty={position_qty}  placed_count=0 (fallback)"
                f"  orders_count={orders_count}  tail={tail_indices}"
            )

        # Build desired tail prices (empty dict when tail_indices is empty).
        # Done before any early return so stale cancel always runs.
        if tail_indices:
            if position_side == "LONG":
                first_price = entry_price * (1 - first_offset_pct / 100)
                last_price  = entry_price * (1 - last_offset_pct  / 100)
            else:
                first_price = entry_price * (1 + first_offset_pct / 100)
                last_price  = entry_price * (1 + last_offset_pct  / 100)
            all_prices = (
                [first_price] if orders_count == 1
                else self.builder._build_grid_prices(
                    first_price, last_price, orders_count, distribution_mode, distribution_val
                )
            )
            sorted_tail = sorted(tail_indices)
            tail_prices = {idx: all_prices[pos] for pos, idx in enumerate(sorted_tail)}
        else:
            all_prices  = []
            tail_prices = {}

        # Cancel stale placed levels (not matching any desired tail price).
        # Runs regardless of whether new orders will be placed.
        # When tail_prices is empty (tail_indices=[]), all placed levels are stale.
        stale_placed = []
        for _sl in placed_levels:
            _eff = _sl.slot_index if _sl.slot_index is not None else _sl.index
            _tgt = tail_prices.get(_eff)
            if _tgt is None or abs(_sl.price - _tgt) / max(_tgt, 1e-12) >= 0.002:
                stale_placed.append(_sl)
        for level in stale_placed:
            if level.order_id:
                try:
                    self.exchange.cancel_order(symbol, level.order_id)
                    print(f"[RebuildV2] {symbol}/{position_side}  cancelled stale level[{level.index}]")
                except Exception as e:
                    print(f"[RebuildV2] {symbol}/{position_side}  cancel error level[{level.index}]: {e}")
            level.status = "canceled"

        if not tail_indices:
            if stale_placed:
                print(f"[RebuildV2] {symbol}/{position_side}  all slots covered, cancelled {len(stale_placed)} stale levels")
            else:
                print(f"[RebuildV2] {symbol}/{position_side}  nothing to rebuild -> skip")
            return None

        metadata     = self.exchange.get_symbol_metadata(symbol)
        min_qty      = metadata["min_qty"]
        min_notional = metadata["min_notional"]

        # Slots already covered by a still-placed level for the same effective slot at the
        # right price. Uses effective slot (slot_index for rebuilt levels, index for original
        # levels) so that an original level never accidentally counts as coverage for a
        # different slot just because its price is coincidentally near that slot's target.
        covered_slots = set()
        for _cl in session.levels:
            if _cl.status != "placed":
                continue
            _eff = _cl.slot_index if _cl.slot_index is not None else _cl.index
            _tgt = tail_prices.get(_eff)
            if _tgt is not None and abs(_cl.price - _tgt) / max(_tgt, 1e-12) < 0.002:
                covered_slots.add(_eff)

        # Pre-flight: check if the most extreme slot that needs a new order can be placed.
        # If it cannot, abort before touching anything on the exchange.
        slots_needing_order = [s for s in tail_indices if s not in covered_slots]
        if not slots_needing_order:
            if stale_placed:
                print(f"[RebuildV2] {symbol}/{position_side}  target slots covered, cancelled {len(stale_placed)} stale levels")
            else:
                print(f"[RebuildV2] {symbol}/{position_side}  all slots covered -> skip")
            return None
        extreme_slot = slots_needing_order[0]
        pf_qty, pf_price = self.exchange.round_order_params(
            symbol, position_side, slot_qtys[extreme_slot - 1], tail_prices[extreme_slot]
        )
        if pf_qty < min_qty or pf_qty * pf_price < min_notional:
            print(f"[RebuildV2] {symbol}/{position_side}  extreme slot={extreme_slot}  preflight failed -> abort")
            return None

        max_index  = max(l.index for l in session.levels)
        new_levels = []
        for slot_idx in tail_indices:
            if slot_idx in covered_slots:
                print(f"[RebuildV2] {symbol}/{position_side}  slot={slot_idx}  already covered -> skip")
                continue
            slot_qty = slot_qtys[slot_idx - 1]
            price    = tail_prices[slot_idx]
            r_qty, r_price = self.exchange.round_order_params(
                symbol, position_side, slot_qty, price
            )
            if r_qty < min_qty or r_qty * r_price < min_notional:
                print(f"[RebuildV2] {symbol}/{position_side}  slot={slot_idx}  margin check failed -> stop")
                break
            max_index += 1
            _lrc = cfg.get("level_reset_configs", [])
            _slot_rc = _lrc[slot_idx - 1] if _lrc and slot_idx - 1 < len(_lrc) else {}
            new_level = GridLevel(
                index=max_index,
                price=price,
                qty=slot_qty,
                position_side=position_side,
                status="planned",
                slot_index=slot_idx,
                use_reset_tp=_slot_rc.get("use_reset_tp", False),
                reset_tp_percent=_slot_rc.get("reset_tp_percent"),
                reset_tp_close_percent=_slot_rc.get("reset_tp_close_percent"),
            )
            new_levels.append(new_level)
            session.levels.append(new_level)
            print(f"[RebuildV2] {symbol}/{position_side}  slot={slot_idx}  price={price:.8f}  qty={slot_qty}")

        if not new_levels:
            print(f"[RebuildV2] {symbol}/{position_side}  no new levels placed")
            return None

        self.runner.place_session_orders(session)
        self.registry.save_session(session)

        placed_snap = [(l.index, l.order_id) for l in session.levels if l.status == "placed"]
        print(f"[RebuildV2] {symbol}/{position_side}  done  new={len(new_levels)}  active_placed={placed_snap}")

        _sl_cfg = self._tpsl_configs.get((symbol, position_side))
        if _sl_cfg and _sl_cfg.sl_mode == "extreme_order":
            self._update_sl_from_extreme(symbol, position_side)
        else:
            self.update_sl_after_averaging(symbol, position_side)
        return new_levels
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
        self._grid_tp_config[(symbol, position_side)] = sorted_tps
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
        template = existing or self._grid_tp_config.get((symbol, position_side))
        if not template:
            return None

        basis_price  = 0.0
        position_qty = 0.0
        for pos in self.exchange.get_positions(symbol):
            if pos["positionSide"] == position_side:
                basis_price  = float(pos["entryPrice"])
                position_qty = abs(float(pos["positionAmt"]))
                break

        if position_qty <= 0:
            print(f"[GridTP] {symbol}/{position_side}  no open position, skip TP update")
            return None

        for tp in (existing or []):
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

        for i, tp_cfg in enumerate(template):
            close_pct = tp_cfg["close_percent"]
            tp_price  = tp_cfg.get("price") or (           # bootstrap: вычислить из entry
                basis_price * (1 + tp_cfg["tp_percent"] / 100)
                if position_side == "LONG"
                else basis_price * (1 - tp_cfg["tp_percent"] / 100)
            )

            if i < len(template) - 1:
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
                f"  qty={tp_qty} (was {tp_cfg.get('qty', '—')})"
                f"  order_id={entry['order_id']}"
            )

        self._grid_tp_orders[(symbol, position_side)] = placed

        if len(placed) != len(template):
            print(
                f"[GridTP] {symbol}/{position_side}"
                f"  WARNING: placed {len(placed)}/{len(template)} TP orders — incomplete"
            )

        return placed

    def update_grid_tp_orders_reprice(self, symbol: str, position_side: str):
        from decimal import Decimal

        existing = self._grid_tp_orders.get((symbol, position_side))
        template = existing or self._grid_tp_config.get((symbol, position_side))
        if not template:
            print(f"[GridTP] {symbol}/{position_side}  skip reprice: no existing/template tp")
            return None

        template_source = "existing_orders" if existing else "_grid_tp_config"
        print(
            f"[GRID-TP] {symbol}/{position_side}  update_reprice enter"
            f"  template_source={template_source}"
            f"  existing_ids={[t['order_id'] for t in (existing or [])]}"
            f"  template_count={len(template)}"
        )

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

        print(
            f"[GRID-TP] {symbol}/{position_side}  reprice basis"
            f"  entry={basis_price:.8f}  position_qty={position_qty}"
        )

        for tp in (existing or []):
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

        for i, tp_cfg in enumerate(template):
            close_pct = tp_cfg["close_percent"]
            tp_pct    = tp_cfg["tp_percent"]

            if position_side == "LONG":
                tp_price = basis_price * (1 + tp_pct / 100)
            else:
                tp_price = basis_price * (1 - tp_pct / 100)

            if i < len(template) - 1:
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
                f"  qty={tp_qty} (was {tp_cfg.get('qty', '—')})"
                f"  order_id={entry['order_id']}"
            )

        self._grid_tp_orders[(symbol, position_side)] = placed

        tp_prices_str = [round(t["price"], 8) for t in placed]
        print(
            f"[GRID-TP] {symbol}/{position_side}  _grid_tp_orders saved"
            f"  count={len(placed)}"
            f"  order_ids={[t['order_id'] for t in placed]}"
            f"  prices={tp_prices_str}"
            f"  qtys={[t['qty'] for t in placed]}"
        )

        if len(placed) != len(template):
            print(
                f"[GridTP] {symbol}/{position_side}"
                f"  WARNING: placed {len(placed)}/{len(template)} TP orders — incomplete"
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

        # SL basis: avg entry (default) or extreme placed level
        if config.sl_mode == "extreme_order":
            _session = self.registry.get_session(symbol, position_side)
            _placed  = [l for l in (_session.levels if _session else []) if l.status == "placed"]
            sl_basis = (min(l.price for l in _placed) if position_side == "LONG" else max(l.price for l in _placed)) if _placed else basis_price
        else:
            sl_basis = basis_price

        # SL — один уровень, всегда
        if position_side == "LONG":
            sl_hit = price <= sl_basis * (1 - config.sl_percent / 100)
        else:
            sl_hit = price >= sl_basis * (1 + config.sl_percent / 100)

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
