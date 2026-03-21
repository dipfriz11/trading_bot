import time
import logging
from config import COINS

logger = logging.getLogger(__name__)


class ProfitManager:

    def __init__(self, symbol: str, taker_fee, storage=None):
        self.symbol = symbol
        self.taker_fee = taker_fee
        self.storage = storage
        self.cycle_number = 1

        self.cycle_start_time = None
        self.entry_fees = 0.0
        self.exit_fees = 0.0
        self.funding_total = 0.0
        self.last_funding_check = 0
        self.last_funding_time = 0

        if self.storage:
            state = self.storage.get_profit_state(self.symbol)
            if state:
                self.cycle_number    = state.get("cycle_number", 1)
                self.entry_fees      = state.get("entry_fees", 0.0)
                self.funding_total   = state.get("funding_total", 0.0)
                self.cycle_start_time = state.get("cycle_start_time")

        if not self.cycle_start_time:
            logger.warning(f"[{self.symbol}] cycle_start_time missing")

            if self.cycle_number > 0:
                logger.error(f"[{self.symbol}] Active cycle without cycle_start_time — trade history will be broken")
            else:
                self.cycle_start_time = int(time.time() * 1000)

    # ---------------------------
    # Cycle control
    # ---------------------------

    def start_cycle(self, symbol, cycle_number, start_time=None):

        self.cycle_number = cycle_number

        if start_time is not None:
            self.cycle_start_time = start_time
        else:
            self.cycle_start_time = int(time.time() * 1000)

        print(f"[{self.symbol}] CYCLE: {self.cycle_number}")
        self.entry_fees = 0.0
        self.exit_fees = 0.0
        self.funding_total = 0.0
        self.last_funding_time = 0

        print(f"[{self.symbol}] Cycle started at:", self.cycle_start_time)

        if self.storage:
            self.storage.save_profit_state(
                symbol=self.symbol,
                cycle_number=self.cycle_number,
                entry_fees=self.entry_fees,
                funding_total=self.funding_total,
                cycle_start_time=self.cycle_start_time
            )

    def register_entry_order(self, symbol, order):
        entry_fee = order.get("calculated_entry_fee", 0.0)

        if entry_fee:
            print(f"[{self.symbol}] REGISTER ENTRY FEE: {entry_fee}")
            self.entry_fees += float(entry_fee)

            if self.storage:
                self.storage.save_profit_state(
                    symbol=self.symbol,
                    cycle_number=self.cycle_number,
                    entry_fees=self.entry_fees,
                    funding_total=self.funding_total,
                    cycle_start_time=self.cycle_start_time
                )

    # ---------------------------
    # FUNDING
    # ---------------------------

    def add_funding(self, funding: float):
        try:
            self.funding_total += float(funding)
        except Exception:
            pass

    # ---------------------------
    # PROFIT CALCULATION
    # ---------------------------

    def calculate_total_net(self, symbol, long_pos, short_pos, target_profit=None):


        total_unreal = 0

        long_unreal = 0.0
        short_unreal = 0.0

        total_exit_fee = 0

        for pos in [long_pos, short_pos]:
            if pos and float(pos["positionAmt"]) != 0:

                entry = float(pos["entryPrice"])
                mark = float(pos["markPrice"])
                qty = float(pos["positionAmt"])
                if pos["positionSide"] == "LONG":
                    unreal = (mark - entry) * qty
                else:
                    unreal = (entry - mark) * abs(qty)    

                total_unreal += unreal

                if pos["positionSide"] == "LONG":
                    long_unreal = unreal

                if pos["positionSide"] == "SHORT":
                    short_unreal = unreal

                notional = abs(float(pos["positionAmt"])) * float(pos["markPrice"])
                total_exit_fee += notional * self.taker_fee

        total_net = (
            total_unreal
            + self.funding_total
            - self.entry_fees
            - total_exit_fee
        )
        
        print("\n============= POSITION DEBUG =============")

        print(f"[{self.symbol}] LONG  PNL:      {long_unreal:.6f}")
        print(f"[{self.symbol}] SHORT PNL:      {short_unreal:.6f}")

        print("------------------------------------------")

        print(f"[{self.symbol}] UNREAL TOTAL:   {total_unreal:.6f}")

        print("")
        print(f"[{self.symbol}] CYCLE FUNDING:  {self.funding_total:.6f}")
        print(f"[{self.symbol}] ENTRY FEES:     {self.entry_fees:.6f}")
        print(f"[{self.symbol}] EXIT FEES:      {total_exit_fee:.6f}")

        print("------------------------------------------")

        print(f"[{self.symbol}] REAL NET:       {total_net:.6f}")

        print("")
        if target_profit is not None:
            distance = target_profit - total_net
            print(f"[{self.symbol}] TARGET PROFIT:  {target_profit:.6f}")
            print(f"[{self.symbol}] DISTANCE:       {distance:.6f}")

        print("==========================================\n")

        return total_net

    # ---------------------------
    # TARGET CHECK
    # ---------------------------

    def should_close(self, symbol, long_pos, short_pos, target_profit):

        total_net = self.calculate_total_net(symbol, long_pos, short_pos, target_profit)

        print(
            f"[{self.symbol}] TARGET CHECK → NET: {total_net:.6f} / TARGET: {target_profit:.6f}"
        )

        if total_net >= target_profit:
            return True

        return False