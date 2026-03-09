import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")

DRY_RUN = True

COINS = {
    "ETHUSDT": {
        "base_size": 12,
        "hedge_ratio": 0.5,
        "major_multiplier": 2.0,
        "minor_multiplier": 0.5,
        "auto_close": True,
        "target_profit": 0.5,
        "repeat_mode": "ignore",
        "max_cycles": 5,
        "max_total_exposure": None,
        "leverage": 10
    },

    "BARDUSDT": {
        "base_size": 12,
        "hedge_ratio": 1.0,
        "major_multiplier": 2.0,
        "minor_multiplier": 0.5,
        "auto_close": True,
        "target_profit": 0.5,
        "repeat_mode": "ignore",
        "max_cycles": 5,
        "max_total_exposure": None,
        "leverage": 10
    },

    "SENTUSDT": {
        "base_size": 12,
        "hedge_ratio": 0.5,
        "major_multiplier": 2.0,
        "minor_multiplier": 0.5,
        "auto_close": True,
        "target_profit": 0.5,
        "repeat_mode": "ignore",
        "max_cycles": 5,
        "max_total_exposure": None,
        "leverage": 10
    },

    "BANANAS31USDT": {
        "base_size": 12,
        "hedge_ratio": 0.5,
        "major_multiplier": 2.0,
        "minor_multiplier": 0.5,
        "auto_close": True,
        "target_profit": 0.5,
        "repeat_mode": "ignore",
        "max_cycles": 5,
        "max_total_exposure": None,
        "leverage": 10
    },

    "DAMUSDT": {
        "base_size": 12,
        "hedge_ratio": 0.5,
        "major_multiplier": 2.0,
        "minor_multiplier": 0.5,
        "auto_close": True,
        "target_profit": 0.5,
        "repeat_mode": "ignore",
        "max_cycles": 5,
        "max_total_exposure": None,
        "leverage": 10
    }
}

def get_target_profit(symbol, cycle_number):
    coin = COINS.get(symbol)

    if not coin:
        return 0

    target = coin.get("target_profit", 0)

    # если число
    if isinstance(target, (int, float)):
        return target

    # если словарь по циклам
    if isinstance(target, dict):

        # точное совпадение
        if cycle_number in target:
            return target[cycle_number]

        # если цикл больше последнего ключа
        max_cycle = max(target.keys())
        if cycle_number > max_cycle:
            return target[max_cycle]

    return 0

def get_coin_config(symbol: str) -> dict:

    coin = COINS.get(symbol)

    if not coin:
        raise ValueError(f"Symbol {symbol} not configured in COINS")

    return coin