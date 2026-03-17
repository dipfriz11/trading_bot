from dataclasses import dataclass
from profit_manager import ProfitManager


@dataclass
class CycleConfig:
    base_size: float
    hedge_ratio: float
    major_multiplier: float
    minor_multiplier: float
    target_profit: float
    auto_close: bool
    repeat_mode: str  # "ACCUMULATE", "IGNORE"
    max_cycles: int | None = None
    max_total_exposure: float | None = None
    leverage: int = 1


class PositionManager:

    def __init__(self, config: CycleConfig):
        self.config = config
        self.reset_cycle()
        self.processing = False
        self.last_signal_time = 0
        self.profit_manager = ProfitManager(
            taker_fee=0.0004
        )

    def reset_cycle(self):
        self.cycle_active = False
        self.bias = None
        self.long_size = 0.0
        self.short_size = 0.0
        self.cycle_number = 0
        self.last_signal = None
        self.blocked = False
        self.processing = False
        self.last_signal_time = 0

    def report_cycle_close(
        self,
        symbol: str,
        reason: str,
        pnl: float,
        funding: float,
        entry_fees: float,
        exit_fees: float,
    ):
        print("\n===== CYCLE CLOSED =====")
        print(f"Symbol: {symbol}")
        print(f"Reason: {reason}")
        print(f"Cycle number: {self.cycle_number}")
        print(f"Realized PnL: {round(pnl, 6)}")
        print(f"Funding: {round(funding, 6)}")
        print(f"Entry fees: {round(entry_fees, 6)}")
        print(f"Exit fees: {round(exit_fees, 6)}")
        print("========================\n")

    # === СТАРТ ЦИКЛА ===

    def start_cycle(self, side: str):
        self.cycle_active = True
        self.bias = "UP" if side == "buy" else "DOWN"

        if side == "buy":
            self.long_size = self.config.base_size
            self.short_size = self.config.base_size * self.config.hedge_ratio
        else:
            self.short_size = self.config.base_size
            self.long_size = self.config.base_size * self.config.hedge_ratio

        self.cycle_number = 1
        self.last_signal = side

    # === ПРИМЕНЕНИЕ СИГНАЛА ===

    def apply_signal(self, side: str):

        if self.blocked:
            return

        if not self.cycle_active:
            self.start_cycle(side)
            return True

        if (self.config.repeat_mode or "").lower() == "ignore" and self.cycle_active:
            if side == self.last_signal:
                return False

        # Проверка лимита циклов
        if self.config.max_cycles is not None:
            if self.cycle_number >= self.config.max_cycles:
                self.blocked = True
                return

        self._apply_averaging(side)
        self.cycle_number += 1
        self.last_signal = side

        # Проверка лимита общего объема
        if self.config.max_total_exposure is not None:
            total = self.long_size + self.short_size
            if total >= self.config.max_total_exposure:
                self.blocked = True

        return True

    # === УСРЕДНЕНИЕ ===

    def _apply_averaging(self, side: str):

        if side == "buy":
            self.long_size += self.long_size * self.config.major_multiplier
            self.short_size += self.short_size * self.config.minor_multiplier

        elif side == "sell":
            self.short_size += self.short_size * self.config.major_multiplier
            self.long_size += self.long_size * self.config.minor_multiplier

    # === ПРОВЕРКА ПРОФИТА ===

    def check_close(self, total_unrealized_pnl: float):

        if not self.config.auto_close:
            return None

        if total_unrealized_pnl >= self.config.target_profit:
            self.reset_cycle()
            return "TARGET_PROFIT"

        return None


    # === СОСТОЯНИЕ ===

    def get_state(self):
        return {
            "cycle_active": self.cycle_active,
            "bias": self.bias,
            "long_size": round(self.long_size, 4),
            "short_size": round(self.short_size, 4),
            "cycle_number": self.cycle_number,
            "blocked": self.blocked,
            "last_signal": self.last_signal,
            "last_signal_time": self.last_signal_time,
        }