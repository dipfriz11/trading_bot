from dataclasses import dataclass, field
from typing import List, Optional
import time
import uuid

ALLOWED_CUSTOM_PRICE_MODES = {
    "offset_from_reference",
    "offset_from_previous",
    "fixed_price",
}


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


@dataclass
class CustomGridLevelConfig:
    index: int
    price_mode: str
    price_value: float
    size_weight: float
    use_reset_tp: bool = False
    reset_tp_percent: Optional[float] = None
    reset_tp_close_percent: Optional[float] = None

    def __post_init__(self) -> None:
        if self.index < 1:
            raise ValueError(f"CustomGridLevelConfig.index must be >= 1, got {self.index}")
        if self.price_mode not in ALLOWED_CUSTOM_PRICE_MODES:
            raise ValueError(
                f"Unsupported price_mode: {self.price_mode!r}. "
                f"Expected one of {sorted(ALLOWED_CUSTOM_PRICE_MODES)}"
            )
        if self.price_value <= 0:
            raise ValueError(f"price_value must be > 0, got {self.price_value}")
        if self.size_weight <= 0:
            raise ValueError(f"size_weight must be > 0, got {self.size_weight}")
        if self.use_reset_tp:
            if self.reset_tp_percent is None or self.reset_tp_percent <= 0:
                raise ValueError("reset_tp_percent must be set and > 0 when use_reset_tp=True")
            if self.reset_tp_close_percent is None or not (0 < self.reset_tp_close_percent <= 100):
                raise ValueError("reset_tp_close_percent must be set and in (0, 100] when use_reset_tp=True")


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
