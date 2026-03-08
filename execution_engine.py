import time
import threading
import websocket
import json

from logger_config import setup_logger

logger = setup_logger()


class ExecutionEngine:

    def __init__(self, exchange, symbol_registry):
        self.exchange = exchange
        self.symbol_registry = symbol_registry
        self.last_sizes = {}
        self.current_symbol = None
        self.current_long_qty = 0.0
        self.current_short_qty = 0.0
        self.mark_price = 0.0
        self.last_total_net = None
        self.price_socket_thread = None

        from profit_manager import ProfitManager

        self.profit_manager = ProfitManager(
             exchange=self.exchange,
             taker_fee=0.0004
        )

    def start_price_monitor(self, symbol: str):

        if self.price_socket_thread:
            return
        
        self.current_symbol = symbol

        def on_message(ws, message):
            data = json.loads(message)

            if "p" in data:
                self.mark_price = float(data["p"])

                # Проверяем закрытие НА КАЖДОМ ТИКЕ
                self.check_close_condition()

                if not self.current_symbol:
                    return

                manager = self.symbol_registry.get_manager(self.current_symbol)
                if not manager:
                    return

                print()
                print("===== CYCLE INFO =====")
                print(f"CYCLE: {manager.cycle_number}")
                print(f"TARGET PROFIT: {manager.config.target_profit}")
                print("======================")

        def on_error(ws, error):
            logger.error(f"WebSocket error: {error}")

        def on_close(ws, close_status_code, close_msg):
            logger.warning("WebSocket closed. Reconnecting in 3 seconds...")
            time.sleep(3)
            self.start_price_monitor(symbol)

        url = f"wss://fstream.binance.com/ws/{symbol.lower()}@markPrice"

        ws = websocket.WebSocketApp(
          url,
          on_message=on_message,
          on_error=on_error,
          on_close=on_close
        )

        self.price_socket_thread = threading.Thread(target=ws.run_forever)
        self.price_socket_thread.daemon = True
        self.price_socket_thread.start()

        logger.info(f"Started mark price monitor for {symbol}")

    def check_close_condition(self):

        if not self.current_symbol:
            return

        if self.mark_price == 0:
            return

        positions = self.exchange.get_positions(self.current_symbol)

        long_pos = None
        short_pos = None

        for p in positions:
            if p["positionSide"] == "LONG" and float(p["positionAmt"]) != 0:
                long_pos = p
            if p["positionSide"] == "SHORT" and float(p["positionAmt"]) != 0:
                short_pos = p

        # если позиций нет — выходим
        if not long_pos and not short_pos:
            return
        
        # UPDATE FUNDING
        self.profit_manager.update_funding(self.current_symbol)

        total_net = self.profit_manager.calculate_total_net(
            self.current_symbol,
            long_pos,
            short_pos
        )

        # печатаем только если total_net изменился
        if self.last_total_net is None or abs(total_net - self.last_total_net) > 0.000001:

            print("----- PROFIT DEBUG -----")
            print("TOTAL NET:", total_net)
            print("------------------------")

            self.last_total_net = total_net

        # TARGET HIT
        if total_net >= self.profit_manager.target_profit:

            print("====== CYCLE CLOSED ======")
            print("FINAL NET:", total_net)
            print("ENTRY FEES:", self.profit_manager.entry_fees)
            print("FUNDING:", self.profit_manager.funding_total)
            print("==========================")

            logger.info(f"TARGET HIT: {total_net} — closing position")

            if long_pos:
                self.exchange.close_position(
                    self.current_symbol,
                    "sell",
                    abs(float(long_pos["positionAmt"]))
                )

            if short_pos:
                self.exchange.close_position(
                    self.current_symbol,
                    "buy",
                    abs(float(short_pos["positionAmt"]))
                ) 

            # сбрасываем состояние после закрытия
            self.current_symbol = None
            self.last_total_net = None
            self.price_socket_thread = None

    def execute(self, symbol: str, side: str, state: dict):
        logger.info(f"--- EXECUTION {symbol} | {side} ---")

        prev_long = self.last_sizes.get(symbol, {}).get("long", 0)
        prev_short = self.last_sizes.get(symbol, {}).get("short", 0)

        new_long = state["long_size"]
        new_short = state["short_size"]

        # === СТАРТ ЦИКЛА ===
        if state["cycle_number"] == 1:
            logger.info("Starting new cycle with hedge")
            self.start_price_monitor(symbol)
            self.profit_manager.start_cycle(symbol, state["cycle_number"])

            if new_short > 0:
                logger.info(f"Opening SHORT {new_short} USDT")

                print("========== ORDER DEBUG (START) ==========")
                print("Signal:", side)
                print("Opening SHORT FULL:", new_short)
                print("State LONG:", state["long_size"])
                print("State SHORT:", state["short_size"])
                print("=========================================")

                order = self.exchange.open_market_position(symbol, "sell", new_short)
                self.profit_manager.register_entry_order(symbol, order)

            if new_long > 0:
                logger.info(f"Opening LONG {new_long} USDT")

                print("========== ORDER DEBUG (START) ==========")
                print("Signal:", side)
                print("Opening SHORT FULL:", new_long)
                print("State LONG:", state["long_size"])
                print("State SHORT:", state["short_size"])
                print("=========================================")

                order = self.exchange.open_market_position(symbol, "buy", new_long)
                self.profit_manager.register_entry_order(symbol, order)

        # === УСРЕДНЕНИЕ ===
        else:
            delta_long = round(new_long - prev_long, 4)
            delta_short = round(new_short - prev_short, 4)

            if delta_long > 0:
                logger.info(f"Averaging LONG +{delta_long} USDT")

                print("========== ORDER DEBUG ==========")
                print("Signal:", side)
                print("Delta LONG:", delta_long)
                print("Delta SHORT:", delta_short)
                print("State LONG:", state["long_size"])
                print("State SHORT:", state["short_size"])
                print("=================================")

                order = self.exchange.open_market_position(symbol, "buy", delta_long)
                self.profit_manager.register_entry_order(symbol, order)

            if delta_short > 0:
                logger.info(f"Averaging SHORT +{delta_short} USDT")

                print("========== ORDER DEBUG ==========")
                print("Signal:", side)
                print("Delta LONG:", delta_long)
                print("Delta SHORT:", delta_short)
                print("State LONG:", state["long_size"])
                print("State SHORT:", state["short_size"])
                print("=================================")

                order = self.exchange.open_market_position(symbol, "sell", delta_short)
                self.profit_manager.register_entry_order(symbol, order)

        # Сохраняем текущие размеры
        self.last_sizes[symbol] = {
            "long": new_long,
            "short": new_short
        }

        # ===== SAFE PROFIT CHECK =====

        positions = self.exchange.client.futures_position_information(symbol=symbol)

        long_pos = None
        short_pos = None

        for p in positions:
            if p["positionSide"] == "LONG" and float(p["positionAmt"]) != 0:
                long_pos = p
            if p["positionSide"] == "SHORT" and float(p["positionAmt"]) != 0:
                short_pos = p

        total_net = self.profit_manager.calculate_total_net(symbol, long_pos, short_pos)

        manager = self.symbol_registry.get_manager(symbol)

        print("------ PROFIT DEBUG ------")
        print("ENTRY FEES:", self.profit_manager.entry_fees)
        print("CYCLE FUNDING:", self.profit_manager.funding_total)
        print("TOTAL NET:", total_net)
        print("--------------------------")

        # ===== CLOSE CHECK =====
        if self.profit_manager.should_close(symbol, long_pos, short_pos):

            print("TARGET PROFIT REACHED -> CLOSING POSITIONS")

            manager = self.symbol_registry.get_manager(symbol)

            manager.report_cycle_close(
                symbol,
                "TARGET_PROFIT",
                total_net,
                self.profit_manager.funding_total,
                self.profit_manager.entry_fees,
                self.profit_manager.exit_fees
            )

            if long_pos:
                self.exchange.open_market_position(symbol, "sell", abs(float(long_pos["positionAmt"])))

            if short_pos:
                self.exchange.open_market_position(symbol, "buy", abs(float(short_pos["positionAmt"])))        

        logger.info(f"Execution complete for {symbol}")