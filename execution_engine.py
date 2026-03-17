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
        self.mark_price = {}
        self.last_total_net = {}
        self.price_socket_thread = {}
        self.ws = {}
        self.stop_requested = {}


    def start_price_monitor(self, symbol: str):

        if self.price_socket_thread.get(symbol):
            return

        self.current_symbol = symbol

        def on_message(ws, message):
            data = json.loads(message)

            if "p" in data:
                self.mark_price[symbol] = float(data["p"])

                # Проверяем закрытие НА КАЖДОМ ТИКЕ
                self.check_close_condition(symbol)

                manager = self.symbol_registry.get_manager(symbol)
                if not manager:
                    return

                print()
                print("===== CYCLE INFO =====")
                print(f"CYCLE: {manager.cycle_number}")
                print(f"TARGET PROFIT: {manager.cycle_target_profit}")
                print("======================")

        def on_error(ws, error):
            logger.error(f"WebSocket error: {error}")

        def on_close(ws, close_status_code, close_msg):
            if self.stop_requested.get(symbol):
                logger.info("WebSocket closed intentionally. No reconnect.")
                self.stop_requested[symbol] = False
                return
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
        self.ws[symbol] = ws

        self.price_socket_thread[symbol] = threading.Thread(target=ws.run_forever)
        self.price_socket_thread[symbol].daemon = True
        self.price_socket_thread[symbol].start()

        logger.info(f"Started mark price monitor for {symbol}")

    def restore_price_monitor(self):
        for symbol, manager in self.symbol_registry.registry.items():
            state = manager.get_state()
            has_position = self.exchange.has_open_position(symbol)

            # CASE 1: state says active but no position on exchange
            if state.get("cycle_active") and not has_position:
                logger.warning(f"[BOOT SYNC] State mismatch detected for {symbol}: cycle_active=True but no exchange position. Resetting cycle.")
                manager.reset_cycle()
                self.last_sizes.pop(symbol, None)
                continue

            # CASE 2: position exists but cycle is inactive
            if not state.get("cycle_active") and has_position:
                logger.warning(f"[BOOT SYNC] Exchange position exists but cycle is inactive for {symbol}")

            if not state.get("cycle_active"):
                continue

            self.last_sizes[symbol] = {
                "long": state["long_size"],
                "short": state["short_size"]
            }

            logger.info(f"[BOOT SYNC] Restoring price monitor for {symbol}")
            self.start_price_monitor(symbol)

    def check_close_condition(self, symbol: str):

        if not self.mark_price.get(symbol):
            return

        positions = self.exchange.get_positions(symbol)

        long_pos = None
        short_pos = None

        for p in positions:
            if p["positionSide"] == "LONG" and float(p["positionAmt"]) != 0:
                long_pos = p
            if p["positionSide"] == "SHORT" and float(p["positionAmt"]) != 0:
                short_pos = p

        # manual close detection
        manager = self.symbol_registry.get_manager(symbol)

        if not long_pos and not short_pos:

            if manager.get_state().get("cycle_active"):
                logger.warning(f"[AUTO SYNC] Manual close detected for {symbol}")
                self.handle_manual_close(symbol)

            return

        # UPDATE FUNDING
        pm = manager.profit_manager
        if pm.cycle_start_time is not None:
            now = time.time()
            if pm.last_funding_check == 0:
                pm.last_funding_check = now - 31
            if now - pm.last_funding_check >= 30:
                try:
                    incomes = self.exchange.get_funding(symbol, pm.cycle_start_time)
                except Exception as e:
                    print(f"[FUNDING ERROR] {symbol}: {e}")
                    return
                print("RAW FUNDING INCOME:", incomes)
                new_last_time = pm.last_funding_time
                for inc in incomes:
                    if inc["incomeType"] != "FUNDING_FEE":
                        continue
                    if inc["time"] <= pm.last_funding_time:
                        continue
                    try:
                        funding_value = float(inc["income"])
                    except Exception:
                        continue
                    print("----- FUNDING EVENT -----")
                    print("FUNDING EVENT:", funding_value)
                    pm.add_funding(funding_value)
                    print("CYCLE FUNDING TOTAL:", pm.funding_total)
                    print("-------------------------")
                    if inc["time"] > new_last_time:
                        new_last_time = inc["time"]
                pm.last_funding_time = new_last_time
                pm.last_funding_check = now

        total_net = manager.profit_manager.calculate_total_net(
            symbol,
            long_pos,
            short_pos
        )

        # печатаем только если total_net изменился
        if self.last_total_net.get(symbol) is None or abs(total_net - self.last_total_net.get(symbol)) > 0.000001:

            print("----- PROFIT DEBUG -----")
            print("TOTAL NET:", total_net)
            print("------------------------")

            self.last_total_net[symbol] = total_net

        # TARGET HIT
        if total_net >= manager.cycle_target_profit:

            print("====== CYCLE CLOSED ======")
            print("FINAL NET:", total_net)
            print("ENTRY FEES:", manager.profit_manager.entry_fees)
            print("FUNDING:", manager.profit_manager.funding_total)
            print("==========================")

            logger.info(f"TARGET HIT: {total_net} — closing position")

            if long_pos:
                self.exchange.close_position(
                    symbol,
                    "sell",
                    abs(float(long_pos["positionAmt"]))
                )

            if short_pos:
                self.exchange.close_position(
                    symbol,
                    "buy",
                    abs(float(short_pos["positionAmt"]))
                )

            # ждём реального закрытия позиций на бирже
            symbol_to_check = symbol
            for attempt in range(10):
                time.sleep(1)
                if not self.exchange.has_open_position(symbol_to_check):
                    logger.info(f"Positions confirmed closed for {symbol_to_check}")
                    break
                logger.warning(f"Waiting for positions to close... attempt {attempt + 1}/10")
            else:
                logger.error(f"Positions NOT closed after 10 attempts for {symbol_to_check}")

            # расчёт реального результата цикла
            trades = self.exchange.get_user_trades(symbol_to_check, manager.profit_manager.cycle_start_time)
            realized_pnl = sum(float(t["realizedPnl"]) for t in trades)
            exit_fees = sum(float(t["commission"]) for t in trades)
            cycle_profit = (
                realized_pnl
                + manager.profit_manager.funding_total
                - manager.profit_manager.entry_fees
            )

            print("\n========== REAL CYCLE RESULT ==========")
            print(f"REALIZED PNL:   {realized_pnl:.6f}")
            print(f"FUNDING:        {manager.profit_manager.funding_total:.6f}")
            print(f"ENTRY FEES:     {manager.profit_manager.entry_fees:.6f}")
            print(f"EXIT FEES:      {exit_fees:.6f}")
            print("----------------------------------------")
            print(f"CYCLE PROFIT:   {cycle_profit:.6f}")
            print("========================================\n")
            logger.info(f"CYCLE PROFIT for {symbol_to_check}: {cycle_profit:.6f}")

            # сбрасываем состояние после закрытия
            self.last_total_net[symbol] = None
            self.price_socket_thread[symbol] = None

    def execute(self, symbol: str, side: str, state: dict):
        manager = self.symbol_registry.get_manager(symbol)
        logger.info(f"--- EXECUTION {symbol} | {side} ---")

        prev_long = self.last_sizes.get(symbol, {}).get("long", 0)
        prev_short = self.last_sizes.get(symbol, {}).get("short", 0)

        # === AUTO MANUAL CLOSE DETECTION ===
        state = manager.get_state()
        has_position = self.exchange.has_open_position(symbol)

        if state.get("cycle_active") and (prev_long > 0 or prev_short > 0) and not has_position:
            logger.warning(f"[AUTO SYNC] Manual close detected for {symbol}")
            self.handle_manual_close(symbol)
            return

        new_long = state["long_size"]
        new_short = state["short_size"]

        # === СТАРТ ЦИКЛА ===
        if state["cycle_number"] == 1:
            logger.info("Starting new cycle with hedge")
            self.start_price_monitor(symbol)
            manager.profit_manager.start_cycle(symbol, state["cycle_number"])

            if new_short > 0:
                logger.info(f"Opening SHORT {new_short} USDT")

                print("========== ORDER DEBUG (START) ==========")
                print("Signal:", side)
                print("Opening SHORT FULL:", new_short)
                print("State LONG:", state["long_size"])
                print("State SHORT:", state["short_size"])
                print("=========================================")

                order = self.exchange.open_market_position(
                    symbol,
                    "sell",
                    new_short,
                    manager.config.leverage
                )
                manager.profit_manager.register_entry_order(symbol, order)

            if new_long > 0:
                logger.info(f"Opening LONG {new_long} USDT")

                print("========== ORDER DEBUG (START) ==========")
                print("Signal:", side)
                print("Opening SHORT FULL:", new_long)
                print("State LONG:", state["long_size"])
                print("State SHORT:", state["short_size"])
                print("=========================================")

                order = self.exchange.open_market_position(
                    symbol,
                    "buy",
                    new_long,
                    manager.config.leverage
                )
                manager.profit_manager.register_entry_order(symbol, order)

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

                order = self.exchange.open_market_position(
                    symbol,
                    "buy",
                    delta_long,
                    manager.config.leverage
                )
                manager.profit_manager.register_entry_order(symbol, order)

            if delta_short > 0:
                logger.info(f"Averaging SHORT +{delta_short} USDT")

                print("========== ORDER DEBUG ==========")
                print("Signal:", side)
                print("Delta LONG:", delta_long)
                print("Delta SHORT:", delta_short)
                print("State LONG:", state["long_size"])
                print("State SHORT:", state["short_size"])
                print("=================================")

                order = self.exchange.open_market_position(
                    symbol,
                    "sell",
                    delta_short,
                    manager.config.leverage
                )
                manager.profit_manager.register_entry_order(symbol, order)

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

        total_net = manager.profit_manager.calculate_total_net(symbol, long_pos, short_pos)

        print("------ PROFIT DEBUG ------")
        print("ENTRY FEES:", manager.profit_manager.entry_fees)
        print("CYCLE FUNDING:", manager.profit_manager.funding_total)
        print("TOTAL NET:", total_net)
        print("--------------------------")

        # ===== CLOSE CHECK =====
        if manager.profit_manager.should_close(symbol, long_pos, short_pos):

            print("TARGET PROFIT REACHED -> CLOSING POSITIONS")

            manager.report_cycle_close(
                symbol,
                "TARGET_PROFIT",
                total_net,
                manager.profit_manager.funding_total,
                manager.profit_manager.entry_fees,
                manager.profit_manager.exit_fees
            )

            if long_pos:
                self.exchange.close_position(
                    symbol,
                    "sell",
                    abs(float(long_pos["positionAmt"]))
                )

            if short_pos:
                self.exchange.close_position(
                    symbol,
                    "buy",
                    abs(float(short_pos["positionAmt"]))
                )

        logger.info(f"Execution complete for {symbol}")

    def handle_manual_close(self, symbol: str):
        symbol_to_check = symbol
        manager = self.symbol_registry.get_manager(symbol)
        trades = self.exchange.get_user_trades(symbol_to_check, manager.profit_manager.cycle_start_time)
        realized_pnl = sum(float(t["realizedPnl"]) for t in trades)
        exit_fees = sum(float(t["commission"]) for t in trades)
        cycle_profit = (
            realized_pnl
            + manager.profit_manager.funding_total
            - manager.profit_manager.entry_fees
        )

        print("\n========== REAL CYCLE RESULT ==========")
        print(f"REALIZED PNL:   {realized_pnl:.6f}")
        print(f"FUNDING:        {manager.profit_manager.funding_total:.6f}")
        print(f"ENTRY FEES:     {manager.profit_manager.entry_fees:.6f}")
        print("(EXIT FEES already included in realized PnL)")
        print("----------------------------------------")
        print(f"CYCLE PROFIT:   {cycle_profit:.6f}")
        print("========================================\n")
        logger.info(f"CYCLE PROFIT for {symbol_to_check}: {cycle_profit:.6f}")

        manager = self.symbol_registry.get_manager(symbol)
        manager.reset_cycle()
        self.last_sizes.pop(symbol, None)

        self.stop_requested[symbol] = True

        if self.ws.get(symbol):
            self.ws[symbol].close()
            self.ws[symbol] = None

        self.price_socket_thread[symbol] = None