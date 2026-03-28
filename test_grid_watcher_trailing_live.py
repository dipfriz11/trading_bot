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
        # --- START SESSION ---
        session = service.start_session(
            symbol=symbol,
            position_side="LONG",
            total_budget=300.0,
            levels_count=5,
            step_percent=1.0,
            qty_mode="fixed",
            orders_count=5,
            first_offset_percent=2.0,
            last_offset_percent=4.0,
            distribution_mode="step",
            distribution_value=1.0,
        )

        # --- ENABLE TRAILING ---
        anchor_price = service.enable_trailing(
            symbol=symbol,
            position_side="LONG",
            trailing_step_percent=1.0,
            first_offset_percent=2.0,
            last_offset_percent=4.0,
            total_budget=300.0,
            orders_count=5,
            distribution_mode="step",
            distribution_value=1.0,
        )

        # --- SNAPSHOT BEFORE ---
        order_ids_before = [lvl.order_id for lvl in session.levels]
        prices_before    = [lvl.price for lvl in session.levels]
        qtys_before      = [lvl.qty for lvl in session.levels]

        print(f"\n=== SESSION STARTED ===")
        print(f"session_id:   {session.session_id}")
        print(f"anchor_price: {anchor_price}")
        print("levels:")
        for lvl in session.levels:
            print(f"  [{lvl.index}] order_id={lvl.order_id}  price={lvl.price}  qty={lvl.qty}")

        # --- START WATCHING ---
        watcher.start_watching(symbol, sides=["LONG"])
        print(f"\n=== WATCHER STARTED ===")
        print(f"subscribed to {symbol}, waiting for first market data tick...")

        # --- WAIT FOR FIRST TICK ---
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

        # --- FORCE ANCHOR ---
        current_price = exchange.get_price(symbol)
        anchor_before_force = service._trailing_configs[(symbol, "LONG")].anchor_price
        service._trailing_configs[(symbol, "LONG")].anchor_price = current_price * 0.97
        forced_anchor = service._trailing_configs[(symbol, "LONG")].anchor_price

        print(f"\n=== ANCHOR FORCED ===")
        print(f"current_price:      {current_price}")
        print(f"anchor_before:      {anchor_before_force}")
        print(f"forced_anchor:      {forced_anchor}")
        print(f"trigger threshold:  {forced_anchor * 1.01:.8f}")
        print(f"waiting for watcher to trigger automatically...")

        # --- WAIT FOR AUTOMATIC TRIGGER ---
        trigger_deadline = time.time() + 30
        triggered = False
        while time.time() < trigger_deadline:
            prices_now = [lvl.price for lvl in session.levels]
            if prices_now != prices_before:
                triggered = True
                break
            time.sleep(0.5)

        # --- SNAPSHOT AFTER ---
        order_ids_after = [lvl.order_id for lvl in session.levels]
        prices_after    = [lvl.price for lvl in session.levels]
        qtys_after      = [lvl.qty for lvl in session.levels]

        print(f"\n=== AFTER WATCHER TRIGGER ===")
        print(f"triggered: {triggered}")
        print("levels:")
        for lvl in session.levels:
            print(f"  [{lvl.index}] order_id={lvl.order_id}  price={lvl.price}  qty={lvl.qty}  status={lvl.status}")
        print(f"order_ids_after: {order_ids_after}")
        print(f"prices_after:    {prices_after}")
        print(f"qtys_after:      {qtys_after}")

        # --- CHECKS ---
        print(f"\n=== CHECKS ===")

        if triggered:
            print(f"  PASS: watcher triggered automatically")
        else:
            print(f"  FAIL: watcher did not trigger within 30s")
            sys.exit(1)

        if order_ids_before == order_ids_after:
            print(f"  PASS: order_ids preserved")
        else:
            print(f"  FAIL: order_ids changed")
            print(f"    before: {order_ids_before}")
            print(f"    after:  {order_ids_after}")
            sys.exit(1)

        if prices_before != prices_after:
            print(f"  PASS: prices changed")
        else:
            print(f"  FAIL: prices did not change")
            sys.exit(1)

        if qtys_before != qtys_after:
            print(f"  PASS: qtys changed")
        else:
            print(f"  FAIL: qtys did not change")
            sys.exit(1)

        if all(lvl.status == "placed" for lvl in session.levels):
            print(f"  PASS: all levels still placed")
        else:
            for lvl in session.levels:
                if lvl.status != "placed":
                    print(f"  FAIL: level [{lvl.index}] has status={lvl.status!r}")
            sys.exit(1)

        # --- STOP WATCHING ---
        watcher.stop_watching(symbol)
        print(f"\n=== WATCHER STOPPED ===")

        # --- STOP SESSION ---
        stopped = service.stop_session(symbol, "LONG")
        print(f"\n=== SESSION STOPPED ===")
        print(f"  status: {stopped.status}")
        for lvl in stopped.levels:
            print(f"  [{lvl.index}] status={lvl.status}  order_id={lvl.order_id}")

        # --- CHECK TRAILING CONFIG REMOVED ---
        config_after_stop = service._trailing_configs.get((symbol, "LONG"))
        if config_after_stop is None:
            print(f"\n  PASS: trailing config removed after stop_session")
        else:
            print(f"\n  FAIL: trailing config still present after stop_session")
            sys.exit(1)

    except Exception as e:
        print(f"\nERROR: {e}")

    finally:
        watcher.stop_all()
        market_data.stop()
        remaining = service.get_session(symbol, "LONG")
        if remaining is not None:
            print("\n=== FALLBACK CLEANUP ===")
            stopped = service.stop_session(symbol, "LONG")
            print(f"  status: {stopped.status}")
            for lvl in stopped.levels:
                print(f"  [{lvl.index}] status={lvl.status}  order_id={lvl.order_id}")

    print("\nTEST DONE")
