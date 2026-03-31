from order.order_manager import OrderManager
from trading_core.watchers.single_trailing_watcher import SingleTrailingWatcher


class SingleOrderStrategy:

    def __init__(self, widget):
        self.widget = widget
        self.exchange = widget.exchange
        self.config = widget.config
        self.symbol = widget.symbol
        self.trailing_watcher = None

        self.order_manager = OrderManager(
            exchange=self.exchange,
            symbol=self.symbol,
            config=self.config
        )

    def execute(self, side: str):
        if self.config.get("entry_type") == "market":
            self._execute_market_entry(side)
            return

        amount = self.config["amount"]
        distance = self.config["distance"]

        price = self.exchange.get_price(self.symbol)

        position_side = "LONG" if side == "buy" else "SHORT"

        if side == "buy":
            target_price = price * (1 - distance / 100)
            order_side = "BUY"
        else:
            target_price = price * (1 + distance / 100)
            order_side = "SELL"

        print(f"[{self.symbol}] placing order | side={order_side} price={target_price}")

        # размещаем ордер через OrderRequest → executor
        from order.order_request import OrderRequest
        request = OrderRequest(
            symbol=self.symbol,
            side=order_side,
            order_type="limit",
            quantity=amount,
            price=target_price,
            params={"position_side": position_side}
        )
        self.order_manager.place_request(request)

        distance    = self.config.get("distance", 1.5)
        market_data = getattr(self.widget, "market_data", None)

        if market_data is not None:
            if self.trailing_watcher is None:
                self.trailing_watcher = SingleTrailingWatcher(self.order_manager, market_data)
            self.trailing_watcher.start_watching(self.symbol, distance, position_side)
        else:
            self.order_manager.start_trailing_loop(distance, position_side=position_side)

    def _execute_market_entry(self, side: str) -> None:
        """Market-entry сценарий для v1.
        Активируется через config["entry_type"] == "market".
        После подтверждённого входа вызывает on_position_confirmed().
        Limit+trailing path не затрагивает.
        """
        position_side = "LONG" if side == "buy" else "SHORT"
        leverage      = self.config.get("leverage", 1)

        side_key        = "long" if side == "buy" else "short"
        side_cfg        = self.config.get(side_key, {})
        usdt_amount_val = side_cfg.get("usdt_amount")
        usdt_amount     = usdt_amount_val if usdt_amount_val is not None \
                          else self.config["usdt_amount"]

        # guard: не открываем если позиция по этому side уже есть
        _, existing_qty = self._get_position(position_side)
        if existing_qty > 0:
            print(f"[{self.symbol}] {position_side} already open "
                  f"(qty={existing_qty}), skipping entry")
            return

        self.exchange.open_market_position(
            self.symbol, side, usdt_amount=usdt_amount, leverage=leverage
        )

        entry_price, qty = self._get_position_with_retry(position_side)
        if qty == 0:
            print(f"[{self.symbol}] WARN: position not confirmed after market entry")
            return

        self.on_position_confirmed(position_side, entry_price, qty)

    # ------------------------------------------------------------------
    # Position helpers
    # ------------------------------------------------------------------

    def _get_position(self, position_side: str) -> tuple:
        """Returns (entry_price, qty). entry_price=None if no open position."""
        for pos in self.exchange.get_positions(self.symbol):
            if pos["positionSide"] == position_side:
                qty = abs(float(pos["positionAmt"]))
                ep  = float(pos["entryPrice"]) if qty > 0 else None
                return ep, qty
        return None, 0.0

    def _get_position_with_retry(
        self, position_side: str, attempts: int = 5, delay: float = 0.5
    ) -> tuple:
        """Опрашивает get_positions() до attempts раз с паузой delay.
        Возвращает как только qty > 0, иначе (None, 0.0).
        """
        import time
        for attempt in range(attempts):
            ep, qty = self._get_position(position_side)
            if qty > 0:
                return ep, qty
            print(f"[{self.symbol}] waiting for position confirmation "
                  f"({attempt + 1}/{attempts})...")
            time.sleep(delay)
        return None, 0.0

    # ------------------------------------------------------------------
    # TP/SL hook — вызывается когда позиция подтверждена
    # Не подключён к execute() — точка подключения отдельный шаг
    # ------------------------------------------------------------------

    def on_position_confirmed(self, position_side: str,
                              entry_price: float, qty: float) -> None:
        """Единая точка постановки TP/SL после подтверждённого входа.
        Работает независимо от типа входа (market или limit fill).
        Вызывается извне: из execute() после market entry
        или из fill-watcher после limit fill.
        """
        side_key = "long" if position_side == "LONG" else "short"
        side_cfg = self.config.get(side_key, {})

        tp_val = side_cfg.get("tp_percent")
        tp_pct = tp_val if tp_val is not None else self.config.get("tp_percent")

        sl_val = side_cfg.get("sl_percent")
        sl_pct = sl_val if sl_val is not None else self.config.get("sl_percent")

        if tp_pct is not None and sl_pct is not None:
            if self.order_manager.has_tpsl(position_side):
                self.order_manager.cancel_tpsl(position_side)

            ids = self.order_manager.place_tpsl(
                entry_price, qty, position_side, tp_pct, sl_pct
            )
            print(f"[{self.symbol}] TP/SL placed: {ids}")
