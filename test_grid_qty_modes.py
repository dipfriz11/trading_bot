from trading_core.grid.grid_builder import GridBuilder

if __name__ == "__main__":

    builder = GridBuilder()

    # --- FIXED ---
    session = builder.build_session(
        symbol="BTCUSDT",
        position_side="LONG",
        base_price=100.0,
        levels_count=3,
        step_percent=1.0,
        base_qty=10.0,
        qty_mode="fixed",
    )
    qtys = [lvl.qty for lvl in session.levels]
    print(f"FIXED qty: {qtys}")
    assert qtys == [10.0, 10.0, 10.0], f"Unexpected: {qtys}"
    print("FIXED OK")

    # --- MULTIPLIER ---
    session = builder.build_session(
        symbol="BTCUSDT",
        position_side="LONG",
        base_price=100.0,
        levels_count=3,
        step_percent=1.0,
        base_qty=10.0,
        qty_mode="multiplier",
        qty_multiplier=2.0,
    )
    qtys = [lvl.qty for lvl in session.levels]
    print(f"MULTIPLIER qty: {qtys}")
    assert qtys == [10.0, 20.0, 40.0], f"Unexpected: {qtys}"
    print("MULTIPLIER OK")

    # --- INVALID MODE ---
    try:
        builder.build_session(
            symbol="BTCUSDT",
            position_side="LONG",
            base_price=100.0,
            levels_count=3,
            step_percent=1.0,
            base_qty=10.0,
            qty_mode="wrong_mode",
        )
        print("INVALID MODE: ERROR — ValueError was not raised")
    except ValueError as e:
        print(f"INVALID MODE caught: {e}")
        print("INVALID MODE OK")
