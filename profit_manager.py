import time
from config import COINS, get_target_profit


class ProfitManager:

    def __init__(self, exchange, taker_fee):
        self.exchange = exchange
        self.taker_fee = taker_fee
        self.target_profit = 0
        self.cycle_number = 1

        self.cycle_start_time = None
        self.entry_fees = 0.0
        self.exit_fees = 0.0
        self.funding_total = 0.0
        self.last_funding_check = 0
        self.last_funding_time = 0

    # ---------------------------
    # Cycle control
    # ---------------------------

    def start_cycle(self, symbol, cycle_number):

        self.cycle_number = cycle_number
        self.target_profit = get_target_profit(symbol, self.cycle_number)

        print(f"CYCLE: {self.cycle_number} | TARGET PROFIT: {self.target_profit}")

        self.cycle_start_time = int(time.time() * 1000)
        self.entry_fees = 0.0
        self.exit_fees = 0.0
        self.funding_total = 0.0
        self.last_funding_time = 0

        print("Cycle started at:", self.cycle_start_time)
    
    def register_entry_order(self, symbol, order):
        entry_fee = order.get("calculated_entry_fee", 0.0)

        if entry_fee:
            print(f"REGISTER ENTRY FEE: {entry_fee}")
            self.entry_fees += float(entry_fee)

    # ---------------------------
    # FUNDING
    # ---------------------------

    def update_funding(self, symbol):

        if self.cycle_start_time is None:
            return

        now = time.time()

        cycle_start_ms = self.cycle_start_time

        if self.last_funding_check is None:
            self.last_funding_check = now - 31

        # проверяем не чаще чем раз в 30 секунд
        if now - self.last_funding_check < 30:
             return

        incomes = self.exchange.get_funding(symbol, cycle_start_ms)
        print("RAW FUNDING INCOME:", incomes)

        new_last_time = self.last_funding_time

        for inc in incomes:

            if inc["incomeType"] != "FUNDING_FEE":
                 continue           
            
            if inc["time"] <= self.last_funding_time:
                continue

            funding_value = float(inc["income"])

            print("----- FUNDING EVENT -----")
            print("FUNDING EVENT:", funding_value)

            self.funding_total += funding_value

            print("CYCLE FUNDING TOTAL:", self.funding_total)
            print("-------------------------")

            if inc["time"] > new_last_time:
                new_last_time = inc["time"]

        self.last_funding_time = new_last_time        


        self.last_funding_check = now

    # ---------------------------
    # PROFIT CALCULATION
    # ---------------------------

    def calculate_total_net(self, symbol, long_pos, short_pos):


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
        
        distance = self.target_profit - total_net

        print("\n============= POSITION DEBUG =============")

        print(f"LONG  PNL:      {long_unreal:.6f}")
        print(f"SHORT PNL:      {short_unreal:.6f}")

        print("------------------------------------------")

        print(f"UNREAL TOTAL:   {total_unreal:.6f}")

        print("")
        print(f"CYCLE FUNDING:  {self.funding_total:.6f}")
        print(f"ENTRY FEES:     {self.entry_fees:.6f}")
        print(f"EXIT FEES:      {total_exit_fee:.6f}")

        print("------------------------------------------")

        print(f"REAL NET:       {total_net:.6f}")

        print("")
        print(f"TARGET PROFIT:  {self.target_profit:.6f}")
        print(f"DISTANCE:       {distance:.6f}")

        print("==========================================\n")

        return total_net

    # ---------------------------
    # TARGET CHECK
    # ---------------------------

    def should_close(self, symbol, long_pos, short_pos):

        total_net = self.calculate_total_net(symbol, long_pos, short_pos)

        print(
            f"TARGET CHECK → NET: {total_net:.6f} / TARGET: {self.target_profit:.6f}"
        )

        if total_net >= self.target_profit:
            return True

        return False