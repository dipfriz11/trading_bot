import threading
import time


class OrderManager:

    def __init__(self, exchange, symbol, config):
        self.exchange = exchange
        self.symbol = symbol
        self.config = config

        self.order_id = None
        self.current_price = None
        self.side = None
        self.quantity = None

        self.trailing_enabled = config.get("trailing_entry", False)

        self._trailing_thread = None
        self._trailing_active = False

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

        if not self.order_id:
            return

        # не обновляем если цена не изменилась
        if abs(new_price - self.current_price) < 1e-8:
            return

        # двигаем только в выгодную сторону
        if self.side == "BUY" and new_price <= self.current_price:
            return
        if self.side == "SELL" and new_price >= self.current_price:
            return

        order = self.exchange.get_order(self.symbol, self.order_id)
        status = order["status"]

        if status != "NEW":
            return

        try:
            self.exchange.modify_order(
                symbol=self.symbol,
                order_id=self.order_id,
                side=self.side,
                quantity=self.quantity,
                price=new_price,
                position_side=position_side
            )
            self.current_price = new_price

        except Exception as e:
            print(f"Modify failed: {e}, fallback to cancel+new")

            # fallback
            try:
                self.exchange.cancel_order(self.symbol, self.order_id)
                order = self.exchange.place_limit_order(
                    symbol=self.symbol,
                    side=self.side,
                    quantity=self.quantity,
                    price=new_price,
                    position_side=position_side
                )

                self.order_id = order["orderId"]
                self.current_price = new_price

            except Exception as e2:
                print(f"Fallback failed: {e2}")

    def start_trailing_loop(self, distance: float, interval: float = 2.0):
        # если трейлинг выключен — не запускаем
        if not self.trailing_enabled:
            return

        # если уже запущен — не дублируем
        if self._trailing_active:
            return

        self._trailing_active = True
        print(f"[Trailing STARTED] {self.symbol} | interval={interval}s | distance={distance}%")

        def loop():
            while self._trailing_active and self.order_id:
                try:
                    current_price = self.exchange.get_price(self.symbol)

                    if self.side == "BUY":
                        target_price = current_price * (1 - distance / 100)
                    else:
                        target_price = current_price * (1 + distance / 100)

                    print(f"[Trailing] {self.symbol} | market={current_price} | target={target_price}")
                    self.update_order(target_price)

                    time.sleep(interval)

                except Exception as e:
                    print(f"[Trailing ERROR] {self.symbol} | {e}")
                    time.sleep(interval)

        self._trailing_thread = threading.Thread(target=loop, daemon=True)
        self._trailing_thread.start()

    def stop_trailing(self):
        self._trailing_active = False
        print(f"[Trailing STOPPED] {self.symbol}")
