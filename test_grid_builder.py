from trading_core.grid.grid_builder import GridBuilder

import sys

if __name__ == "__main__":

    builder = GridBuilder()

    # --- LONG ---
    long_session = builder.build_session(
        symbol="ANIMEUSDT",
        position_side="LONG",
        base_price=100,
        levels_count=3,
        step_percent=1,
        base_qty=1200,
    )

    print("=== LONG SESSION ===")
    print(f"session_id:     {long_session.session_id}")
    print(f"symbol:         {long_session.symbol}")
    print(f"position_side:  {long_session.position_side}")
    print("levels:")
    for lvl in long_session.levels:
        print(f"  [{lvl.index}] price={lvl.price}  qty={lvl.qty}  status={lvl.status}")

    print()

    # --- SHORT ---
    short_session = builder.build_session(
        symbol="ANIMEUSDT",
        position_side="SHORT",
        base_price=100,
        levels_count=3,
        step_percent=1,
        base_qty=1200,
    )

    print("=== SHORT SESSION ===")
    print(f"session_id:     {short_session.session_id}")
    print(f"symbol:         {short_session.symbol}")
    print(f"position_side:  {short_session.position_side}")
    print("levels:")
    for lvl in short_session.levels:
        print(f"  [{lvl.index}] price={lvl.price}  qty={lvl.qty}  status={lvl.status}")

    print()
    errors = []
    step_prices = []

    # -------------------------------------------------------
    # 1) step mode
    # -------------------------------------------------------
    print("=== TEST 1: step mode ===")
    s = builder.build_session(
        symbol="ANIMEUSDT",
        position_side="LONG",
        base_price=0.0045,
        levels_count=5,
        step_percent=1,
        base_qty=1000,
        orders_count=5,
        first_price=0.0045,
        last_price=0.0039,
        distribution_mode="step",
        distribution_value=1.0,
    )
    errors_before = len(errors)
    if len(s.levels) != 5:
        errors.append(f"TEST1: expected 5 levels, got {len(s.levels)}")
        print(f"  FAIL: expected 5 levels, got {len(s.levels)}")
    else:
        if abs(s.levels[0].price - 0.0045) >= 1e-12:
            errors.append(f"TEST1: first price expected 0.0045, got {s.levels[0].price}")
            print(f"  FAIL: first price expected 0.0045, got {s.levels[0].price}")
        if abs(s.levels[-1].price - 0.0039) >= 1e-12:
            errors.append(f"TEST1: last price expected 0.0039, got {s.levels[-1].price}")
            print(f"  FAIL: last price expected 0.0039, got {s.levels[-1].price}")
        step_prices = [lvl.price for lvl in s.levels]
        gaps = [round(step_prices[i] - step_prices[i + 1], 10) for i in range(len(step_prices) - 1)]
        for gi, g in enumerate(gaps):
            if abs(g - gaps[0]) >= 1e-9:
                errors.append(f"TEST1: gaps not equal at index {gi}: {gaps}")
                print(f"  FAIL: gaps not equal at index {gi}: {gaps}")
                break
        print(f"  prices: {step_prices}")
        print(f"  gaps:   {gaps}")
    if len(errors) == errors_before:
        print("  PASS")

    # -------------------------------------------------------
    # 2) density mode with distribution_value=1.0 matches step mode
    # -------------------------------------------------------
    print("=== TEST 2: density distribution_value=1.0 matches step ===")
    s2 = builder.build_session(
        symbol="ANIMEUSDT",
        position_side="LONG",
        base_price=0.0045,
        levels_count=5,
        step_percent=1,
        base_qty=1000,
        orders_count=5,
        first_price=0.0045,
        last_price=0.0039,
        distribution_mode="density",
        distribution_value=1.0,
    )
    errors_before = len(errors)
    if len(s2.levels) != 5:
        errors.append(f"TEST2: expected 5 levels, got {len(s2.levels)}")
        print(f"  FAIL: expected 5 levels, got {len(s2.levels)}")
    else:
        if len(step_prices) != 5:
            errors.append("TEST2: step_prices from TEST1 unavailable, cannot compare")
            print("  FAIL: step_prices from TEST1 unavailable, cannot compare")
        else:
            density_prices_1 = [lvl.price for lvl in s2.levels]
            for i, (p_step, p_density) in enumerate(zip(step_prices, density_prices_1)):
                if abs(p_step - p_density) >= 1e-10:
                    errors.append(f"TEST2: level {i+1} step={p_step} != density={p_density}")
                    print(f"  FAIL: level {i+1} step={p_step} != density={p_density}")
            print(f"  prices: {density_prices_1}")
    if len(errors) == errors_before:
        print("  PASS")

    # -------------------------------------------------------
    # 3) density distribution_value=2.0 — gaps smaller near last_price
    # -------------------------------------------------------
    print("=== TEST 3: density distribution_value=2.0 ===")
    s3 = builder.build_session(
        symbol="ANIMEUSDT",
        position_side="LONG",
        base_price=0.0045,
        levels_count=5,
        step_percent=1,
        base_qty=1000,
        orders_count=5,
        first_price=0.0045,
        last_price=0.0039,
        distribution_mode="density",
        distribution_value=2.0,
    )
    errors_before = len(errors)
    if len(s3.levels) != 5:
        errors.append(f"TEST3: expected 5 levels, got {len(s3.levels)}")
        print(f"  FAIL: expected 5 levels, got {len(s3.levels)}")
    else:
        prices3 = [lvl.price for lvl in s3.levels]
        gaps3 = [round(prices3[i] - prices3[i + 1], 10) for i in range(len(prices3) - 1)]
        if not (gaps3[0] > gaps3[-1]):
            errors.append(f"TEST3: expected first gap > last gap, got gaps={gaps3}")
            print(f"  FAIL: expected first gap > last gap, got gaps={gaps3}")
        print(f"  prices: {prices3}")
        print(f"  gaps:   {gaps3}")
    if len(errors) == errors_before:
        print("  PASS")

    # -------------------------------------------------------
    # 4) density distribution_value=0.5 — gaps smaller near first_price
    # -------------------------------------------------------
    print("=== TEST 4: density distribution_value=0.5 ===")
    s4 = builder.build_session(
        symbol="ANIMEUSDT",
        position_side="LONG",
        base_price=0.0045,
        levels_count=5,
        step_percent=1,
        base_qty=1000,
        orders_count=5,
        first_price=0.0045,
        last_price=0.0039,
        distribution_mode="density",
        distribution_value=0.5,
    )
    errors_before = len(errors)
    if len(s4.levels) != 5:
        errors.append(f"TEST4: expected 5 levels, got {len(s4.levels)}")
        print(f"  FAIL: expected 5 levels, got {len(s4.levels)}")
    else:
        prices4 = [lvl.price for lvl in s4.levels]
        gaps4 = [round(prices4[i] - prices4[i + 1], 10) for i in range(len(prices4) - 1)]
        if not (gaps4[0] < gaps4[-1]):
            errors.append(f"TEST4: expected first gap < last gap, got gaps={gaps4}")
            print(f"  FAIL: expected first gap < last gap, got gaps={gaps4}")
        print(f"  prices: {prices4}")
        print(f"  gaps:   {gaps4}")
    if len(errors) == errors_before:
        print("  PASS")

    # -------------------------------------------------------
    # 5) validation: _build_grid_prices raises ValueError
    # -------------------------------------------------------
    print("=== TEST 5: validation errors ===")

    validation_cases = [
        ("orders_count < 2",          dict(first_price=0.0045, last_price=0.0039, orders_count=1,    distribution_mode="step", distribution_value=1.0)),
        ("first_price <= 0",          dict(first_price=0.0,    last_price=0.0039, orders_count=5,    distribution_mode="step", distribution_value=1.0)),
        ("last_price <= 0",           dict(first_price=0.0045, last_price=0.0,    orders_count=5,    distribution_mode="step", distribution_value=1.0)),
        ("first_price == last_price", dict(first_price=0.0045, last_price=0.0045, orders_count=5,    distribution_mode="step", distribution_value=1.0)),
        ("distribution_value <= 0",   dict(first_price=0.0045, last_price=0.0039, orders_count=5,    distribution_mode="step", distribution_value=0.0)),
        ("unsupported mode",          dict(first_price=0.0045, last_price=0.0039, orders_count=5,    distribution_mode="bad",  distribution_value=1.0)),
    ]

    for label, kwargs in validation_cases:
        try:
            builder._build_grid_prices(**kwargs)
            errors.append(f"TEST5 [{label}]: expected ValueError, got no exception")
            print(f"  [{label}] FAIL — no exception raised")
        except ValueError as e:
            print(f"  [{label}] PASS — ValueError: {e}")
        except Exception as e:
            errors.append(f"TEST5 [{label}]: unexpected exception {type(e).__name__}: {e}")
            print(f"  [{label}] FAIL — {type(e).__name__}: {e}")

    print()
    if errors:
        print("=== FAILURES ===")
        for err in errors:
            print(f"  {err}")
        sys.exit(1)
    else:
        print("=== ALL TESTS PASSED ===")
