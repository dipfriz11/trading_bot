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

    symbol        = "SIRENUSDT"
    position_side = "SHORT"

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

    leftover = service.get_session(symbol, position_side)
    if leftover is not None:
        service.stop_session(symbol, position_side)
        print("  stopped leftover grid session")
    else:
        print("  no leftover grid session")

    for pos in exchange.get_positions(symbol):
        if pos["positionSide"] == position_side:
            qty = abs(float(pos["positionAmt"]))
            if qty > 0:
                exchange.close_position(symbol, "buy", qty)
                print(f"  closed leftover SHORT position: qty={qty}")
            else:
                print("  no open SHORT position")
            break

    time.sleep(1.0)

    try:
        # ------------------------------------------------------------------
        # OPEN MARKET SHORT (~8.5 USDT)
        # ------------------------------------------------------------------
        print("\n=== OPEN MARKET SHORT (~8.5 USDT) ===")
        t0 = time.time()
        exchange.open_market_position(symbol, "sell", usdt_amount=8.5, leverage=1)
        time.sleep(1.0)

        entry_price = None
        opened_qty  = 0.0
        for pos in exchange.get_positions(symbol):
            if pos["positionSide"] == position_side:
                entry_price = float(pos["entryPrice"])
                opened_qty  = abs(float(pos["positionAmt"]))
                break

        if opened_qty == 0 or entry_price is None:
            print("FAIL: SHORT position not opened")
            sys.exit(1)

        print(f"  entry_price={entry_price:.8f}  qty={opened_qty}")

        # ------------------------------------------------------------------
        # GRID SESSION (grid levels далеко выше — не мешают тесту)
        # ------------------------------------------------------------------
        current_price = exchange.get_price(symbol)
        first_price   = current_price * 1.080   # +8% above, pending
        last_price    = current_price * 1.100   # +10% above, pending

        print(f"\n=== START SHORT GRID SESSION ===")
        print(f"  current_price={current_price:.8f}")
        print(f"  level[1] first_price={first_price:.8f}  (+8% above, pending)")
        print(f"  level[2] last_price={last_price:.8f}   (+10% above, pending)")

        session = service.start_session(
            symbol=symbol,
            position_side=position_side,
            total_budget=20.0,
            levels_count=2,
            step_percent=1.0,
            orders_count=2,
            first_price=first_price,
            last_price=last_price,
            distribution_mode="step",
            distribution_value=1.0,
        )
        print(f"  session_id: {session.session_id}")
        for lvl in session.levels:
            print(f"  [{lvl.index}] price={lvl.price:.8f}  qty={lvl.qty}  status={lvl.status}")

        time.sleep(0.5)

        # ------------------------------------------------------------------
        # PLACE TP ORDERS
        # TP1: -0.3% от entry — близко, должен исполниться при волатильности
        # TP2: -3.0% от entry — далеко, остаётся pending
        # ------------------------------------------------------------------
        take_profits = [
            {"tp_percent": 0.3, "close_percent": 50},
            {"tp_percent": 3.0, "close_percent": 50},
        ]

        tp1_price = entry_price * (1 - 0.003)
        tp2_price = entry_price * (1 - 0.030)

        print(f"\n=== PLACE INITIAL TP ORDERS ===")
        print(f"  TP1: -0.3% from entry={entry_price:.8f}  -> {tp1_price:.8f}  close=50%  (near, expect fill)")
        print(f"  TP2: -3.0% from entry={entry_price:.8f}  -> {tp2_price:.8f}  close=50%  (far, pending)")

        t_tp_start = time.time()
        initial_placed = service.place_grid_tp_orders(
            symbol=symbol,
            position_side=position_side,
            take_profits=take_profits,
        )
        t_tp_placed = time.time()

        initial_order_ids = {tp["order_id"] for tp in initial_placed}
        initial_count     = len(initial_placed)

        print(f"  placed order_ids: {initial_order_ids}")
        print(f"  [TIMING] initial TP placed in {t_tp_placed - t_tp_start:.2f}s")

        base_qty_at_placement = service._base_position_qty.get((symbol, position_side), 0.0)
        print(f"  _base_position_qty at placement: {base_qty_at_placement}")

        # ------------------------------------------------------------------
        # [1] ПРОВЕРКА: initial TP orders placed
        # ------------------------------------------------------------------
        print("\n=== CHECK [1]: initial TP orders placed ===")
        passed = True

        tp_state = service._grid_tp_orders.get((symbol, position_side), [])
        if len(tp_state) == initial_count:
            print(f"  PASS: _grid_tp_orders has {len(tp_state)} entries")
        else:
            print(f"  FAIL: _grid_tp_orders has {len(tp_state)}, expected {initial_count}")
            passed = False
            sys.exit(1)

        # ------------------------------------------------------------------
        # START WATCHER
        # ------------------------------------------------------------------
        print(f"  position before watcher: positionAmt={opened_qty}  entry_price={entry_price:.8f}")

        watcher.start_watching(symbol, position_side)
        t_watcher_start = time.time()
        print(f"\n=== WATCHER STARTED — ждём TP1 fill до 60s ===")

        # ------------------------------------------------------------------
        # WAIT: _grid_tp_orders должен уменьшиться на 1
        # ------------------------------------------------------------------
        deadline        = time.time() + 60
        fill_detected   = False
        t_fill_detected = None

        while time.time() < deadline:
            current_tp    = service._grid_tp_orders.get((symbol, position_side), [])
            current_count = len(current_tp)

            if current_count < initial_count:
                t_fill_detected = time.time()
                fill_detected   = True
                break

            print(f"  waiting... _grid_tp_orders count={current_count}  ({time.time() - t_watcher_start:.0f}s elapsed)")
            time.sleep(2.0)

        # ------------------------------------------------------------------
        # TIMING SUMMARY
        # ------------------------------------------------------------------
        print(f"\n=== TIMING ===")
        print(f"  initial TP placed:   +{t_tp_placed - t0:.2f}s from test start")
        if t_fill_detected:
            print(f"  TP fill detected:    +{t_fill_detected - t_watcher_start:.1f}s from watcher start")

        # ------------------------------------------------------------------
        # CHECKS [2-7]
        # ------------------------------------------------------------------
        print("\n=== CHECKS ===")

        # [2] один TP исполнен / [3] watcher detected TP fill
        if fill_detected:
            print("  PASS: TP fill detected (_grid_tp_orders count decreased)")
        else:
            print("  FAIL: TP fill not detected within 60s")
            passed = False

        updated_tp = service._grid_tp_orders.get((symbol, position_side), [])

        # [4] filled TP removed from _grid_tp_orders
        if len(updated_tp) == initial_count - 1:
            print(f"  PASS: _grid_tp_orders reduced from {initial_count} to {len(updated_tp)}")
        else:
            print(f"  FAIL: expected {initial_count - 1} remaining TP, got {len(updated_tp)}")
            passed = False

        # remaining TP должен быть TP2 (дальний, tp_percent=3.0)
        if len(updated_tp) == 1:
            remaining_tp = updated_tp[0]
            if abs(remaining_tp["tp_percent"] - 3.0) < 1e-9:
                print(f"  PASS: remaining TP is TP2 (tp_percent={remaining_tp['tp_percent']}%  order_id={remaining_tp['order_id']})")
            else:
                print(f"  FAIL: remaining TP has unexpected tp_percent={remaining_tp['tp_percent']}")
                passed = False
        elif len(updated_tp) == 0:
            print("  INFO: _grid_tp_orders is empty (both TPs filled)")
        else:
            print(f"  FAIL: expected 1 remaining TP, got {len(updated_tp)}")
            passed = False

        # [5] _base_position_qty обновился до нового positionAmt
        new_position_qty = 0.0
        for pos in exchange.get_positions(symbol):
            if pos["positionSide"] == position_side:
                new_position_qty = abs(float(pos["positionAmt"]))
                break

        recorded_base = service._base_position_qty.get((symbol, position_side), -1.0)
        if abs(recorded_base - new_position_qty) < 1e-8:
            print(f"  PASS: _base_position_qty={recorded_base} matches positionAmt={new_position_qty}")
        else:
            print(f"  FAIL: _base_position_qty={recorded_base} != positionAmt={new_position_qty}")
            passed = False

        # [6] session живая
        current_session = service.get_session(symbol, position_side)
        if current_session is not None:
            print(f"  PASS: session still alive (session_id={current_session.session_id})")
        else:
            print("  FAIL: session gone")
            passed = False

        # [7] remaining TP orders still NEW on exchange
        for i, tp in enumerate(updated_tp):
            try:
                order     = exchange.get_order(symbol, tp["order_id"])
                ex_status = order.get("status")
                if ex_status == "NEW":
                    print(f"  PASS: remaining TP[{i}] order_id={tp['order_id']}  exchange_status={ex_status}")
                else:
                    print(f"  FAIL: remaining TP[{i}] order_id={tp['order_id']}  unexpected status={ex_status}")
                    passed = False
            except Exception as e:
                print(f"  FAIL: remaining TP[{i}] get_order error: {e}")
                passed = False

        if not passed:
            sys.exit(1)

    except Exception as e:
        print(f"\nERROR: {e}")
        raise

    finally:
        watcher.stop_all()
        market_data.stop()

        print("\n=== FINAL CLEANUP ===")

        tp_state = service._grid_tp_orders.get((symbol, position_side), [])
        for tp in tp_state:
            try:
                exchange.cancel_order(symbol, tp["order_id"])
                print(f"  cancelled TP order_id={tp['order_id']}")
            except Exception as e:
                print(f"  cancel TP order_id={tp['order_id']} error: {e}")
        service._grid_tp_orders.pop((symbol, position_side), None)
        service._tp_update_mode.pop((symbol, position_side), None)

        leftover = service.get_session(symbol, position_side)
        if leftover is not None:
            service.stop_session(symbol, position_side)
            print("  stopped session")

        for pos in exchange.get_positions(symbol):
            if pos["positionSide"] == position_side:
                qty = abs(float(pos["positionAmt"]))
                if qty > 0:
                    exchange.close_position(symbol, "buy", qty)
                    print(f"  closed position: qty={qty}")
                break

    print("\nTEST DONE")
