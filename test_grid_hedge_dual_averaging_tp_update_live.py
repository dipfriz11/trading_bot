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

        long_first  = current_price * 0.950
        long_last   = current_price * 0.920
        short_first = current_price * 1.050
        short_last  = current_price * 1.080

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
            print(f"    [{lvl.index}] order_id={lvl.order_id}  price={lvl.price:.8f}  qty={lvl.qty}  status={lvl.status}")

        print(f"\n  SHORT session_id: {short_session.session_id}")
        for lvl in short_session.levels:
            print(f"    [{lvl.index}] order_id={lvl.order_id}  price={lvl.price:.8f}  qty={lvl.qty}  status={lvl.status}")

        time.sleep(0.5)

        # ------------------------------------------------------------------
        # PLACE TP ORDERS FOR BOTH SIDES
        # ------------------------------------------------------------------
        print("\n=== PLACE TP ORDERS ===")

        take_profits = [
            {"tp_percent": 5.0, "close_percent": 50},
            {"tp_percent": 10.0, "close_percent": 50},
        ]

        t_tp_start = time.time()

        long_placed = service.place_grid_tp_orders(
            symbol=symbol,
            position_side="LONG",
            take_profits=take_profits,
        )

        short_placed = service.place_grid_tp_orders(
            symbol=symbol,
            position_side="SHORT",
            take_profits=take_profits,
        )

        t_tp_placed = time.time()
        print(f"  [TIMING] both TP sets placed in {t_tp_placed - t_tp_start:.2f}s")

        # -- SNAPSHOT: initial state --
        long_initial_ids    = {tp["order_id"] for tp in long_placed}
        long_initial_prices = [tp["price"] for tp in long_placed]
        long_initial_qtys   = [tp["qty"]   for tp in long_placed]

        short_initial_ids    = {tp["order_id"] for tp in short_placed}
        short_initial_prices = [tp["price"] for tp in short_placed]
        short_initial_qtys   = [tp["qty"]   for tp in short_placed]

        print(f"\n  LONG  initial TP ids:    {long_initial_ids}")
        print(f"  LONG  initial TP prices: {[f'{p:.8f}' for p in long_initial_prices]}")
        print(f"  LONG  initial TP qtys:   {long_initial_qtys}")
        print(f"\n  SHORT initial TP ids:    {short_initial_ids}")
        print(f"  SHORT initial TP prices: {[f'{p:.8f}' for p in short_initial_prices]}")
        print(f"  SHORT initial TP qtys:   {short_initial_qtys}")

        # ------------------------------------------------------------------
        # START WATCHER FOR BOTH SIDES
        # ------------------------------------------------------------------
        print("\n=== START WATCHER FOR BOTH SIDES ===")
        watcher.start_watching(symbol, "LONG")
        watcher.start_watching(symbol, "SHORT")
        print(f"  watcher watching: {list(watcher._watched.keys())}")

        # ==================================================================
        # STEP A — averaging fill на LONG
        # ==================================================================
        long_level1 = long_session.levels[0]
        print(f"\n=== STEP A: MANUAL ACTION — LONG averaging fill ===")
        print(f"  LONG level[1] order_id={long_level1.order_id}  price={long_level1.price:.8f}")
        print(f"  Текущая цена ~{exchange.get_price(symbol):.8f}")
        print(f"  Перетащи LONG grid ордер ВВЕРХ выше текущей цены -> averaging fill.")
        print(f"  SHORT сторону НЕ трогать.")
        print(f"  Ожидание до 30s.")

        t_a_start   = time.time()
        step_a_done = False
        t_a_fill    = None
        t_a_update  = None

        while time.time() < t_a_start + 30:
            long_current_tp  = service._grid_tp_orders.get((symbol, "LONG"), [])
            long_current_ids = {tp["order_id"] for tp in long_current_tp}

            if long_current_ids and long_current_ids != long_initial_ids:
                t_a_update  = time.time()
                step_a_done = True
                break

            long_filled = sum(1 for lvl in long_session.levels if lvl.status == "filled")
            if long_filled > 0 and t_a_fill is None:
                t_a_fill = time.time()
                print(f"  [TIMING] LONG fill detected at +{t_a_fill - t_a_start:.1f}s")

            print(f"  waiting... LONG tp_ids={long_current_ids}  filled={long_filled}")
            time.sleep(2.0)

        if not step_a_done:
            print("FAIL: LONG averaging fill not detected in Step A — aborting")
            sys.exit(1)

        print(f"  [TIMING] LONG TP update done at +{t_a_update - t_a_start:.1f}s from step A start")
        if t_a_fill:
            print(f"  [TIMING] LONG update lag: {t_a_update - t_a_fill:.2f}s")

        # -- SNAPSHOT: post-A state --
        long_after_a_tp     = service._grid_tp_orders.get((symbol, "LONG"), [])
        long_after_a_ids    = {tp["order_id"] for tp in long_after_a_tp}
        long_after_a_prices = [tp["price"] for tp in long_after_a_tp]
        long_after_a_qtys   = [tp["qty"]   for tp in long_after_a_tp]

        short_after_a_tp     = service._grid_tp_orders.get((symbol, "SHORT"), [])
        short_after_a_ids    = {tp["order_id"] for tp in short_after_a_tp}
        short_after_a_prices = [tp["price"] for tp in short_after_a_tp]
        short_after_a_qtys   = [tp["qty"]   for tp in short_after_a_tp]

        print(f"\n  [POST-A] LONG  ids={long_after_a_ids}  qtys={long_after_a_qtys}")
        print(f"  [POST-A] SHORT ids={short_after_a_ids}  qtys={short_after_a_qtys}")

        # ==================================================================
        # STEP B — averaging fill на SHORT
        # ==================================================================
        short_level1 = short_session.levels[0]
        print(f"\n=== STEP B: MANUAL ACTION — SHORT averaging fill ===")
        print(f"  SHORT level[1] order_id={short_level1.order_id}  price={short_level1.price:.8f}")
        print(f"  Текущая цена ~{exchange.get_price(symbol):.8f}")
        print(f"  Перетащи SHORT grid ордер ВНИЗ ниже текущей цены -> averaging fill.")
        print(f"  LONG сторону НЕ трогать.")
        print(f"  Ожидание до 30s.")

        t_b_start   = time.time()
        step_b_done = False
        t_b_fill    = None
        t_b_update  = None

        while time.time() < t_b_start + 30:
            short_current_tp  = service._grid_tp_orders.get((symbol, "SHORT"), [])
            short_current_ids = {tp["order_id"] for tp in short_current_tp}

            if short_current_ids and short_current_ids != short_initial_ids:
                t_b_update  = time.time()
                step_b_done = True
                break

            short_filled = sum(1 for lvl in short_session.levels if lvl.status == "filled")
            if short_filled > 0 and t_b_fill is None:
                t_b_fill = time.time()
                print(f"  [TIMING] SHORT fill detected at +{t_b_fill - t_b_start:.1f}s")

            print(f"  waiting... SHORT tp_ids={short_current_ids}  filled={short_filled}")
            time.sleep(2.0)

        if not step_b_done:
            print("FAIL: SHORT averaging fill not detected in Step B — aborting")
            sys.exit(1)

        print(f"  [TIMING] SHORT TP update done at +{t_b_update - t_b_start:.1f}s from step B start")
        if t_b_fill:
            print(f"  [TIMING] SHORT update lag: {t_b_update - t_b_fill:.2f}s")

        # -- SNAPSHOT: post-B state --
        long_after_b_tp     = service._grid_tp_orders.get((symbol, "LONG"), [])
        long_after_b_ids    = {tp["order_id"] for tp in long_after_b_tp}
        long_after_b_prices = [tp["price"] for tp in long_after_b_tp]
        long_after_b_qtys   = [tp["qty"]   for tp in long_after_b_tp]

        short_after_b_tp     = service._grid_tp_orders.get((symbol, "SHORT"), [])
        short_after_b_ids    = {tp["order_id"] for tp in short_after_b_tp}
        short_after_b_prices = [tp["price"] for tp in short_after_b_tp]
        short_after_b_qtys   = [tp["qty"]   for tp in short_after_b_tp]

        print(f"\n  [POST-B] LONG  ids={long_after_b_ids}  qtys={long_after_b_qtys}")
        print(f"  [POST-B] SHORT ids={short_after_b_ids}  qtys={short_after_b_qtys}")

        # ------------------------------------------------------------------
        # TIMING SUMMARY
        # ------------------------------------------------------------------
        print(f"\n=== TIMING SUMMARY ===")
        print(f"  positions opened:      +{t_positions_opened - t0:.2f}s from test start")
        print(f"  sessions started:      +{t_sessions_started - t0:.2f}s from test start")
        print(f"  TP placed:             +{t_tp_placed - t0:.2f}s from test start")
        if t_a_fill:
            print(f"  LONG fill detected:    +{t_a_fill - t_a_start:.1f}s from step A start")
        if t_a_update:
            print(f"  LONG TP update done:   +{t_a_update - t_a_start:.1f}s from step A start")
        if t_b_fill:
            print(f"  SHORT fill detected:   +{t_b_fill - t_b_start:.1f}s from step B start")
        if t_b_update:
            print(f"  SHORT TP update done:  +{t_b_update - t_b_start:.1f}s from step B start")

        # ------------------------------------------------------------------
        # CHECKS
        # ------------------------------------------------------------------
        print("\n=== CHECKS ===")
        passed = True

        # [1] обе позиции открыты
        if long_qty > 0:
            print(f"  PASS: LONG position opened  entry={long_entry:.8f}  qty={long_qty}")
        else:
            print("  FAIL: LONG position not opened")
            passed = False

        if short_qty > 0:
            print(f"  PASS: SHORT position opened  entry={short_entry:.8f}  qty={short_qty}")
        else:
            print("  FAIL: SHORT position not opened")
            passed = False

        # [2] обе session созданы
        long_s  = service.get_session(symbol, "LONG")
        short_s = service.get_session(symbol, "SHORT")

        if long_s is not None:
            print(f"  PASS: LONG session alive  session_id={long_s.session_id}")
        else:
            print("  FAIL: LONG session gone")
            passed = False

        if short_s is not None:
            print(f"  PASS: SHORT session alive  session_id={short_s.session_id}")
        else:
            print("  FAIL: SHORT session gone")
            passed = False

        # [3] initial TP placed for both sides
        if len(long_initial_ids) == len(take_profits):
            print(f"  PASS: LONG initial TP placed  count={len(long_initial_ids)}")
        else:
            print(f"  FAIL: LONG initial TP count={len(long_initial_ids)}")
            passed = False

        if len(short_initial_ids) == len(take_profits):
            print(f"  PASS: SHORT initial TP placed  count={len(short_initial_ids)}")
        else:
            print(f"  FAIL: SHORT initial TP count={len(short_initial_ids)}")
            passed = False

        # [4] LONG averaging update happened (Step A)
        if step_a_done:
            print("  PASS: LONG averaging update completed (Step A)")
        else:
            print("  FAIL: LONG averaging update not detected")
            passed = False

        if long_after_a_ids != long_initial_ids:
            print(f"  PASS: LONG TP order_ids changed after step A")
        else:
            print(f"  FAIL: LONG TP order_ids unchanged after step A")
            passed = False

        sum_long_init    = sum(long_initial_qtys)
        sum_long_after_a = sum(long_after_a_qtys)
        if sum_long_after_a > sum_long_init:
            print(f"  PASS: LONG TP qty increased  {sum_long_init} -> {sum_long_after_a}")
        else:
            print(f"  FAIL: LONG TP qty not increased  {sum_long_init} -> {sum_long_after_a}")
            passed = False

        long_prices_fixed = (
            len(long_after_a_tp) == len(long_initial_prices)
            and all(
                abs(long_after_a_tp[i]["price"] - long_initial_prices[i]) < 1e-9
                for i in range(len(long_after_a_tp))
            )
        )
        if long_prices_fixed:
            print(f"  PASS: LONG TP prices unchanged (fixed mode)")
        else:
            print(f"  FAIL: LONG TP prices changed unexpectedly")
            passed = False

        # [5] SHORT untouched after LONG step (post-A snapshot)
        if short_after_a_ids == short_initial_ids:
            print(f"  PASS: SHORT TP order_ids unchanged after step A")
        else:
            print(f"  FAIL: SHORT TP order_ids changed after step A  {short_initial_ids} -> {short_after_a_ids}")
            passed = False

        if short_after_a_qtys == short_initial_qtys:
            print(f"  PASS: SHORT TP qty unchanged after step A")
        else:
            print(f"  FAIL: SHORT TP qty changed after step A  {short_initial_qtys} -> {short_after_a_qtys}")
            passed = False

        if short_after_a_prices == short_initial_prices:
            print(f"  PASS: SHORT TP prices unchanged after step A")
        else:
            print(f"  FAIL: SHORT TP prices changed after step A")
            passed = False

        # [6] SHORT averaging update happened (Step B)
        if step_b_done:
            print("  PASS: SHORT averaging update completed (Step B)")
        else:
            print("  FAIL: SHORT averaging update not detected")
            passed = False

        if short_after_b_ids != short_initial_ids:
            print(f"  PASS: SHORT TP order_ids changed after step B")
        else:
            print(f"  FAIL: SHORT TP order_ids unchanged after step B")
            passed = False

        sum_short_init    = sum(short_initial_qtys)
        sum_short_after_b = sum(short_after_b_qtys)
        if sum_short_after_b > sum_short_init:
            print(f"  PASS: SHORT TP qty increased  {sum_short_init} -> {sum_short_after_b}")
        else:
            print(f"  FAIL: SHORT TP qty not increased  {sum_short_init} -> {sum_short_after_b}")
            passed = False

        short_prices_fixed = (
            len(short_after_b_tp) == len(short_initial_prices)
            and all(
                abs(short_after_b_tp[i]["price"] - short_initial_prices[i]) < 1e-9
                for i in range(len(short_after_b_tp))
            )
        )
        if short_prices_fixed:
            print(f"  PASS: SHORT TP prices unchanged (fixed mode)")
        else:
            print(f"  FAIL: SHORT TP prices changed unexpectedly")
            passed = False

        # [7] LONG state preserved after SHORT step (post-B == post-A)
        if long_after_b_ids == long_after_a_ids:
            print(f"  PASS: LONG TP order_ids preserved after step B")
        else:
            print(f"  FAIL: LONG TP order_ids changed during step B  {long_after_a_ids} -> {long_after_b_ids}")
            passed = False

        if long_after_b_qtys == long_after_a_qtys:
            print(f"  PASS: LONG TP qty preserved after step B")
        else:
            print(f"  FAIL: LONG TP qty changed during step B  {long_after_a_qtys} -> {long_after_b_qtys}")
            passed = False

        if long_after_b_prices == long_after_a_prices:
            print(f"  PASS: LONG TP prices preserved after step B")
        else:
            print(f"  FAIL: LONG TP prices changed during step B")
            passed = False

        # [8] обе session alive
        if long_s is not None and short_s is not None:
            print(f"  PASS: both sessions still alive")
        else:
            print(f"  FAIL: one or both sessions gone")
            passed = False

        # [9] watcher watching both sides
        watches_long  = (symbol, "LONG")  in watcher._watched
        watches_short = (symbol, "SHORT") in watcher._watched
        if watches_long and watches_short:
            print(f"  PASS: watcher still watching both sides")
        else:
            print(f"  FAIL: watcher lost a side  LONG={watches_long}  SHORT={watches_short}")
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
