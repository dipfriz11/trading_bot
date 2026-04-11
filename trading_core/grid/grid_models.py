from dataclasses import dataclass, field
from typing import List, Optional
import time
import uuid


# =========================
# GridLevel
# =========================

@dataclass
class GridLevel:
    index: int
    price: float
    qty: float
    position_side: str  # "LONG" | "SHORT"
    status: str = "planned"  # planned | placed | filled | canceled
    order_id: Optional[str] = None
    client_order_id: Optional[str] = None
    use_reset_tp: bool = False
    reset_tp_percent: Optional[float] = None
    reset_tp_close_percent: Optional[float] = None
    slot_index: Optional[int] = None


# =========================
# GridSession
# =========================

@dataclass
class GridSession:
    symbol: str
    position_side: str  # "LONG" | "SHORT"

    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: str = "created"  # created | running | stopped | completed

    levels: List[GridLevel] = field(default_factory=list)

    created_at: float = field(default_factory=time.time)
