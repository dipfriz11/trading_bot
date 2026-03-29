class Widget:
    def __init__(self, config: dict, exchange):
        self.id = config["id"]
        self.symbol = config["symbol"]
        self.exchange_name = config["exchange"]
        self.market = config["market"]

        self.margin_type = config.get("margin_type", "cross")
        self.position_mode = config.get("position_mode", "hedge")
        self.leverage = config.get("leverage", 1)

        self.strategy_name = config["strategy"]
        self.config = config["config"]

        self.exchange = exchange
        self.market_data = None

        self.is_running = False

        # --- stop_new режимы ---
        self.stop_new_enabled = self.config.get("stop_new_enabled", False)
        self.stop_new_mode = self.config.get("stop_new_mode", "entries_only")
        # entries_only / full_stop

        # --- инициализация стратегии ---
        if self.strategy_name == "single_order":
            from strategy.single_order_strategy import SingleOrderStrategy
            self.strategy = SingleOrderStrategy(self)
        elif self.strategy_name == "imbalance":
            from strategy.imbalance_strategy import ImbalanceStrategy
            self.strategy = ImbalanceStrategy(self)
        else:
            self.strategy = None

    def start(self):
        self.is_running = True

    def stop(self):
        self.is_running = False
        if self.strategy is not None and hasattr(self.strategy, "trailing_watcher"):
            watcher = self.strategy.trailing_watcher
            if watcher is not None:
                watcher.stop_all()

    def set_stop_new(self, enabled: bool, mode: str = "entries_only"):
        self.stop_new_enabled = enabled
        self.stop_new_mode = mode
        print(f"[{self.symbol}] stop_new: {enabled}, mode: {mode}")

    def on_signal(self, side: str):
        if not self.is_running:
            return

        # --- FULL STOP ---
        if self.stop_new_enabled and self.stop_new_mode == "full_stop":
            print(f"[{self.symbol}] FULL STOP active — ignoring signal")
            return

        # --- STOP ONLY NEW ENTRIES ---
        if self.stop_new_enabled and self.stop_new_mode == "entries_only":
            print(f"[{self.symbol}] stop_new entries_only — ignoring new entry")
            return

        if self.strategy:
            self.strategy.execute(side)
        else:
            print(f"[{self.symbol}] Unknown strategy: {self.strategy_name}")
