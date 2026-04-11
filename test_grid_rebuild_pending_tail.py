"""
test_grid_rebuild_pending_tail.py

Unit-style isolated test for GridService.rebuild_pending_tail(symbol, position_side).
Pair: SIRENUSDT @ ~0.57066

Uses FakeExchange and manually constructed session state — no real exchange calls.
Both tests are expected to FAIL with AttributeError until rebuild_pending_tail is implemented.
"""

from trading_core.grid.grid_models import GridLevel, GridSession
from trading_core.grid.grid_builder import GridBuilder
from trading_core.grid.grid_runner import GridRunner
from trading_core.grid.grid_registry import GridRegistry
from trading_core.grid.grid_service import GridService
from trading_core.grid.grid_sizer import GridSizer


# ─────────────────────────────────────────────────────────────
# FakeExchange
# ─────────────────────────────────────────────────────────────

class FakeExchange:
    """
    Minimal fake exchange for rebuild_pending_tail tests.
    Tracks cancel_order and place_limit_order calls for assertions.
    round_to_zero=True makes round_order_params return qty=0.0,
    which forces the extreme order check to fail.
    """

    def __init__(
        self,
        entry_price: float,
        position_qty: float,
        position_side: str = "LONG",
        min_qty: float = 1.0,
        min_notional: float = 5.0,
        step_size: float = 1.0,
        round_to_zero: bool = False,
    ):
        self._entry_price   = entry_price
        self._position_qty  = position_qty
        self._position_side = position_side
        self._min_qty       = min_qty
        self._min_notional  = min_notional
        self._step_size     = step_size
        self._round_to_zero = round_to_zero

        self.cancelled_orders    = []   # list of str(order_id)
        self.placed_limit_orders = []   # list of dicts
        self._next_order_id      = 2000

    def get_positions(self, symbol: str):
        return [{
            "positionSide": self._position_side,
            "entryPrice":   str(self._entry_price),
            "positionAmt":  str(self._position_qty),
        }]

    def get_symbol_metadata(self, symbol: str) -> dict:
        return {
            "min_qty":      self._min_qty,
            "min_notional": self._min_notional,
            "step_size":    self._step_size,
        }

    def round_order_params(self, symbol: str, side: str, qty: float, price: float):
        if self._round_to_zero:
            return (0.0, price)
        return (round(qty), round(price, 5))   # SIREN: whole coins, 5 decimal price

    def normalize_qty(self, symbol: str, qty: float) -> float:
        return 0.0 if self._round_to_zero else round(qty)

    def normalize_price(self, symbol: str, side: str, price: float) -> float:
        return round(price, 5)

    def cancel_order(self, symbol: str, order_id):
        self.cancelled_orders.append(str(order_id))

    def cancel_algo_order(self, algo_id: int):
        pass

    def place_limit_order(self, symbol: str, side: str, quantity: float,
                          price: float, position_side: str = None) -> dict:
        oid = self._next_order_id
        self._next_order_id += 1
        self.placed_limit_orders.append({
            "symbol":   symbol,
            "side":     side,
            "quantity": quantity,
            "price":    price,
        })
        return {"orderId": oid, "clientOrderId": f"fake_{oid}"}

    def get_price(self, symbol: str) -> float:
        return self._entry_price


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _make_service(exchange) -> GridService:
    return GridService(
        builder  = GridBuilder(),
        runner   = GridRunner(exchange),
        registry = GridRegistry(),
        exchange = exchange,
        sizer    = GridSizer(),
    )


def _make_placed_session(symbol: str, position_side: str,
                          levels: list) -> GridSession:
    """
    Build a GridSession with pre-placed levels (no exchange call needed).
    levels = [(price, qty), ...]
    order_ids = "900", "901", ... for tracking in assertions.
    """
    session = GridSession(symbol=symbol, position_side=position_side)
    session.status = "running"
    for i, (price, qty) in enumerate(levels):
        lvl = GridLevel(
            index=i + 1,
            price=price,
            qty=qty,
            position_side=position_side,
            status="placed",
            order_id=str(900 + i),
        )
        session.levels.append(lvl)
    return session


