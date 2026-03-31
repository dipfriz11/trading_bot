import threading
import time

from order.order_request import OrderRequest
from order.executors import MarketExecutor, LimitExecutor


class OrderManager:

    def __init__(self, exchange, symbol, config):
        self.exchange = exchange
        self.symbol = symbol
        self.config = config

        self.order_id = None
        self.current_price = None
        self.side = None
        self.quantity = None

        # структура для нескольких ордеров (LONG / SHORT)
        self.orders = {}

        self.trailing_enabled = config.get("trailing_entry", False)

        self._trailing_thread = None
        self._trailing_active = False

        # multi-trailing: поток и флаг на каждый position_side
        self.trailing_threads = {}
        self.trailing_active  = {}

        # executors — тонкий слой под order_type
        self._market_executor = MarketExecutor(exchange)
        self._limit_executor = LimitExecutor(exchange)

        # exchange-native TP/SL algo orders: { position_side: {"tp_algo_id": int, "sl_algo_id": int} }
        self.tpsl = {}

    def place_order(self, side, price, quantity, position_side=None):
        # останавливаем предыдущий trailing (если был)
        self.stop_trailing()

        order = self.exchange.place_limit_order(
            symbol=self.symbol,
            side=side,
            quantity=quantity,
            price=price,
            position_side=position_side
        )

        self.order_id = order["orderId"]
        self.current_price = price
        self.side = side
        self.quantity = quantity

    def update_order(self, new_price, position_side=None):

        # если трейлинг выключен — не двигаем ордер (режим как на бирже)
        if not self.trailing_enabled:
            return

        # выбираем источник данных: multi-order или старый single-order
        if position_side and position_side in self.orders:
            entry = self.orders[position_side]
            order_id      = entry["order_id"]
            current_price = entry["price"]
            side          = entry["side"]
            quantity      = entry["quantity"]
        else:
            order_id      = self.order_id
            current_price = self.current_price
            side          = self.side
            quantity      = self.quantity

        if not order_id:
            return

        # не обновляем если цена не изменилась
        if abs(new_price - current_price) < 1e-8:
            return

        # двигаем только в выгодную сторону
        if side == "BUY" and new_price <= current_price:
            return
        if side == "SELL" and new_price >= current_price:
            return

        order = self.exchange.get_order(self.symbol, order_id)
        status = order["status"]

        if status != "NEW":
            return

        try:
            request = OrderRequest(
                symbol=self.symbol,
                side=side,
                order_type="limit",
                quantity=quantity,
                price=new_price,
                params={"position_side": position_side} if position_side else {}
            )
            self._limit_executor.modify(order_id, request)

            # обновляем цену в нужном месте
            if position_side and position_side in self.orders:
                self.orders[position_side]["price"] = new_price
            else:
                self.current_price = new_price

        except Exception as e:
            print(f"Modify failed: {e}, fallback to cancel+new")

            # fallback
            try:
                self.exchange.cancel_order(self.symbol, order_id)
                order = self.exchange.place_limit_order(
                    symbol=self.symbol,
                    side=side,
                    quantity=quantity,
                    price=new_price,
                    position_side=position_side
                )

                new_order_id = order["orderId"]

                if position_side and position_side in self.orders:
                    self.orders[position_side]["order_id"] = new_order_id
                    self.orders[position_side]["price"]    = new_price
                else:
                    self.order_id      = new_order_id
                    self.current_price = new_price

            except Exception as e2:
                print(f"Fallback failed: {e2}")

    def _apply_trailing_price(self, price: float, distance: float, position_side: str = None) -> None:
        if position_side:
            entry = self.orders.get(position_side)
            if not entry:
                return
            side = entry["side"]
            if side == "BUY":
                target_price = price * (1 - distance / 100)
            else:
                target_price = price * (1 + distance / 100)
            print(f"[Trailing] {self.symbol} | {position_side} | market={price} | target={target_price}")
            self.update_order(target_price, position_side=position_side)
        else:
            if not self.side:
                return
            if self.side == "BUY":
                target_price = price * (1 - distance / 100)
            else:
                target_price = price * (1 + distance / 100)
            print(f"[Trailing] {self.symbol} | market={price} | target={target_price}")
            self.update_order(target_price)

    def start_trailing_loop(self, distance: float, interval: float = 2.0, position_side: str = None):
        # если трейлинг выключен — не запускаем
        if not self.trailing_enabled:
            return

        if position_side:
            # multi-order режим
            if self.trailing_active.get(position_side):
                return

            self.trailing_active[position_side] = True
            print(f"[Trailing STARTED] {self.symbol} | {position_side} | interval={interval}s | distance={distance}%")

            def loop():
                while self.trailing_active.get(position_side) and self.orders.get(position_side, {}).get("order_id"):
                    try:
                        current_price = self.exchange.get_price(self.symbol)
                        self._apply_trailing_price(price=current_price, distance=distance, position_side=position_side)

                        time.sleep(interval)

                    except Exception as e:
                        print(f"[Trailing ERROR] {self.symbol} | {position_side} | {e}")
                        time.sleep(interval)

            t = threading.Thread(target=loop, daemon=True)
            self.trailing_threads[position_side] = t
            t.start()

        else:
            # старый single-order режим
            if self._trailing_active:
                return

            self._trailing_active = True
            print(f"[Trailing STARTED] {self.symbol} | interval={interval}s | distance={distance}%")

            def loop():
                while self._trailing_active and self.order_id:
                    try:
                        current_price = self.exchange.get_price(self.symbol)
                        self._apply_trailing_price(price=current_price, distance=distance)

                        time.sleep(interval)

                    except Exception as e:
                        print(f"[Trailing ERROR] {self.symbol} | {e}")
                        time.sleep(interval)

            self._trailing_thread = threading.Thread(target=loop, daemon=True)
            self._trailing_thread.start()

    def stop_trailing(self, position_side: str = None):
        if position_side:
            self.trailing_active[position_side] = False
            self.trailing_threads.pop(position_side, None)
            print(f"[Trailing STOPPED] {self.symbol} | {position_side}")
        else:
            self._trailing_active = False
            print(f"[Trailing STOPPED] {self.symbol}")

    # ------------------------------------------------------------------
    # Новый слой: методы принимают OrderRequest / работают через executor
    # Существующий place_order / update_order НЕ затронуты
    # ------------------------------------------------------------------

    def cancel_order(self, order_id: int = None) -> dict | None:
        """Отменяет текущий (или указанный) ордер."""
        oid = order_id if order_id is not None else self.order_id
        if not oid:
            return None
        return self.exchange.cancel_order(self.symbol, oid)

    def place_request(self, request: OrderRequest, position_side: str = None) -> dict:
        """Размещает ордер через OrderRequest → executor. Trailing не запускает."""
        ps = request.params.get("position_side") if request.params else None
        if not ps:
            ps = "LONG" if request.side == "BUY" else "SHORT"
        self.stop_trailing(position_side=ps)

        if request.order_type == "market":
            order = self._market_executor.place(request)
        else:
            order = self._limit_executor.place(request)

        self.order_id = order["orderId"]
        self.current_price = request.price
        self.side = request.side
        self.quantity = request.quantity

        # сохраняем в новую структуру
        self.orders[ps] = {
            "order_id": order["orderId"],
            "price": request.price,
            "quantity": request.quantity,
            "side": request.side,
        }

        return order

    def modify_order(self, request: OrderRequest) -> dict | None:
        """Модифицирует текущий ордер через OrderRequest → LimitExecutor."""
        if not self.order_id:
            return None
        result = self._limit_executor.modify(self.order_id, request)
        self.current_price = request.price
        return result

    # ------------------------------------------------------------------
    # Exchange-native TP/SL (algo orders)
    # Не подключены к execute() — вызываются через on_position_confirmed()
    # ------------------------------------------------------------------

    def place_tpsl(self, entry_price: float, qty: float,
                   position_side: str, tp_pct: float, sl_pct: float) -> dict:
        """Ставит TAKE_PROFIT (limit) + STOP_MARKET для position_side.
        symbol_info получает сам. Возвращает {"tp_algo_id": ..., "sl_algo_id": ...}.
        """
        symbol_info = self.exchange.get_symbol_info(self.symbol)
        side      = "SELL" if position_side == "LONG" else "BUY"
        tp_factor = (1 + tp_pct / 100) if position_side == "LONG" else (1 - tp_pct / 100)
        sl_factor = (1 - sl_pct / 100) if position_side == "LONG" else (1 + sl_pct / 100)
        tp_price  = self.exchange._round_price(symbol_info, entry_price * tp_factor, side)
        sl_price  = self.exchange._round_price(symbol_info, entry_price * sl_factor, side)

        tp_resp = self.exchange.client.futures_create_order(
            symbol=self.symbol, side=side, positionSide=position_side,
            type="TAKE_PROFIT", stopPrice=tp_price, price=tp_price,
            quantity=qty, timeInForce="GTC", workingType="MARK_PRICE",
        )
        sl_resp = self.exchange.client.futures_create_order(
            symbol=self.symbol, side=side, positionSide=position_side,
            type="STOP_MARKET", stopPrice=sl_price,
            closePosition=True, workingType="MARK_PRICE",
        )
        self.tpsl[position_side] = {
            "tp_algo_id": tp_resp["algoId"],
            "sl_algo_id": sl_resp["algoId"],
        }
        return self.tpsl[position_side]

    def cancel_tpsl(self, position_side: str) -> None:
        """Отменяет оба защитных ордера для position_side."""
        state = self.tpsl.pop(position_side, None)
        if not state:
            return
        for key, label in [("tp_algo_id", "TP"), ("sl_algo_id", "SL")]:
            aid = state.get(key)
            if aid:
                try:
                    self.exchange.client.futures_cancel_algo_order(algoId=aid)
                except Exception as e:
                    print(f"[{self.symbol}] cancel {label} algoId={aid}: {e}")

    def has_tpsl(self, position_side: str) -> bool:
        """Возвращает True если для position_side есть активные TP/SL ордера."""
        return position_side in self.tpsl
