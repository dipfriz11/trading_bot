from trading_core.grid.grid_builder import GridBuilder

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
