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

    try:
        # ------------------------------------------------------------------
        # START LONG SESSION
        # ------------------------------------------------------------------
        session_long = service.start_session(
            symbol=symbol,
            position_side="LONG",
            total_budget=150.0,
            levels_count=5,
            step_percent=1.0,
            qty_mode="fixed",
            orders_count=5,
            first_offset_percent=2.0,
            last_offset_percent=4.0,
            distribution_mode="step",
            distribution_value=1.0,
        )

        anchor_long = service.enable_trailing(
            symbol=symbol,
            position_side="LONG",
            trailing_step_percent=1.0,
            first_offset_percent=2.0,
            last_offset_percent=4.0,
            total_budget=150.0,
            orders_count=5,
            distribution_mode="step",
            distribution_value=1.0,
        )

        order_ids_long_before = [lvl.order_id for lvl in session_long.levels]
        prices_long_before    = [lvl.price    for lvl in session_long.levels]

        print(f"\n=== LONG SESSION STARTED ===")
        print(f"session_id:   {session_long.session_id}")
        print(f"anchor_price: {anchor_long}")
        print("levels:")
        for lvl in session_long.levels:
            print(f"  [{lvl.index}] order_id={lvl.order_id}  price={lvl.price}  qty={lvl.qty}  status={lvl.status}")

        # ------------------------------------------------------------------
        # START SHORT SESSION (LONG stays alive)
        # ------------------------------------------------------------------
        session_short = service.start_session(
            symbol=symbol,
            position_side="SHORT",
            total_budget=150.0,
            levels_count=5,
            step_percent=1.0,
            qty_mode="fixed",
            orders_count=5,
            first_offset_percent=2.0,
            last_offset_percent=4.0,
            distribution_mode="step",
            distribution_value=1.0,
        )

        anchor_short = service.enable_trailing(
            symbol=symbol,
            position_side="SHORT",
            trailing_step_percent=1.0,
            first_offset_percent=2.0,
            last_offset_percent=4.0,
            total_budget=150.0,
            orders_count=5,
            distribution_mode="step",
            distribution_value=1.0,
        )

        order_ids_short_before = [lvl.order_id for lvl in session_short.levels]
        prices_short_before    = [lvl.price    for lvl in session_short.levels]

        print(f"\n=== SHORT SESSION STARTED (LONG still alive) ===")
        print(f"session_id:   {session_short.session_id}")
        print(f"anchor_price: {anchor_short}")
        print("levels:")
        for lvl in session_short.levels:
            print(f"  [{lvl.index}] order_id={lvl.order_id}  price={lvl.price}  qty={lvl.qty}  status={lvl.status}")

        # ------------------------------------------------------------------
        # START WATCHER — both legs
        # ------------------------------------------------------------------
        watcher.start_watching(symbol, "LONG")
        watcher.start_watching(symbol, "SHORT")
        print(f"\n=== WATCHER STARTED (LONG + SHORT) ===")
        print(f"subscribed to {symbol}, waiting for first market data tick...")

        # ------------------------------------------------------------------
        # WAIT FOR FIRST TICK
        # ------------------------------------------------------------------
        tick_deadline = time.time() + 15
        first_price = None
        while time.time() < tick_deadline:
            first_price = market_data.get_latest_price(symbol)
            if first_price is not None:
                break
            time.sleep(0.3)

        if first_price is None:
            print(f"FAIL: no market data tick received within 15s")
            sys.exit(1)

        print(f"first tick received: {first_price}")

        # ------------------------------------------------------------------
        # FORCE ANCHOR: LONG + SHORT
        # ------------------------------------------------------------------
        current_price = exchange.get_price(symbol)

        service._trailing_configs[(symbol, "LONG")].anchor_price  = current_price * 0.97
        service._trailing_configs[(symbol, "SHORT")].anchor_price = current_price * 1.03

        forced_anchor_long  = service._trailing_configs[(symbol, "LONG")].anchor_price
        forced_anchor_short = service._trailing_configs[(symbol, "SHORT")].anchor_price

        print(f"\n=== ANCHOR FORCED ===")
        print(f"current_price:        {current_price}")
        print(f"LONG  forced_anchor:  {forced_anchor_long}  (threshold: {forced_anchor_long  * 1.01:.8f})")
        print(f"SHORT forced_anchor:  {forced_anchor_short} (threshold: {forced_anchor_short * 0.99:.8f})")
        print(f"waiting for watcher to trigger both legs automatically...")

        # ------------------------------------------------------------------
        # WAIT FOR BOTH LEGS TO TRIGGER
        # ------------------------------------------------------------------
        trigger_deadline = time.time() + 30
        triggered_long  = False
        triggered_short = False

        while time.time() < trigger_deadline:
            prices_long_now  = [lvl.price for lvl in session_long.levels]
            prices_short_now = [lvl.price for lvl in session_short.levels]
            if prices_long_now  != prices_long_before:
                triggered_long  = True
            if prices_short_now != prices_short_before:
                triggered_short = True
            if triggered_long and triggered_short:
                break
            time.sleep(0.5)

        # ------------------------------------------------------------------
        # SNAPSHOTS AFTER
        # ------------------------------------------------------------------
        order_ids_long_after  = [lvl.order_id for lvl in session_long.levels]
        prices_long_after     = [lvl.price    for lvl in session_long.levels]

        order_ids_short_after = [lvl.order_id for lvl in session_short.levels]
        prices_short_after    = [lvl.price    for lvl in session_short.levels]

        config_long_alive  = service._trailing_configs.get((symbol, "LONG"))  is not None
        config_short_alive = service._trailing_configs.get((symbol, "SHORT")) is not None

        print(f"\n=== AFTER TRIGGER ===")
        print("LONG levels:")
        for lvl in session_long.levels:
            print(f"  [{lvl.index}] order_id={lvl.order_id}  price={lvl.price}  qty={lvl.qty}  status={lvl.status}")
        print("SHORT levels:")
        for lvl in session_short.levels:
            print(f"  [{lvl.index}] order_id={lvl.order_id}  price={lvl.price}  qty={lvl.qty}  status={lvl.status}")

        # ------------------------------------------------------------------
        # CHECKS
        # ------------------------------------------------------------------
        print(f"\n=== CHECKS ===")
        passed = True

        if triggered_long:
            print(f"  PASS: LONG triggered")
        else:
            print(f"  FAIL: LONG did not trigger within 30s")
            passed = False

        if triggered_short:
            print(f"  PASS: SHORT triggered")
        else:
            print(f"  FAIL: SHORT did not trigger within 30s")
            passed = False

        if order_ids_long_before == order_ids_long_after:
            print(f"  PASS: LONG order_ids preserved")
        else:
            print(f"  FAIL: LONG order_ids changed")
            print(f"    before: {order_ids_long_before}")
            print(f"    after:  {order_ids_long_after}")
            passed = False

        if order_ids_short_before == order_ids_short_after:
            print(f"  PASS: SHORT order_ids preserved")
        else:
            print(f"  FAIL: SHORT order_ids changed")
            print(f"    before: {order_ids_short_before}")
            print(f"    after:  {order_ids_short_after}")
            passed = False

        if prices_long_before != prices_long_after:
            print(f"  PASS: LONG prices changed")
        else:
            print(f"  FAIL: LONG prices did not change")
            passed = False

        if prices_short_before != prices_short_after:
            print(f"  PASS: SHORT prices changed")
        else:
            print(f"  FAIL: SHORT prices did not change")
            passed = False

        if all(lvl.status == "placed" for lvl in session_long.levels):
            print(f"  PASS: all LONG levels still placed")
        else:
            for lvl in session_long.levels:
                if lvl.status != "placed":
                    print(f"  FAIL: LONG level [{lvl.index}] has status={lvl.status!r}")
            passed = False

        if all(lvl.status == "placed" for lvl in session_short.levels):
            print(f"  PASS: all SHORT levels still placed")
        else:
            for lvl in session_short.levels:
                if lvl.status != "placed":
                    print(f"  FAIL: SHORT level [{lvl.index}] has status={lvl.status!r}")
            passed = False

        if config_long_alive:
            print(f"  PASS: LONG trailing config alive after SHORT trigger")
        else:
            print(f"  FAIL: LONG trailing config was killed by SHORT")
            passed = False

        if config_short_alive:
            print(f"  PASS: SHORT trailing config alive after LONG trigger")
        else:
            print(f"  FAIL: SHORT trailing config was killed by LONG")
            passed = False

        if not passed:
            sys.exit(1)

        # ------------------------------------------------------------------
        # STOP WATCHER
        # ------------------------------------------------------------------
        watcher.stop_watching(symbol, "LONG")
        watcher.stop_watching(symbol, "SHORT")
        print(f"\n=== WATCHER STOPPED (LONG + SHORT) ===")

        # ------------------------------------------------------------------
        # STOP SESSIONS
        # ------------------------------------------------------------------
        stopped_long  = service.stop_session(symbol, "LONG")
        stopped_short = service.stop_session(symbol, "SHORT")

        print(f"\n=== SESSIONS STOPPED ===")
        print(f"LONG  status: {stopped_long.status}")
        for lvl in stopped_long.levels:
            print(f"  [{lvl.index}] status={lvl.status}  order_id={lvl.order_id}")
        print(f"SHORT status: {stopped_short.status}")
        for lvl in stopped_short.levels:
            print(f"  [{lvl.index}] status={lvl.status}  order_id={lvl.order_id}")

        # ------------------------------------------------------------------
        # CHECK TRAILING CONFIGS REMOVED
        # ------------------------------------------------------------------
        print(f"\n=== CLEANUP CHECKS ===")

        if service._trailing_configs.get((symbol, "LONG")) is None:
            print(f"  PASS: LONG trailing config removed after stop_session")
        else:
            print(f"  FAIL: LONG trailing config still present after stop_session")
            sys.exit(1)

        if service._trailing_configs.get((symbol, "SHORT")) is None:
            print(f"  PASS: SHORT trailing config removed after stop_session")
        else:
            print(f"  FAIL: SHORT trailing config still present after stop_session")
            sys.exit(1)

    except Exception as e:
        print(f"\nERROR: {e}")
        raise

    finally:
        watcher.stop_all()
        market_data.stop()

        for ps in ("LONG", "SHORT"):
            remaining = service.get_session(symbol, ps)
            if remaining is not None:
                print(f"\n=== FALLBACK CLEANUP: {ps} ===")
                stopped = service.stop_session(symbol, ps)
                print(f"  status: {stopped.status}")
                for lvl in stopped.levels:
                    print(f"  [{lvl.index}] status={lvl.status}  order_id={lvl.order_id}")

    print("\nTEST DONE")
