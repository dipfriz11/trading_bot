from execution_engine import ExecutionEngine
from exchange.binance_exchange import BinanceExchange
from exchange.mock_exchange import MockExchange
import os
from flask import Flask, request, jsonify
import traceback
import time

from trading_core.position_manager import CycleConfig
from trading_core.symbol_registry import SymbolRegistry
from logger_config import setup_logger
from config import COINS
from storage.sqlite_storage import SQLiteStorage


# =========================
# СОЗДАНИЕ FLASK
# =========================

app = Flask(__name__)
logger = setup_logger()


COOLDOWN_SECONDS = 3


# =========================
# WEBHOOK ROUTE
# =========================

@app.route("/api/hooks/<hook_token>", methods=["POST"])
def webhook(hook_token):

    registry = app.config.get("registry")
    engine = app.config.get("engine")
    storage = app.config.get("storage")

    if registry is None or engine is None or storage is None:
        return jsonify({"error": "server not initialized"}), 500

    try:
        logger.info(f"Incoming webhook request: token={hook_token}")
        if hook_token != os.environ.get("WEBHOOK_TOKEN", "my_token"):
            return jsonify({"error": "Invalid token"}), 403

        data = request.get_json()
        print("DEBUG SECRET VALUE:", repr(data.get("secret")))
        print("DEBUG EXPECTED VALUE:", repr(os.environ.get("WEBHOOK_SECRET", "my_secret")))
        logger.info(f"Webhook payload: {data}")

        if not data:
            return jsonify({"error": "Empty body"}), 400

        if data.get("secret", "").strip() != "my_secret":
            return jsonify({"error": "Invalid secret"}), 403

        side = data.get("side")
        symbol = data.get("symbol")
        logger.info(f"Signal received: {side} {symbol}")

        if not side or not symbol:
            return jsonify({"error": "Missing fields"}), 400

        symbol = symbol.replace(".P", "").upper()
        side = side.lower()

        symbol_cfg = storage.get_symbol(symbol)

        if not symbol_cfg:
            logger.warning(f"[SYMBOL] {symbol} not registered — ignoring signal")
            return jsonify({"status": "ignored", "reason": "symbol_not_registered"})

        if not symbol_cfg["active"]:
            logger.info(f"[SYMBOL] {symbol} inactive — ignoring signal")
            return jsonify({"status": "ignored", "reason": "symbol_inactive"})

        cfg = build_cycle_config(symbol)
        if not cfg:
            logger.warning(f"Symbol not in config: {symbol}. Ignoring webhook.")
            return jsonify({
                "status": "ignored",
                "reason": "symbol_not_in_config",
                "symbol": symbol
            }), 200

        manager = registry.get_manager(symbol)

        # привязываем конфиг этой монеты
        manager.config = cfg    

        # --- Защита от одновременного webhook ---
        if manager.processing:
            logger.warning(f"Signal ignored (processing in progress): {side} for {symbol}")
            return jsonify({
                "status": "ignored",
                "reason": "processing_in_progress",
                "symbol": symbol
            }), 200
        
       
        manager.processing = True
        
                # ---- COOLDOWN CHECK ----
        current_time = time.time()
        last_signal_time = manager.get_state().get("last_signal_time", 0)

        if current_time - last_signal_time < COOLDOWN_SECONDS:
            logger.warning(f"Cooldown active: signal ignored for {symbol}")
            manager.processing = False
            return jsonify({
                "status": "ignored",
                "reason": "cooldown_active",
                "symbol": symbol
            }), 200
        
                 # ----- AUTO SYNC WITH BINANCE -----
        state = manager.get_state()
        has_position = engine.exchange.has_open_position(symbol)
            
        print("DEBUG SYNC CHECK:",
            "cycle_active=", state.get("cycle_active"),
            "has_position=", has_position)
            
        if state.get("cycle_active") and not has_position:
            logger.warning(f"[SYNC] Manual close detected for {symbol} — resetting cycle before new signal")
            manager.reset_cycle()
            engine.last_sizes.pop(symbol, None)
            registry._save_state()
            state = manager.get_state()

        accepted = manager.apply_signal(side)

        if not accepted:
            manager.processing = False
            return jsonify({
                "status": "ignored",
                "reason": "repeat_signal"
            }), 200

        manager.last_signal_time = time.time()

        registry._save_state()

        state = manager.get_state()

        logger.info(f"Executing order for {symbol} | side={side} | state={state}")
        engine.execute(symbol, side, state)

                    # ---- DEBUG: NET PNL ----
        net_pnl = engine.exchange.get_net_pnl(symbol)
        print(f"DEBUG NET PNL for {symbol}: {net_pnl}")
        
        logger.info(f"Execution complete for {symbol}")

        manager.processing = False

        return jsonify({
            "status": "ok",
            "symbol": symbol,
            "state": state
        }), 200

    except Exception as e:
        logger.exception("Unhandled exception in webhook")

        if "manager" in locals():
            manager.processing = False

        return jsonify({
            "error": str(e),
            "trace": traceback.format_exc()
        }), 500


