import threading
import time
from typing import Dict, Optional


class SingleTrailingWatcher:

    def __init__(self, order_manager, market_data, cooldown_sec: float = 2.0):
        self._order_manager = order_manager
        self._market_data = market_data
        self._cooldown_sec = cooldown_sec

        self._watched: Dict[str, dict] = {}           # symbol → {distance, position_side}
        self._in_flight: Dict[str, bool] = {}
        self._last_applied_at: Dict[str, float] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_watching(self, symbol: str, distance: float, position_side: str = None) -> None:
        listener_id = f"single_trailing_{symbol}"
        with self._lock:
            already_watched = symbol in self._watched
            self._watched[symbol] = {"distance": distance, "position_side": position_side}
            self._last_applied_at.setdefault(symbol, 0.0)
            self._in_flight.setdefault(symbol, False)
        if already_watched:
            self._market_data.remove_price_listener(symbol, listener_id)
            deadline = time.monotonic() + 3.0
            while time.monotonic() < deadline:
                with self._lock:
                    if not self._in_flight.get(symbol, False):
                        break
                time.sleep(0.05)
            self._market_data.add_price_listener(symbol, listener_id, self._on_price_update)
        else:
            self._market_data.subscribe(symbol)
            self._market_data.add_price_listener(symbol, listener_id, self._on_price_update)

    def stop_watching(self, symbol: str) -> None:
        listener_id = f"single_trailing_{symbol}"
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
            self._last_applied_at.pop(symbol, None)
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
            elapsed = time.monotonic() - self._last_applied_at.get(symbol, 0.0)
            if elapsed < self._cooldown_sec:
                return
            config = self._watched[symbol]
            self._in_flight[symbol] = True
        thread = threading.Thread(
            target=self._do_apply,
            args=(symbol, price, config["distance"], config["position_side"]),
            daemon=True,
        )
        thread.start()

    def _do_apply(self, symbol: str, price: float, distance: float, position_side: Optional[str]) -> None:
        try:
            with self._lock:
                if symbol not in self._watched:
                    return
            self._order_manager._apply_trailing_price(
                price=price,
                distance=distance,
                position_side=position_side,
            )
            with self._lock:
                if symbol in self._last_applied_at:
                    self._last_applied_at[symbol] = time.monotonic()
        except Exception as e:
            print(f"[SingleTrailingWatcher] apply error ({symbol}): {e}")
        finally:
            with self._lock:
                if symbol in self._in_flight:
                    self._in_flight[symbol] = False
