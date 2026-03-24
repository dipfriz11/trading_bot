from dataclasses import dataclass, field
from typing import Optional


@dataclass
class OrderRequest:
    symbol: str
    side: str                   # "BUY" | "SELL"
    order_type: str             # "market" | "limit" | "stop_limit"
    quantity: float
    price: Optional[float] = None
    params: dict = field(default_factory=dict)
    behavior: Optional[dict] = None  # зарезервировано, пока не используется
