# single_order_config.py
#
# Конфиги символов исключительно для SingleOrderStrategy.
# Не смешивать с config.py (hedge/перекос стратегия).
#
# Поля market-entry:
#   entry_type  — "market" | "limit"
#   usdt_amount — размер позиции в USDT (для market entry)
#   amount      — количество монет (для limit entry)
#   distance    — отступ в % от цены (для limit entry)
#   tp_percent  — TP от entry price в %
#   sl_percent  — SL от entry price в %
#   leverage    — кредитное плечо

SINGLE_ORDER_COINS = {
    "SIRENUSDT": {
        "entry_type": "market",
        "leverage":   5,
        # per-side конфиги — если нет, стратегия ищет поля на верхнем уровне
        "long": {
            "usdt_amount": 8.5,
            "tp_percent":  2.0,
            "sl_percent":  1.5,
        },
        "short": {
            "usdt_amount": 8.5,
            "tp_percent":  2.0,
            "sl_percent":  1.5,
        },
    },
}