# ─────────────────────────────────────────────────────────────
# Scenario 1 — successful rebuild
# ─────────────────────────────────────────────────────────────

def test_rebuild_success():
    """
    SIRENUSDT LONG, market price ~0.57066.
    Session has 3 placed tail levels below old entry.
    New entry after averaging = 0.560.

    _grid_build_config: first_offset=1%, last_offset=3%
      → expected new prices: [0.5544, ~0.549, 0.5432]

    Expected after rebuild_pending_tail:
    - Old placed levels → status="canceled", cancel_order called × 3
    - 3 new placed levels with prices near new entry offsets
    - place_limit_order called × 3
    - update_sl_after_averaging called × 1
    - session saved in registry
    """
    symbol        = "SIRENUSDT"
    position_side = "LONG"
    entry_price   = 0.560    # new avg entry after averaging

    exchange = FakeExchange(
        entry_price   = entry_price,
        position_qty  = 60.0,
        position_side = position_side,
        min_qty       = 1.0,
        min_notional  = 5.0,
        step_size     = 1.0,
    )

    service = _make_service(exchange)

    # pending tail: 3 levels placed below old entry (now stale after averaging)
    session = _make_placed_session(symbol, position_side, [
        (0.558, 20.0),
        (0.551, 20.0),
        (0.546, 20.0),  # clearly stale: 0.52% away from new target 0.5432
    ])
    service.registry.save_session(session)

    # Inject build config — normally populated by start_session
    service._grid_build_config[(symbol, position_side)] = {
        "orders_count":         3,
        "first_offset_percent": 1.0,   # 0.560 * 0.99 = 0.5544
        "last_offset_percent":  3.0,   # 0.560 * 0.97 = 0.5432
        "distribution_mode":    "step",
        "distribution_value":   1.0,
    }

    # Track update_sl_after_averaging via monkey-patch
    sl_calls = []
    service.update_sl_after_averaging = lambda sym, ps: sl_calls.append((sym, ps))

    # ── Act ──
    service.rebuild_pending_tail(symbol, position_side)

    # ── Assert: old levels canceled ──
    old_order_ids = {"900", "901", "902"}
    assert set(exchange.cancelled_orders) == old_order_ids, (
        f"Expected cancel_order for {old_order_ids}, got {exchange.cancelled_orders}"
    )

    old_levels = [l for l in session.levels if l.order_id in old_order_ids]
    assert all(l.status == "canceled" for l in old_levels), (
        f"Old levels should be canceled: {[(l.order_id, l.status) for l in old_levels]}"
    )

    # ── Assert: 3 new placed levels added ──
    new_placed = [l for l in session.levels if l.status == "placed"]
    assert len(new_placed) == 3, (
        f"Expected 3 new placed levels, got {len(new_placed)}"
    )

    # ── Assert: new prices derived from entry_price + offsets ──
    # step distribution: prices evenly from first_price to last_price
    first_expected = entry_price * (1 - 1.0 / 100)   # 0.5544
    last_expected  = entry_price * (1 - 3.0 / 100)   # 0.5432
    new_prices     = sorted([l.price for l in new_placed], reverse=True)
    assert abs(new_prices[0] - first_expected) < 0.002, (
        f"First new price {new_prices[0]:.5f} too far from expected {first_expected:.5f}"
    )
    assert abs(new_prices[-1] - last_expected) < 0.002, (
        f"Last new price {new_prices[-1]:.5f} too far from expected {last_expected:.5f}"
    )

    # ── Assert: place_limit_order called × 3 ──
    assert len(exchange.placed_limit_orders) == 3, (
        f"Expected 3 place_limit_order calls, got {len(exchange.placed_limit_orders)}"
    )

    # ── Assert: update_sl_after_averaging called × 1 ──
    assert len(sl_calls) == 1, (
        f"Expected update_sl_after_averaging called once, got {len(sl_calls)}"
    )
    assert sl_calls[0] == (symbol, position_side), (
        f"update_sl_after_averaging called with wrong args: {sl_calls[0]}"
    )

    # ── Assert: session saved in registry ──
    saved = service.registry.get_session(symbol, position_side)
    assert saved is not None
    assert any(l.status == "placed" for l in saved.levels), (
        "Saved session should have at least one placed level"
    )

    print("[PASS] test_rebuild_success")


