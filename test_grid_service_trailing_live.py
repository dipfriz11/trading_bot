import sys

from trading_core.grid.grid_sizer import GridSizer
from exchange.binance_exchange import BinanceExchange
from trading_core.grid.grid_builder import GridBuilder
from trading_core.grid.grid_runner import GridRunner
from trading_core.grid.grid_registry import GridRegistry
from trading_core.grid.grid_service import GridService

if __name__ == "__main__":

    exchange = BinanceExchange()
    builder = GridBuilder()
    runner = GridRunner(exchange)
    registry = GridRegistry()
    sizer = GridSizer()
    service = GridService(builder, runner, registry, exchange, sizer)

    symbol = "SIRENUSDT"

    # -------------------------------------------------------
    # LIVE: LONG trailing
    # -------------------------------------------------------
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

        order_ids_before = [lvl.order_id for lvl in session.levels]
        prices_before    = [lvl.price for lvl in session.levels]
        qtys_before      = [lvl.qty for lvl in session.levels]

        print(f"\n=== TRAILING ENABLED ===")
        print(f"session_id:            {session.session_id}")
        print(f"anchor_price:          {anchor_price}")
        print(f"trailing_step_percent: 1.0")
        print(f"first_offset_percent:  2.0")
        print(f"last_offset_percent:   4.0")
        print("levels:")
        for lvl in session.levels:
            print(f"  [{lvl.index}] order_id={lvl.order_id}  price={lvl.price}  qty={lvl.qty}  status={lvl.status}")
        print(f"order_ids_before: {order_ids_before}")
        print(f"prices_before:    {prices_before}")
        print(f"qtys_before:      {qtys_before}")

        input("\nПроверь ордера на бирже ДО trigger и нажми Enter...")

        # --- FORCE TRIGGER ---
        current_price = exchange.get_price(symbol)
        anchor_price_before_force = service._trailing_configs[(symbol, "LONG")].anchor_price
        service._trailing_configs[(symbol, "LONG")].anchor_price = current_price * 0.97
        forced_anchor = service._trailing_configs[(symbol, "LONG")].anchor_price

        print(f"\n=== FORCING TRIGGER ===")
        print(f"anchor_price_before_force: {anchor_price_before_force}")
        print(f"forced_anchor:             {forced_anchor}")
        print(f"trigger threshold:         {forced_anchor * 1.01:.8f}")
        print(f"current_price:             {current_price}  -> trigger should fire")

        # --- CHECK TRAILING ---
        result = service.check_trailing(symbol, "LONG", price=current_price)

        # --- AFTER TRIGGER ---
        order_ids_after          = [lvl.order_id for lvl in session.levels]
        prices_after             = [lvl.price for lvl in session.levels]
        qtys_after               = [lvl.qty for lvl in session.levels]
        anchor_price_after_check = service._trailing_configs[(symbol, "LONG")].anchor_price

        print(f"\n=== AFTER TRAILING CHECK ===")
        print(f"result: {result}")
        print("levels:")
        for lvl in session.levels:
            print(f"  [{lvl.index}] order_id={lvl.order_id}  price={lvl.price}  qty={lvl.qty}  status={lvl.status}")
        print(f"order_ids_after:          {order_ids_after}")
        print(f"prices_after:             {prices_after}")
        print(f"qtys_after:               {qtys_after}")
        print(f"anchor_price_after_check: {anchor_price_after_check}")

        # --- CHECKS ---
        print(f"\n=== CHECKS ===")

        if result is not None:
            print(f"  PASS: check_trailing returned session")
        else:
            print(f"  FAIL: check_trailing returned None — trigger did not fire")
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

        if anchor_price_after_check != forced_anchor:
            print(f"  PASS: anchor_price updated  ({forced_anchor} -> {anchor_price_after_check})")
        else:
            print(f"  FAIL: anchor_price was not updated after trigger")
            sys.exit(1)

        if all(lvl.status == "placed" for lvl in session.levels):
            print(f"  PASS: all levels still placed")
        else:
            for lvl in session.levels:
                if lvl.status != "placed":
                    print(f"  FAIL: level [{lvl.index}] has status={lvl.status!r}")
            sys.exit(1)

        input("\nПроверь ордера на бирже ПОСЛЕ trigger и нажми Enter...")

        # --- SECOND CHECK (no trigger expected) ---
        result2 = service.check_trailing(symbol, "LONG", price=current_price)
        if result2 is None:
            print(f"\n  PASS: second check_trailing returned None (no trigger without price movement)")
        else:
            print(f"\n  FAIL: expected None on second check, got session")
            sys.exit(1)

        # --- STOP SESSION ---
        stopped = service.stop_session(symbol, "LONG")
        print(f"\n=== STOPPED ===")
        print(f"  status: {stopped.status}")
        for lvl in stopped.levels:
            print(f"  [{lvl.index}] status={lvl.status}  order_id={lvl.order_id}")

        # --- CHECK DISABLE TRAILING ---
        config_after_stop = service._trailing_configs.get((symbol, "LONG"))
        if config_after_stop is None:
            print(f"\n  PASS: trailing config removed after stop_session")
        else:
            print(f"\n  FAIL: trailing config still present after stop_session")
            sys.exit(1)

    except Exception as e:
        print(f"\nERROR: {e}")

    finally:
        remaining = service.get_session(symbol, "LONG")
        if remaining is not None:
            print("\n=== FALLBACK CLEANUP ===")
            stopped = service.stop_session(symbol, "LONG")
            print(f"  status: {stopped.status}")
            for lvl in stopped.levels:
                print(f"  [{lvl.index}] status={lvl.status}  order_id={lvl.order_id}")

    # -------------------------------------------------------
    # LIVE: SHORT trailing
    # -------------------------------------------------------
    try:
        # --- START SESSION ---
        session = service.start_session(
            symbol=symbol,
            position_side="SHORT",
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
            position_side="SHORT",
            trailing_step_percent=1.0,
            first_offset_percent=2.0,
            last_offset_percent=4.0,
            total_budget=300.0,
            orders_count=5,
            distribution_mode="step",
            distribution_value=1.0,
        )

        order_ids_before = [lvl.order_id for lvl in session.levels]
        prices_before    = [lvl.price for lvl in session.levels]
        qtys_before      = [lvl.qty for lvl in session.levels]

        print(f"\n=== SHORT TRAILING ENABLED ===")
        print(f"session_id:            {session.session_id}")
        print(f"anchor_price:          {anchor_price}")
        print(f"trailing_step_percent: 1.0")
        print(f"first_offset_percent:  2.0")
        print(f"last_offset_percent:   4.0")
        print("levels:")
        for lvl in session.levels:
            print(f"  [{lvl.index}] order_id={lvl.order_id}  price={lvl.price}  qty={lvl.qty}  status={lvl.status}")
        print(f"order_ids_before: {order_ids_before}")
        print(f"prices_before:    {prices_before}")
        print(f"qtys_before:      {qtys_before}")

        input("\nПроверь SHORT ордера на бирже ДО trigger и нажми Enter...")

        # --- FORCE TRIGGER ---
        current_price = exchange.get_price(symbol)
        anchor_price_before_force = service._trailing_configs[(symbol, "SHORT")].anchor_price
        service._trailing_configs[(symbol, "SHORT")].anchor_price = current_price * 1.03
        forced_anchor = service._trailing_configs[(symbol, "SHORT")].anchor_price

        print(f"\n=== SHORT FORCING TRIGGER ===")
        print(f"anchor_price_before_force: {anchor_price_before_force}")
        print(f"forced_anchor:             {forced_anchor}")
        print(f"trigger threshold:         {forced_anchor * 0.99:.8f}")
        print(f"current_price:             {current_price}  -> trigger should fire")

        # --- CHECK TRAILING ---
        result = service.check_trailing(symbol, "SHORT", price=current_price)

        # --- AFTER TRIGGER ---
        order_ids_after          = [lvl.order_id for lvl in session.levels]
        prices_after             = [lvl.price for lvl in session.levels]
        qtys_after               = [lvl.qty for lvl in session.levels]
        anchor_price_after_check = service._trailing_configs[(symbol, "SHORT")].anchor_price

        print(f"\n=== SHORT AFTER TRAILING CHECK ===")
        print(f"result: {result}")
        print("levels:")
        for lvl in session.levels:
            print(f"  [{lvl.index}] order_id={lvl.order_id}  price={lvl.price}  qty={lvl.qty}  status={lvl.status}")
        print(f"order_ids_after:          {order_ids_after}")
        print(f"prices_after:             {prices_after}")
        print(f"qtys_after:               {qtys_after}")
        print(f"anchor_price_after_check: {anchor_price_after_check}")

        # --- CHECKS ---
        print(f"\n=== SHORT CHECKS ===")

        if result is not None:
            print(f"  PASS: check_trailing returned session")
        else:
            print(f"  FAIL: check_trailing returned None — trigger did not fire")
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

        if anchor_price_after_check != forced_anchor:
            print(f"  PASS: anchor_price updated  ({forced_anchor} -> {anchor_price_after_check})")
        else:
            print(f"  FAIL: anchor_price was not updated after trigger")
            sys.exit(1)

        if all(lvl.status == "placed" for lvl in session.levels):
            print(f"  PASS: all levels still placed")
        else:
            for lvl in session.levels:
                if lvl.status != "placed":
                    print(f"  FAIL: level [{lvl.index}] has status={lvl.status!r}")
            sys.exit(1)

        input("\nПроверь SHORT ордера на бирже ПОСЛЕ trigger и нажми Enter...")

        # --- SECOND CHECK (no trigger expected) ---
        result2 = service.check_trailing(symbol, "SHORT", price=current_price)
        if result2 is None:
            print(f"\n  PASS: second check_trailing returned None (no trigger without price movement)")
        else:
            print(f"\n  FAIL: expected None on second check, got session")
            sys.exit(1)

        # --- STOP SESSION ---
        stopped = service.stop_session(symbol, "SHORT")
        print(f"\n=== SHORT STOPPED ===")
        print(f"  status: {stopped.status}")
        for lvl in stopped.levels:
            print(f"  [{lvl.index}] status={lvl.status}  order_id={lvl.order_id}")

        # --- CHECK DISABLE TRAILING ---
        config_after_stop = service._trailing_configs.get((symbol, "SHORT"))
        if config_after_stop is None:
            print(f"\n  PASS: trailing config removed after stop_session")
        else:
            print(f"\n  FAIL: trailing config still present after stop_session")
            sys.exit(1)

    except Exception as e:
        print(f"\nSHORT ERROR: {e}")

    finally:
        remaining = service.get_session(symbol, "SHORT")
        if remaining is not None:
            print("\n=== SHORT FALLBACK CLEANUP ===")
            stopped = service.stop_session(symbol, "SHORT")
            print(f"  status: {stopped.status}")
            for lvl in stopped.levels:
                print(f"  [{lvl.index}] status={lvl.status}  order_id={lvl.order_id}")

    print("\nTEST DONE")