@app.route("/api/state", methods=["GET"])
def get_all_state():

    registry = app.config.get("registry")

    if registry is None:
        return jsonify({"error": "server not initialized"}), 500

    return jsonify(registry.get_all_states()), 200


@app.route("/api/reset/<symbol>", methods=["POST"])
def reset_symbol(symbol):

    registry = app.config.get("registry")

    if registry is None:
        return jsonify({"error": "server not initialized"}), 500

    symbol = symbol.replace(".P", "").upper()

    manager = registry.get_manager(symbol)
    manager.reset_cycle()

    return jsonify({
        "status": "reset_done",
        "symbol": symbol
    }), 200


def build_cycle_config(symbol: str) -> CycleConfig:
    coin = COINS.get(symbol)
    if not coin:
        return None

    return CycleConfig(
        base_size=coin["base_size"],
        hedge_ratio=coin["hedge_ratio"],
        major_multiplier=coin["major_multiplier"],
        minor_multiplier=coin["minor_multiplier"],
        target_profit=coin["target_profit"],
        auto_close=coin["auto_close"],
        repeat_mode=coin["repeat_mode"],
        max_cycles=coin["max_cycles"],
        max_total_exposure=coin["max_total_exposure"],
        leverage=coin["leverage"]
    )

# =========================
# ИНИЦИАЛИЗАЦИЯ И ЗАПУСК
# =========================

def initialize():

    logger.info("STEP 1: Reading env variables")

    PORT = int(os.environ.get("PORT", 5000))
    EXCHANGE_TYPE = os.environ.get("EXCHANGE_TYPE", "binance")

    logger.info("STEP 2: Creating strategy config")

    default_symbol = next(iter(COINS.keys()), None)
    base_config = build_cycle_config(default_symbol) if default_symbol else None

    logger.info("STEP 3: Creating registry")
    registry = SymbolRegistry(base_config)

    app.config["registry"] = registry

    logger.info("STEP 4: Creating exchange")

    if EXCHANGE_TYPE == "mock":
        exchange = MockExchange()
    else:
        exchange = BinanceExchange()

    logger.info("STEP 5: Creating execution engine")
    engine = ExecutionEngine(exchange, registry)

    storage = SQLiteStorage("bot.db")
    app.config["storage"] = storage

    active_symbols = storage.get_active_symbols()
    logger.info(f"Loading active symbols from DB: {len(active_symbols)}")

    for s in active_symbols:
        symbol = s["symbol"]
        registry.get_manager(symbol)
        logger.info(f"Symbol manager initialized: {symbol}")

    logger.info("STEP 6: Restoring price monitors")
    engine.restore_price_monitor()

    app.config["engine"] = engine

    logger.info("STEP 7: Initialization complete")

    return PORT


if __name__ == "__main__":

    logger.info("SERVER STARTING...")

    port = initialize()

    print(f"RUNNING ON PORT {port}")

    app.run(host="0.0.0.0", port=port, debug=False)