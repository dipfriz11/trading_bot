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

        print(f"  entry_price={entry_price}  qty={opened_qty}")

        # ------------------------------------------------------------------
        # GRID SESSION: levels выше рынка -> pending SELL LIMIT
        # ------------------------------------------------------------------
        current_price = exchange.get_price(symbol)
        first_price   = current_price * 1.050   # +5% above market
        last_price    = current_price * 1.080   # +8% above market

        print(f"\n=== START SHORT GRID SESSION ===")
        print(f"  current_price={current_price:.8f}")
        print(f"  level[1] first_price={first_price:.8f}  (+5% above -> manual fill needed)")
        print(f"  level[2] last_price={last_price:.8f}   (+8% above -> pending)")

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
        # PLACE INITIAL TP ORDERS (based on initial entry_price)
        # TP для SHORT: entry * (1 - tp_pct/100) — ниже entry
        # ------------------------------------------------------------------
        take_profits = [
            {"tp_percent": 1.0, "close_percent": 50},
            {"tp_percent": 2.0, "close_percent": 50},
        ]

        print(f"\n=== PLACE INITIAL TP ORDERS ===")
        print(f"  TP1: -1.0% from entry={entry_price}  -> {entry_price * (1 - 0.010):.8f}  close=50%")
        print(f"  TP2: -2.0% from entry={entry_price}  -> {entry_price * (1 - 0.020):.8f}  close=50%")

        t_initial_start = time.time()
        initial_placed  = service.place_grid_tp_orders(
            symbol=symbol,
            position_side=position_side,
            take_profits=take_profits,
        )
        t_initial_placed = time.time()

        initial_order_ids = {tp["order_id"] for tp in initial_placed}
        initial_prices    = [tp["price"] for tp in initial_placed]
        initial_qtys      = [tp["qty"]   for tp in initial_placed]

        print(f"  initial order_ids: {initial_order_ids}")
        print(f"  initial prices:    {[f'{p:.8f}' for p in initial_prices]}")
        print(f"  initial qtys:      {initial_qtys}")
        print(f"  [TIMING] initial TP placed in {t_initial_placed - t_initial_start:.2f}s")

        level1 = session.levels[0]
        print(f"\n=== MANUAL ACTION REQUIRED ===")
        print(f"  На бирже найди ордер order_id={level1.order_id}")
        print(f"  Текущая цена сейчас ~{exchange.get_price(symbol):.8f}")
        print(f"  Перетащи ордер ВНИЗ ниже текущей цены чтобы он сработал как averaging fill.")
        print(f"  Watcher обнаружит fill и обновит TP ордера автоматически.")
        print(f"  Ожидание до 30s.")

        # ------------------------------------------------------------------
        # START WATCHER
        # watcher: check_grid_fills -> update_grid_tp_orders_fixed
        # ------------------------------------------------------------------
        watcher.start_watching(symbol, position_side)
        t_watcher_start = time.time()
        print(f"\n=== WATCHER STARTED ===")
        print(f"  ждём до 30s — fill level[1] -> update TP orders")

        # ------------------------------------------------------------------
        # WAIT: order_ids в _grid_tp_orders изменятся после update
        # ------------------------------------------------------------------
        deadline         = time.time() + 30
        update_done      = False
        t_fill_detected  = None
        t_update_done_at = None

        while time.time() < deadline:
            current_tp  = service._grid_tp_orders.get((symbol, position_side), [])
            current_ids = {tp["order_id"] for tp in current_tp}

            if current_ids and current_ids != initial_order_ids:
                t_update_done_at = time.time()
                update_done = True
                break

            current_session = service.get_session(symbol, position_side)
            filled_count = sum(
                1 for lvl in (current_session.levels if current_session else [])
                if lvl.status == "filled"
            )
            if filled_count > 0 and t_fill_detected is None:
                t_fill_detected = time.time()
                print(f"  [TIMING] fill detected at +{t_fill_detected - t_watcher_start:.1f}s from watcher start")

            print(f"  waiting... tp_order_ids={current_ids}  filled_levels={filled_count}")
            time.sleep(2.0)

        # ------------------------------------------------------------------
        # TIMING SUMMARY
        # ------------------------------------------------------------------
        print(f"\n=== TIMING ===")
        print(f"  initial TP placed:        +{t_initial_placed - t0:.2f}s from test start")
        if t_fill_detected:
            print(f"  fill detected:            +{t_fill_detected - t_watcher_start:.1f}s from watcher start")
        if t_update_done_at:
            print(f"  TP update done:           +{t_update_done_at - t_watcher_start:.1f}s from watcher start")
            if t_fill_detected:
                print(f"  update lag after fill:    {t_update_done_at - t_fill_detected:.2f}s")

        # ------------------------------------------------------------------
        # CHECKS
        # ------------------------------------------------------------------
        print("\n=== CHECKS ===")
        passed = True

        # [1] update произошёл
        if update_done:
            print("  PASS: TP orders were updated (new order_ids)")
        else:
            print("  FAIL: TP orders not updated within 30s")
            passed = False

        updated_tp = service._grid_tp_orders.get((symbol, position_side), [])

        # [2] цены не изменились (fixed mode)
        prices_ok = (
            len(updated_tp) == len(initial_prices)
            and all(
                abs(updated_tp[i]["price"] - initial_prices[i]) < 1e-9
                for i in range(len(updated_tp))
            )
        )
        if prices_ok:
            print(f"  PASS: TP prices unchanged (fixed mode)")
            for i, tp in enumerate(updated_tp):
                print(f"    TP[{i}] price={tp['price']:.8f}  (was {initial_prices[i]:.8f})")
        else:
            print("  FAIL: TP prices changed unexpectedly")
            passed = False

        # [3] qty суммарно выросло
        sum_initial = sum(initial_qtys)
        sum_updated = sum(tp["qty"] for tp in updated_tp)
        any_grew    = any(
            updated_tp[i]["qty"] > initial_qtys[i]
            for i in range(min(len(updated_tp), len(initial_qtys)))
        )
        if sum_updated > sum_initial and any_grew:
            print(f"  PASS: TP total qty increased after averaging fill")
            print(f"    sum_initial={sum_initial}  sum_updated={sum_updated}")
            for i, tp in enumerate(updated_tp):
                print(f"    TP[{i}] qty={tp['qty']}  (was {initial_qtys[i]})")
        else:
            print(f"  FAIL: TP qty did not increase as expected")
            print(f"    sum_initial={sum_initial}  sum_updated={sum_updated}  any_grew={any_grew}")
            for i, tp in enumerate(updated_tp):
                print(f"    TP[{i}] qty={tp['qty']}  (was {initial_qtys[i] if i < len(initial_qtys) else '?'})")
            passed = False

        # [4] новые ордера видны на бирже как NEW
        for i, tp in enumerate(updated_tp):
            try:
                order     = exchange.get_order(symbol, tp["order_id"])
                ex_status = order.get("status")
                if ex_status == "NEW":
                    print(f"  PASS: TP[{i}] order_id={tp['order_id']}  exchange_status={ex_status}")
                else:
                    print(f"  FAIL: TP[{i}] order_id={tp['order_id']}  unexpected status={ex_status}")
                    passed = False
            except Exception as e:
                print(f"  FAIL: TP[{i}] get_order error: {e}")
                passed = False

        # [5] session живая
        current_session = service.get_session(symbol, position_side)
        if current_session is not None:
            print(f"  PASS: session still alive (session_id={current_session.session_id})")
        else:
            print("  FAIL: session gone after TP update")
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
