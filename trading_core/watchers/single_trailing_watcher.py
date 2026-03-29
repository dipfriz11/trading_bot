import threading
import time
from typing import Dict, Optional, Tuple


class SingleTrailingWatcher:

    def __init__(self, order_manager, market_data, cooldown_sec: float = 2.0):
        self._order_manager = order_manager
        self._market_data = market_data
        self._cooldown_sec = cooldown_sec

        self._watched: Dict[Tuple[str, str], dict] = {}    # (symbol, position_side) → {distance}
        self._in_flight: Dict[Tuple[str, str], bool] = {}
        self._last_applied_at: Dict[Tuple[str, str], float] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_watching(self, symbol: str, distance: float, position_side: str) -> None:
        key = (symbol, position_side)
        listener_id = f"single_trailing_{symbol}_{position_side}"
        with self._lock:
            already_watched = key in self._watched
            self._watched[key] = {"distance": distance}
            self._last_applied_at.setdefault(key, 0.0)
            self._in_flight.setdefault(key, False)
        if already_watched:
            self._market_data.remove_price_listener(symbol, listener_id)
            deadline = time.monotonic() + 3.0
            while time.monotonic() < deadline:
                with self._lock:
                    if not self._in_flight.get(key, False):
                        break
                time.sleep(0.05)
            self._market_data.add_price_listener(symbol, listener_id, self._on_price_update)
        else:
            self._market_data.subscribe(symbol)
            self._market_data.add_price_listener(symbol, listener_id, self._on_price_update)

    def stop_watching(self, symbol: str, position_side: str) -> None:
        key = (symbol, position_side)
        listener_id = f"single_trailing_{symbol}_{position_side}"
        self._market_data.remove_price_listener(symbol, listener_id)
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            with self._lock:
                if not self._in_flight.get(key, False):
                    break
            time.sleep(0.05)
        self._market_data.unsubscribe(symbol)
        with self._lock:
            self._watched.pop(key, None)
            self._last_applied_at.pop(key, None)
            self._in_flight.pop(key, None)

    def stop_all(self) -> None:
        for symbol, position_side in list(self._watched.keys()):
            self.stop_watching(symbol, position_side)

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _on_price_update(self, symbol: str, price: float) -> None:
        with self._lock:
            legs = [(s, ps) for (s, ps) in self._watched if s == symbol]
        for key in legs:
            _, position_side = key
            with self._lock:
                if key not in self._watched:
                    continue
                if self._in_flight.get(key, False):
                    continue
                elapsed = time.monotonic() - self._last_applied_at.get(key, 0.0)
                if elapsed < self._cooldown_sec:
                    continue
                config = self._watched[key]
                self._in_flight[key] = True
            thread = threading.Thread(
                target=self._do_apply,
                args=(symbol, price, config["distance"], position_side),
                daemon=True,
            )
            thread.start()

    def _do_apply(self, symbol: str, price: float, distance: float, position_side: str) -> None:
        key = (symbol, position_side)
        try:
            with self._lock:
                if key not in self._watched:
                    return
            self._order_manager._apply_trailing_price(
                price=price,
                distance=distance,
                position_side=position_side,
            )
            with self._lock:
                if key in self._last_applied_at:
                    self._last_applied_at[key] = time.monotonic()
        except Exception as e:
            print(f"[SingleTrailingWatcher] apply error ({symbol}/{position_side}): {e}")
        finally:
            with self._lock:
                if key in self._in_flight:
                    self._in_flight[key] = False
