import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")

LEVERAGE = 10
ORDER_USDT = 20
DRY_RUN = True

COINS = {
    "ETHUSDT": {
        "base_size": 18,
        "target_profit": 1.0,
        "auto_close": True
    },

    "BARDUSDT": {
        "base_size": 12,
        "target_profit": 0.5,
        "auto_close": True
    },

    "SENTUSDT": {
        "base_size": 12,
        "target_profit": 0.5,
        "auto_close": True
    },

    "BANANAS31USDT": {
        "symbol": "BANANAS31USDT",
        "base_size": 18,
        "hedge_ratio": 1.0,
        "major_multiplier": 2.0,
        "minor_multiplier": 0.5,
        "auto_close": True,
        "target_profit": 0.5,
        "repeat_mode": "ignore",
        "max_cycles": 5,
        "max_total_exposure": None
    },

    "DAMUSDT": {
        "base_size": 24,
        "target_profit": 0.5,
        "auto_close": True
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