import threading
from typing import Callable, Dict, Optional

from binance import ThreadedWebsocketManager


class MarketDataService:

    def __init__(self, client):
        self._latest_prices: Dict[str, float] = {}
        self._streams: Dict[str, str] = {}
        self._subscriber_count: Dict[str, int] = {}
        self._listeners: Dict[str, Dict[str, Callable]] = {}
        self._lock = threading.Lock()

        self._twm = ThreadedWebsocketManager(
            api_key=client.API_KEY,
            api_secret=client.API_SECRET,
        )
        self._twm.start()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def subscribe(self, symbol: str) -> None:
        with self._lock:
            if symbol not in self._subscriber_count:
                self._subscriber_count[symbol] = 0
                self._listeners[symbol] = {}
            self._subscriber_count[symbol] += 1
            should_start = self._subscriber_count[symbol] == 1
        if should_start:
            self._start_stream(symbol)

    def unsubscribe(self, symbol: str) -> None:
        with self._lock:
            if symbol not in self._subscriber_count:
                return
            self._subscriber_count[symbol] -= 1
            should_stop = self._subscriber_count[symbol] <= 0
            if should_stop:
                del self._subscriber_count[symbol]
                del self._listeners[symbol]
                self._latest_prices.pop(symbol, None)
        if should_stop:
            self._stop_stream(symbol)

    def get_latest_price(self, symbol: str) -> Optional[float]:
        with self._lock:
            return self._latest_prices.get(symbol)

    def add_price_listener(
        self,
        symbol: str,
        listener_id: str,
        callback: Callable[[str, float], None],
    ) -> None:
        with self._lock:
            if symbol not in self._listeners:
                self._listeners[symbol] = {}
            self._listeners[symbol][listener_id] = callback

    def remove_price_listener(self, symbol: str, listener_id: str) -> None:
        with self._lock:
            if symbol in self._listeners:
                self._listeners[symbol].pop(listener_id, None)

    def stop(self) -> None:
        self._twm.stop()
        with self._lock:
            self._streams.clear()
            self._subscriber_count.clear()
            self._listeners.clear()
            self._latest_prices.clear()

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _start_stream(self, symbol: str) -> None:
        stream_key = self._twm.start_futures_multiplex_socket(
            callback=self._make_handler(symbol),
            streams=[f"{symbol.lower()}@miniTicker"],
        )
        self._streams[symbol] = stream_key

    def _stop_stream(self, symbol: str) -> None:
        stream_key = self._streams.pop(symbol, None)
        if stream_key:
            self._twm.stop_socket(stream_key)

    def _make_handler(self, symbol: str) -> Callable:
        def handler(msg: dict) -> None:
            self._handle_message(symbol, msg)
        return handler

    def _handle_message(self, symbol: str, msg: dict) -> None:
        if msg.get("e") == "error":
            return
        data = msg.get("data", msg)
        price_str = data.get("c")
        if price_str is None:
            return
        price = float(price_str)
        with self._lock:
            self._latest_prices[symbol] = price
            listeners = dict(self._listeners.get(symbol, {}))
        for callback in listeners.values():
            try:
                callback(symbol, price)
            except Exception as e:
                print(f"[MarketDataService] listener error ({symbol}): {e}")
