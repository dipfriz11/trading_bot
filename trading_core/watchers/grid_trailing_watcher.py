import threading
import time
from typing import Dict, List, Optional, Set


class GridTrailingWatcher:

    def __init__(self, grid_service, market_data, cooldown_sec: float = 5.0):
        self._grid_service = grid_service
        self._market_data = market_data
        self._cooldown_sec = cooldown_sec

        self._watched: Dict[str, Set[str]] = {}
        self._last_modified_at: Dict[str, float] = {}
        self._in_flight: Dict[str, bool] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_watching(self, symbol: str, sides: Optional[List[str]] = None) -> None:
        if sides is None:
            sides = ["LONG", "SHORT"]
        with self._lock:
            self._watched[symbol] = set(sides)
            self._last_modified_at.setdefault(symbol, 0.0)
            self._in_flight.setdefault(symbol, False)
        listener_id = f"grid_trailing_{symbol}"
        self._market_data.subscribe(symbol)
        self._market_data.add_price_listener(symbol, listener_id, self._on_price_update)

    def stop_watching(self, symbol: str) -> None:
        listener_id = f"grid_trailing_{symbol}"
        self._market_data.remove_price_listener(symbol, listener_id)
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            with self._lock:
                if not self._in_flight.get(symbol, False):
                    break
            time.sleep(0.05)
        self._market_data.unsubscribe(symbol)
        with self._lock:
            self._watched.pop(symbol, None)
            self._last_modified_at.pop(symbol, None)
            self._in_flight.pop(symbol, None)

    def stop_all(self) -> None:
        for symbol in list(self._watched.keys()):
            self.stop_watching(symbol)

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _on_price_update(self, symbol: str, price: float) -> None:
        with self._lock:
            if symbol not in self._watched:
                return
            if self._in_flight.get(symbol, False):
                return
            elapsed = time.monotonic() - self._last_modified_at.get(symbol, 0.0)
            if elapsed < self._cooldown_sec:
                return
            self._in_flight[symbol] = True
        thread = threading.Thread(
            target=self._do_check,
            args=(symbol, price),
            daemon=True,
        )
        thread.start()

    def _do_check(self, symbol: str, price: float) -> None:
        try:
            with self._lock:
                sides = list(self._watched.get(symbol, []))
            for side in sides:
                with self._lock:
                    if symbol not in self._watched:
                        return
                result = self._grid_service.check_trailing(symbol, side, price)
                if result is not None:
                    with self._lock:
                        if symbol in self._last_modified_at:
                            self._last_modified_at[symbol] = time.monotonic()
                    break
        except Exception as e:
            print(f"[GridTrailingWatcher] check error ({symbol}): {e}")
        finally:
            with self._lock:
                if symbol in self._in_flight:
                    self._in_flight[symbol] = False
