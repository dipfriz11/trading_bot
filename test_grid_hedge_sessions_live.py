import sys
import time

from exchange.binance_exchange import BinanceExchange
from trading_core.grid.grid_builder import GridBuilder
from trading_core.grid.grid_runner import GridRunner
from trading_core.grid.grid_registry import GridRegistry
from trading_core.grid.grid_sizer import GridSizer
from trading_core.grid.grid_service import GridService
from trading_core.market_data.market_data_service import MarketDataService
from trading_core.watchers.grid_trailing_watcher import GridTrailingWatcher

if __name__ == "__main__":

    symbol = "SIRENUSDT"

    exchange    = BinanceExchange()
    builder     = GridBuilder()
    runner      = GridRunner(exchange)
    registry    = GridRegistry()
    sizer       = GridSizer()
    service     = GridService(builder, runner, registry, exchange, sizer)
    market_data = MarketDataService(exchange.client)
    watcher     = GridTrailingWatcher(service, market_data, cooldown_sec=2.0)

    # ------------------------------------------------------------------
    # PRE-CLEANUP
    # ------------------------------------------------------------------
    print("\n=== PRE-CLEANUP ===")

    for side in ("LONG", "SHORT"):
        leftover = service.get_session(symbol, side)
        if leftover is not None:
            service.stop_session(symbol, side)
            print(f"  stopped leftover {side} grid session")
        else:
            print(f"  no leftover {side} grid session")

    close_side = {"LONG": "sell", "SHORT": "buy"}
    for pos in exchange.get_positions(symbol):
        ps  = pos["positionSide"]
        qty = abs(float(pos["positionAmt"]))
        if ps in ("LONG", "SHORT") and qty > 0:
            exchange.close_position(symbol, close_side[ps], qty)
            print(f"  closed leftover {ps} position: qty={qty}")

    time.sleep(1.0)

    try:
        # ------------------------------------------------------------------
        # OPEN BOTH POSITIONS
        # ------------------------------------------------------------------
        print("\n=== OPEN LONG + SHORT POSITIONS ===")
        t0 = time.time()

        exchange.open_market_position(symbol, "buy",  usdt_amount=8.5, leverage=5)
        exchange.open_market_position(symbol, "sell", usdt_amount=8.5, leverage=5)
        time.sleep(1.0)

        t_positions_opened = time.time()
        print(f"  [TIMING] both positions opened in {t_positions_opened - t0:.2f}s")

        long_entry  = None
        long_qty    = 0.0
        short_entry = None
        short_qty   = 0.0

        for pos in exchange.get_positions(symbol):
            ps  = pos["positionSide"]
            qty = abs(float(pos["positionAmt"]))
            if ps == "LONG" and qty > 0:
                long_entry = float(pos["entryPrice"])
                long_qty   = qty
            elif ps == "SHORT" and qty > 0:
                short_entry = float(pos["entryPrice"])
                short_qty   = qty

        print(f"  LONG:  entry={long_entry}  qty={long_qty}")
        print(f"  SHORT: entry={short_entry}  qty={short_qty}")

        if long_qty == 0 or long_entry is None:
            print("FAIL: LONG position not opened")
            sys.exit(1)
        if short_qty == 0 or short_entry is None:
            print("FAIL: SHORT position not opened")
            sys.exit(1)

        # ------------------------------------------------------------------
        # START GRID SESSIONS
        # ------------------------------------------------------------------
        print("\n=== START GRID SESSIONS ===")
        current_price = exchange.get_price(symbol)
        print(f"  current_price={current_price:.8f}")

        long_first  = current_price * 0.950   # -5% below market
        long_last   = current_price * 0.920   # -8% below market
        short_first = current_price * 1.050   # +5% above market
        short_last  = current_price * 1.080   # +8% above market

        t_sessions_start = time.time()

        long_session = service.start_session(
            symbol=symbol,
            position_side="LONG",
            total_budget=20.0,
            levels_count=2,
            step_percent=1.0,
            orders_count=2,
            first_price=long_first,
            last_price=long_last,
            distribution_mode="step",
            distribution_value=1.0,
        )

        short_session = service.start_session(
            symbol=symbol,
            position_side="SHORT",
            total_budget=20.0,
            levels_count=2,
            step_percent=1.0,
            orders_count=2,
            first_price=short_first,
            last_price=short_last,
            distribution_mode="step",
            distribution_value=1.0,
        )

        t_sessions_started = time.time()
        print(f"  [TIMING] both sessions started in {t_sessions_started - t_sessions_start:.2f}s")

        print(f"\n  LONG  session_id: {long_session.session_id}")
        for lvl in long_session.levels:
            print(f"    [{lvl.index}] price={lvl.price:.8f}  qty={lvl.qty}  status={lvl.status}")

        print(f"\n  SHORT session_id: {short_session.session_id}")
        for lvl in short_session.levels:
            print(f"    [{lvl.index}] price={lvl.price:.8f}  qty={lvl.qty}  status={lvl.status}")

        time.sleep(0.5)

        # ------------------------------------------------------------------
        # PLACE TP ORDERS FOR BOTH SIDES
        # ------------------------------------------------------------------
        print("\n=== PLACE TP ORDERS ===")

        long_take_profits  = [
            {"tp_percent": 1.0, "close_percent": 50},
            {"tp_percent": 2.0, "close_percent": 50},
        ]
        short_take_profits = [
            {"tp_percent": 1.0, "close_percent": 50},
            {"tp_percent": 2.0, "close_percent": 50},
        ]

        t_tp_start = time.time()

        long_placed = service.place_grid_tp_orders(
            symbol=symbol,
            position_side="LONG",
            take_profits=long_take_profits,
        )

        short_placed = service.place_grid_tp_orders(
            symbol=symbol,
            position_side="SHORT",
            take_profits=short_take_profits,
        )

        t_tp_placed = time.time()
        print(f"  [TIMING] both TP sets placed in {t_tp_placed - t_tp_start:.2f}s")

        print(f"\n  LONG  TP order_ids: {[tp['order_id'] for tp in long_placed]}")
        for tp in long_placed:
            print(f"    tp_percent={tp['tp_percent']}%  price={tp['price']:.8f}  qty={tp['qty']}")

        print(f"\n  SHORT TP order_ids: {[tp['order_id'] for tp in short_placed]}")
        for tp in short_placed:
            print(f"    tp_percent={tp['tp_percent']}%  price={tp['price']:.8f}  qty={tp['qty']}")

        # ------------------------------------------------------------------
        # START WATCHER FOR BOTH SIDES
        # ------------------------------------------------------------------
        print("\n=== START WATCHER FOR BOTH SIDES ===")
        watcher.start_watching(symbol, "LONG")
        watcher.start_watching(symbol, "SHORT")
        print(f"  watcher watching: {list(watcher._watched.keys())}")

        time.sleep(2.0)

        # ------------------------------------------------------------------
        # CHECKS
        # ------------------------------------------------------------------
        print("\n=== CHECKS ===")
        passed = True

        # [1] LONG position opened
        if long_qty > 0 and long_entry is not None:
            print(f"  PASS: LONG position opened  entry={long_entry:.8f}  qty={long_qty}")
        else:
            print("  FAIL: LONG position not opened")
            passed = False

        # [2] SHORT position opened
        if short_qty > 0 and short_entry is not None:
            print(f"  PASS: SHORT position opened  entry={short_entry:.8f}  qty={short_qty}")
        else:
            print("  FAIL: SHORT position not opened")
            passed = False

        # [3] LONG grid session created
        long_s = service.get_session(symbol, "LONG")
        if long_s is not None:
            print(f"  PASS: LONG grid session exists  session_id={long_s.session_id}")
        else:
            print("  FAIL: LONG grid session not found")
            passed = False

        # [4] SHORT grid session created
        short_s = service.get_session(symbol, "SHORT")
        if short_s is not None:
            print(f"  PASS: SHORT grid session exists  session_id={short_s.session_id}")
        else:
            print("  FAIL: SHORT grid session not found")
            passed = False

        # [5] session_ids независимы
        if long_s is not None and short_s is not None:
            if long_s.session_id != short_s.session_id:
                print(f"  PASS: session_ids are independent")
            else:
                print(f"  FAIL: session_ids are identical — sessions not isolated")
                passed = False

        # [6] LONG TP orders placed
        long_tp_state = service._grid_tp_orders.get((symbol, "LONG"), [])
        if len(long_tp_state) == len(long_take_profits):
            print(f"  PASS: LONG _grid_tp_orders has {len(long_tp_state)} entries")
        else:
            print(f"  FAIL: LONG _grid_tp_orders has {len(long_tp_state)}, expected {len(long_take_profits)}")
            passed = False

        for i, tp in enumerate(long_tp_state):
            try:
                order     = exchange.get_order(symbol, tp["order_id"])
                ex_status = order.get("status")
                if ex_status == "NEW":
                    print(f"    PASS: LONG TP[{i}] order_id={tp['order_id']}  status={ex_status}  price={tp['price']:.8f}")
                else:
                    print(f"    FAIL: LONG TP[{i}] order_id={tp['order_id']}  unexpected status={ex_status}")
                    passed = False
            except Exception as e:
                print(f"    FAIL: LONG TP[{i}] get_order error: {e}")
                passed = False

        # [7] SHORT TP orders placed
        short_tp_state = service._grid_tp_orders.get((symbol, "SHORT"), [])
        if len(short_tp_state) == len(short_take_profits):
            print(f"  PASS: SHORT _grid_tp_orders has {len(short_tp_state)} entries")
        else:
            print(f"  FAIL: SHORT _grid_tp_orders has {len(short_tp_state)}, expected {len(short_take_profits)}")
            passed = False

        for i, tp in enumerate(short_tp_state):
            try:
                order     = exchange.get_order(symbol, tp["order_id"])
                ex_status = order.get("status")
                if ex_status == "NEW":
                    print(f"    PASS: SHORT TP[{i}] order_id={tp['order_id']}  status={ex_status}  price={tp['price']:.8f}")
                else:
                    print(f"    FAIL: SHORT TP[{i}] order_id={tp['order_id']}  unexpected status={ex_status}")
                    passed = False
            except Exception as e:
                print(f"    FAIL: SHORT TP[{i}] get_order error: {e}")
                passed = False

        # [8] _grid_tp_orders хранится раздельно
        long_ids  = {tp["order_id"] for tp in long_tp_state}
        short_ids = {tp["order_id"] for tp in short_tp_state}
        if long_ids.isdisjoint(short_ids):
            print(f"  PASS: _grid_tp_orders isolated — no shared order_ids")
        else:
            print(f"  FAIL: _grid_tp_orders overlap  shared={long_ids & short_ids}")
            passed = False

        # [9] watcher watches both sides
        watches_long  = (symbol, "LONG")  in watcher._watched
        watches_short = (symbol, "SHORT") in watcher._watched
        if watches_long and watches_short:
            print(f"  PASS: watcher is watching both LONG and SHORT")
        else:
            print(f"  FAIL: watcher not watching both sides  LONG={watches_long}  SHORT={watches_short}")
            passed = False

        if not passed:
            sys.exit(1)

    except Exception as e:
        print(f"\nERROR: {e}")
        raise

    finally:
        # [10] cleanup both sides
        watcher.stop_all()
        market_data.stop()

        print("\n=== FINAL CLEANUP ===")

        for side in ("LONG", "SHORT"):
            tp_state = service._grid_tp_orders.get((symbol, side), [])
            for tp in tp_state:
                try:
                    exchange.cancel_order(symbol, tp["order_id"])
                    print(f"  cancelled {side} TP order_id={tp['order_id']}")
                except Exception as e:
                    print(f"  cancel {side} TP order_id={tp['order_id']} error: {e}")
            service._grid_tp_orders.pop((symbol, side), None)
            service._tp_update_mode.pop((symbol, side), None)

            leftover = service.get_session(symbol, side)
            if leftover is not None:
                service.stop_session(symbol, side)
                print(f"  stopped {side} session")

        close_side = {"LONG": "sell", "SHORT": "buy"}
        for pos in exchange.get_positions(symbol):
            ps  = pos["positionSide"]
            qty = abs(float(pos["positionAmt"]))
            if ps in ("LONG", "SHORT") and qty > 0:
                exchange.close_position(symbol, close_side[ps], qty)
                print(f"  closed {ps} position: qty={qty}")

    print("\nTEST DONE")
