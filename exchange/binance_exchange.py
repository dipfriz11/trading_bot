from binance.client import Client
from config import API_KEY, API_SECRET
from .base_exchange import BaseExchange
import math
from decimal import Decimal, ROUND_CEILING


class BinanceExchange(BaseExchange):

    def __init__(self):
        self.client = Client(API_KEY, API_SECRET, testnet=False)
        self.client.ping()

        # Binance Futures fees
        self.taker_fee = 0.0005
        self.maker_fee = 0.0002

        print("Binance exchange initialized")

    # ==============================
    # PRICE
    # ==============================

    def get_price(self, symbol: str) -> float:
        ticker = self.client.futures_symbol_ticker(symbol=symbol)
        return float(ticker["price"])

    def get_server_time(self) -> int:
        return self.client.futures_time()["serverTime"]

    # ==============================
    # SYMBOL INFO
    # ==============================

    def get_symbol_info(self, symbol: str) -> dict:
        exchange_info = self.client.futures_exchange_info()
        return next(
            s for s in exchange_info["symbols"]
            if s["symbol"] == symbol
        )

    def get_symbol_metadata(self, symbol: str) -> dict:
        symbol_info = self.get_symbol_info(symbol)
        lot_size = next(f for f in symbol_info["filters"] if f["filterType"] == "LOT_SIZE")
        min_notional = next(f for f in symbol_info["filters"] if f["filterType"] == "MIN_NOTIONAL")
        return {
            "min_qty":      float(lot_size["minQty"]),
            "step_size":    float(lot_size["stepSize"]),
            "min_notional": float(min_notional["notional"]),
        }

    def round_order_params(self, symbol: str, side: str, quantity: float, price: float) -> tuple:
        symbol_info = self.get_symbol_info(symbol)
        normalized_side = "BUY" if side.upper() in ("BUY", "LONG") else "SELL"
        rounded_qty   = self._round_quantity(symbol_info, quantity)
        rounded_price = self._round_price(symbol_info, price, normalized_side)
        return (rounded_qty, rounded_price)

    # ==============================
    # LEVERAGE
    # ==============================

    def change_leverage(self, symbol: str, leverage: int):
        self.client.futures_change_leverage(
            symbol=symbol,
            leverage=leverage
        )

    # ==============================
    # PLACE MARKET ORDER
    # ==============================

    def place_market_order(self, symbol: str, side: str, quantity: float):
        return self.client.futures_create_order(
            symbol=symbol,
            side=side.upper(),
            type="MARKET",
            quantity=quantity,
            positionSide="LONG" if side.lower() == "buy" else "SHORT"
        )

    # ==============================
    # OPEN POSITION (USDT BASED)
    # ==============================

    def open_market_position(self, symbol: str, side: str, usdt_amount: float, leverage: int):

        price = self.get_price(symbol)

        print(">>>>>>>> BINANCE ORDER PREP >>>>>>>>")
        print("Symbol:", symbol)
        print("Side:", side)
        print("Requested USDT amount:", usdt_amount)
        print("Current price:", price)

        account_info = self.client.futures_account()

        print("Wallet balance:", account_info["totalWalletBalance"])
        print("Available balance:", account_info["availableBalance"])
        print("Total position initial margin:", account_info["totalPositionInitialMargin"])
        print("Total maint margin:", account_info["totalMaintMargin"])

        

        account_full = self.client.futures_account()

        for p in account_full["positions"]:
            if p["symbol"] == symbol:
               print("Leverage set:", p["leverage"])

        symbol_info = self.get_symbol_info(symbol)

        # --- MIN_NOTIONAL ---
        min_notional = next(
            float(f["notional"])
            for f in symbol_info["filters"]
            if f["filterType"] == "MIN_NOTIONAL"
        )

        if usdt_amount < min_notional:
            usdt_amount = min_notional + 1

            print("Adjusted USDT amount (after MIN_NOTIONAL):", usdt_amount)

        # --- LOT_SIZE ---
        step_size = next(
            float(f["stepSize"])
            for f in symbol_info["filters"]
            if f["filterType"] == "LOT_SIZE"
        )


        raw_quantity = Decimal(str(usdt_amount)) / Decimal(str(price))
        step = Decimal(str(step_size))

        quantity = (raw_quantity // step) * step

        print("Raw quantity:", raw_quantity)

        quantity = float(quantity)

        if quantity * price < min_notional:
            quantity += float(step)

        print("Final quantity:", quantity)
        print("PositionSide:", "LONG" if side.lower()=="buy" else "SHORT")
        print("<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<")

        # leverage
        self.change_leverage(symbol, leverage)

        order = self.place_market_order(symbol, side, quantity)

                # ---- CALCULATE ENTRY FEE ----
        notional = float(usdt_amount)
        entry_fee = self.calculate_fee("MARKET", notional)

        print("Entry fee (calculated):", entry_fee)

        order["calculated_entry_fee"] = entry_fee

        # ===== POSITION-LEVEL MARGIN CHECK AFTER ORDER =====
        import time
        time.sleep(0.5)

        positions = self.client.futures_position_information(symbol=symbol)

        print("---- POSITION RISK AFTER ORDER ----")
        for p in positions:
            if float(p["positionAmt"]) != 0:
                print("Symbol:", p["symbol"])
                print("Side:", p["positionSide"])
                print("Position Amt:", p["positionAmt"])
                print("Entry Price:", p["entryPrice"])
                print("Position Initial Margin:", p["positionInitialMargin"])
                print("Maintenance Margin:", p["maintMargin"])
                print("-----------------------")

        return order

        # ==============================
        # CLOSE POSITION (HEDGE MODE)
        # ==============================
    def close_position(self, symbol: str, side: str, quantity: float):

        print(">>>>>> BINANCE CLOSE ORDER >>>>>>")
        print("Symbol:", symbol)
        print("Side:", side)
        print("Quantity:", quantity)

        position_side = "LONG" if side.lower() == "sell" else "SHORT"

        order = self.client.futures_create_order(
            symbol=symbol,
            side=side.upper(),
            type="MARKET",
            quantity=quantity,
            positionSide=position_side,
        )

        print("Close order sent")
        print(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")

        return order
    
        # ==========================================
    # NET PNL (HEDGE MODE)
    # ==========================================

    def get_net_pnl(self, symbol: str) -> float:
        try:
            positions = self.client.futures_position_information(symbol=symbol)

            net_pnl = 0.0

            for pos in positions:
                unrealized = float(pos["unRealizedProfit"])
                net_pnl += unrealized

            return net_pnl

        except Exception as e:
            print("Error getting net PnL:", e)
            return 0.0
        
        # ==========================================
    # CHECK IF POSITIONS EXIST
    # ==========================================

    def has_open_position(self, symbol: str) -> bool:
        try:
             print("\n================ POSITION CHECK ================")
             print("SYMBOL:", symbol)

             positions = self.get_positions(symbol)
             print("RAW POSITIONS FROM EXCHANGE:")
             print(positions)

             for pos in positions:
                 position_amt = float(pos["positionAmt"])
                 print("positionAmt =", position_amt)

                 if abs(position_amt) > 1e-8:
                    print("→ OPEN POSITION DETECTED")
                    return True

             print("→ NO OPEN POSITION")
             return False

        except Exception as e:
             print("Error checking open positions:", e)
             return False
    
    def get_positions(self, symbol: str):
        return self.client.futures_position_information(symbol=symbol)
    
    def get_funding(self, symbol: str, start_time: int):
        return self.client.futures_income_history(
            symbol=symbol,
            incomeType="FUNDING_FEE",
            startTime=start_time,
            limit=100
        )
    
    def open_limit_position(self, symbol: str, side: str, usdt_amount: float, price: float):
        raise NotImplementedError("Limit orders not implemented yet")

    # ==============================
    # LIMIT ORDER MANAGEMENT
    # ==============================

    def _round_price(self, symbol_info: dict, price: float, side: str) -> float:
        tick_size = next(
            float(f["tickSize"])
            for f in symbol_info["filters"]
            if f["filterType"] == "PRICE_FILTER"
        )
        tick = Decimal(str(tick_size))
        price_dec = Decimal(str(price))

        if side.upper() == "BUY":
            return float((price_dec // tick) * tick)
        else:
            return float((price_dec / tick).to_integral_value(rounding=ROUND_CEILING) * tick)

    def _round_quantity(self, symbol_info: dict, quantity: float) -> float:
        step_size = next(
            float(f["stepSize"])
            for f in symbol_info["filters"]
            if f["filterType"] == "LOT_SIZE"
        )
        step = Decimal(str(step_size))
        return float((Decimal(str(quantity)) // step) * step)

    def place_limit_order(self, symbol: str, side: str, quantity: float, price: float, position_side: str = None):
        symbol_info = self.get_symbol_info(symbol)
        price    = self._round_price(symbol_info, price, side)
        quantity = self._round_quantity(symbol_info, quantity)

        params = {
            "symbol": symbol,
            "side": side.upper(),
            "type": "LIMIT",
            "quantity": quantity,
            "price": price,
            "timeInForce": "GTC"
        }

        if not position_side:
            if side.upper() == "BUY":
                position_side = "LONG"
            else:
                position_side = "SHORT"

        params["positionSide"] = position_side

        return self.client.futures_create_order(**params)

    def modify_order(self, symbol: str, order_id: int, side: str, quantity: float, price: float, position_side: str = None):
        symbol_info = self.get_symbol_info(symbol)
        price    = self._round_price(symbol_info, price, side)
        quantity = self._round_quantity(symbol_info, quantity)

        params = {
            "symbol": symbol,
            "orderId": order_id,
            "side": side.upper(),
            "quantity": quantity,
            "price": price
        }

        if not position_side:
            if side.upper() == "BUY":
                position_side = "LONG"
            else:
                position_side = "SHORT"

        params["positionSide"] = position_side

        return self.client.futures_modify_order(**params)

    def cancel_order(self, symbol: str, order_id: int):
        return self.client.futures_cancel_order(
            symbol=symbol,
            orderId=order_id
        )

    def get_order(self, symbol: str, order_id: int):
        return self.client.futures_get_order(
            symbol=symbol,
            orderId=order_id
        )
    
    def calculate_fee(self, order_type: str, notional: float) -> float:
        """
        order_type: "MARKET" or "LIMIT"
        notional: position size in USDT
        """

        if order_type.upper() == "MARKET":
            rate = self.taker_fee
        elif order_type.upper() == "LIMIT":
            rate = self.maker_fee
        else:
            raise ValueError("Unknown order type")

        return notional * rate

    def get_user_trades(self, symbol: str, start_time: int, limit: int = 100):
        """
        Возвращает сделки пользователя с Binance Futures.
        Каждая сделка содержит: price, qty, commission, realizedPnl, side, time.
        """
        return self.client.futures_account_trades(
            symbol=symbol,
            startTime=start_time,
            limit=limit
        )