# ─────────────────────────────────────────────────────────────
# Scenario 2 — rebuild skipped when extreme order check fails
# ─────────────────────────────────────────────────────────────

def test_rebuild_skipped_when_extreme_order_check_fails():
    """
    round_order_params returns qty=0.0 — simulates extreme level order check failure.
    This is not a real margin check: it artificially forces rounded_qty < min_qty
    to verify that rebuild is skipped when the extreme order cannot be placed.

    Expected after rebuild_pending_tail:
    - cancel_order NOT called
    - All original levels remain status="placed"
    - No new levels added (session.levels still len=3)
    - place_limit_order NOT called
    - update_sl_after_averaging NOT called
    """
    symbol        = "SIRENUSDT"
    position_side = "LONG"

    exchange = FakeExchange(
        entry_price   = 0.560,
        position_qty  = 60.0,
        position_side = position_side,
        round_to_zero = True,   # forces rounded_qty=0.0 → extreme order check fails
    )

    service = _make_service(exchange)

    session = _make_placed_session(symbol, position_side, [
        (0.558, 20.0),
        (0.551, 20.0),
        (0.546, 20.0),  # clearly stale: 0.52% away from new target 0.5432
    ])
    service.registry.save_session(session)

    service._grid_build_config[(symbol, position_side)] = {
        "orders_count":         3,
        "first_offset_percent": 1.0,
        "last_offset_percent":  3.0,
        "distribution_mode":    "step",
        "distribution_value":   1.0,
    }

    sl_calls = []
    service.update_sl_after_averaging = lambda sym, ps: sl_calls.append((sym, ps))

    # ── Act ──
    service.rebuild_pending_tail(symbol, position_side)

    # ── Assert: nothing cancelled ──
    assert len(exchange.cancelled_orders) == 0, (
        f"Expected 0 cancel_order calls, got {exchange.cancelled_orders}"
    )

    # ── Assert: original levels untouched ──
    assert len(session.levels) == 3, (
        f"Session should still have 3 levels, got {len(session.levels)}"
    )
    assert all(l.status == "placed" for l in session.levels), (
        f"All original levels should remain placed: {[l.status for l in session.levels]}"
    )

    # ── Assert: no new orders ──
    assert len(exchange.placed_limit_orders) == 0, (
        f"Expected 0 place_limit_order calls, got {exchange.placed_limit_orders}"
    )

    # ── Assert: SL not touched ──
    assert len(sl_calls) == 0, (
        f"Expected update_sl_after_averaging NOT called, got {len(sl_calls)}"
    )

    print("[PASS] test_rebuild_skipped_when_extreme_order_check_fails")


# ─────────────────────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        test_rebuild_success,
        test_rebuild_skipped_when_extreme_order_check_fails,
    ]
    passed = 0
    failed = 0

    for test_fn in tests:
        try:
            test_fn()
            passed += 1
        except AttributeError as e:
            print(f"[FAIL - expected until implemented] {test_fn.__name__}: {e}")
            failed += 1
        except AssertionError as e:
            print(f"[FAIL] {test_fn.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"[ERROR] {test_fn.__name__}: {type(e).__name__}: {e}")
            failed += 1

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed")
    print("(AttributeError failures are expected until rebuild_pending_tail is implemented)")
