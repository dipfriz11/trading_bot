import threading

from trading_core.position_manager import PositionManager, CycleConfig
from storage.sqlite_storage import SQLiteStorage
from config import get_target_profit


class SymbolRegistry:

    def __init__(self, base_config: CycleConfig):
        self.base_config = base_config
        self.registry = {}
        self._lock = threading.RLock()  # ← ВАЖНО: RLock вместо Lock

        self.storage = SQLiteStorage()
        self._load_state()
        
    def get_manager(self, symbol: str) -> PositionManager:
        with self._lock:

            if symbol not in self.registry:

                config_copy = CycleConfig(
                    base_size=self.base_config.base_size,
                    hedge_ratio=self.base_config.hedge_ratio,
                    major_multiplier=self.base_config.major_multiplier,
                    minor_multiplier=self.base_config.minor_multiplier,
                    target_profit=self.base_config.target_profit,
                    auto_close=self.base_config.auto_close,
                    repeat_mode=self.base_config.repeat_mode,
                    max_cycles=self.base_config.max_cycles,
                    max_total_exposure=self.base_config.max_total_exposure,
                )

                self.registry[symbol] = PositionManager(config_copy)

            return self.registry[symbol]

    def get_all_states(self):
        return {
            symbol: manager.get_state()
            for symbol, manager in self.registry.items()
        }

    # === СОХРАНЕНИЕ СОСТОЯНИЯ ===
    def _save_state(self):
        with self._lock:
            data = self.get_all_states()

            for symbol, state in data.items():
                self.storage.save_state(symbol, state)

    # === ЗАГРУЗКА СОСТОЯНИЯ ===
    def _load_state(self):
        with self._lock:

             try:
                  data = self.storage.load_all_states()

                  for symbol, state in data.items():
                      manager = self.get_manager(symbol)

                      manager.cycle_active = state["cycle_active"]
                      manager.bias = state["bias"]
                      manager.long_size = state["long_size"]
                      manager.short_size = state["short_size"]
                      manager.cycle_number = state["cycle_number"]
                      manager.blocked = state["blocked"]
                      manager.last_signal = state.get("last_signal")
                      if state.get("cycle_active"):
                          manager.cycle_target_profit = get_target_profit(symbol, manager.cycle_number)
                      else:
                          manager.cycle_target_profit = 0.0

             except Exception as e:
                  print("State load error:", e)

