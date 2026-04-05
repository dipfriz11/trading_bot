import threading
import time
from typing import Dict, Optional, Tuple


class GridTrailingWatcher:

    def __init__(self, grid_service, market_data, cooldown_sec: float = 5.0):
        self._grid_service = grid_service
        self._market_data = market_data
        self._cooldown_sec = cooldown_sec

        self._watched: Dict[Tuple[str, str], bool] = {}           # (symbol, position_side) → True
        self._last_modified_at: Dict[Tuple[str, str], float] = {}
        self._in_flight: Dict[Tuple[str, str], bool] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_watching(self, symbol: str, position_side: str) -> None:
        key = (symbol, position_side)
        listener_id = f"grid_trailing_{symbol}_{position_side}"
        with self._lock:
            already_watched = key in self._watched
            self._watched[key] = True
            self._last_modified_at.setdefault(key, 0.0)
            self._in_flight.setdefault(key, False)
        if not already_watched:
            self._market_data.subscribe(symbol)
            self._market_data.add_price_listener(symbol, listener_id, self._on_price_update)

    def stop_watching(self, symbol: str, position_side: str) -> None:
        key = (symbol, position_side)
        listener_id = f"grid_trailing_{symbol}_{position_side}"
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
            self._last_modified_at.pop(key, None)
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
                elapsed = time.monotonic() - self._last_modified_at.get(key, 0.0)
                if elapsed < self._cooldown_sec:
                    continue
                self._in_flight[key] = True
            thread = threading.Thread(
                target=self._do_check,
                args=(symbol, price, position_side),
                daemon=True,
            )
            thread.start()

    def _do_check(self, symbol: str, price: float, position_side: str) -> None:
        key = (symbol, position_side)
        try:
            with self._lock:
                if key not in self._watched:
                    return

            hit = self._grid_service.check_tpsl(symbol, position_side, price)
            if hit is not None:
                return

            filled = self._grid_service.check_grid_fills(symbol, position_side)
            if filled:
                for lvl in filled:
                    print(
                        f"[GridFills] {symbol}/{position_side}"
                        f"  level[{lvl.index}] filled"
                        f"  price={lvl.price}"
                    )
                mode = self._grid_service._tp_update_mode.get((symbol, position_side), "fixed")
                if mode == "reprice":
                    updated = self._grid_service.update_grid_tp_orders_reprice(symbol, position_side)
                else:
                    updated = self._grid_service.update_grid_tp_orders_fixed(symbol, position_side)
                if updated is not None:
                    print(
                        f"[GridTP] {symbol}/{position_side}"
                        f"  TP orders updated after averaging fill ({mode}): {len(updated)} orders"
                    )
                self._grid_service.update_sl_after_averaging(symbol, position_side)

            filled_tps = self._grid_service.check_tp_fills(symbol, position_side)
            if filled_tps:
                for tp in filled_tps:
                    print(
                        f"[GridTP] {symbol}/{position_side}"
                        f"  TP filled: order_id={tp['order_id']}"
                        f"  tp_percent={tp['tp_percent']}%"
                        f"  price={tp['price']:.8f}"
                        f"  qty={tp['qty']}"
                    )

            result = self._grid_service.check_trailing(symbol, position_side, price)
            if result is not None:
                with self._lock:
                    if key in self._last_modified_at:
                        self._last_modified_at[key] = time.monotonic()
        except Exception as e:
            print(f"[GridTrailingWatcher] check error ({symbol}/{position_side}): {e}")
        finally:
            with self._lock:
                if key in self._in_flight:
                    self._in_flight[key] = False
