import threading
import time
from typing import Dict, Optional, Tuple


class GridTrailingWatcher:

    def __init__(self, grid_service, market_data, cooldown_sec: float = 5.0):
        self._grid_service = grid_service
        self._market_data = market_data
        self._cooldown_sec = cooldown_sec

        self._watched: Dict[Tuple[str, str], bool] = {}           # (symbol, position_side) → True
        self._last_modified_at: Dict[Tuple[str, str], float] = {}
        self._in_flight: Dict[Tuple[str, str], bool] = {}
        self._lock = threading.Lock()
        self._last_known_qty: Dict[Tuple[str, str], float] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_watching(self, symbol: str, position_side: str) -> None:
        key = (symbol, position_side)
        listener_id = f"grid_trailing_{symbol}_{position_side}"
        with self._lock:
            already_watched = key in self._watched
            self._watched[key] = True
            self._last_modified_at.setdefault(key, 0.0)
            self._in_flight.setdefault(key, False)
        if not already_watched:
            self._market_data.subscribe(symbol)
            self._market_data.add_price_listener(symbol, listener_id, self._on_price_update)

    def stop_watching(self, symbol: str, position_side: str) -> None:
        key = (symbol, position_side)
        listener_id = f"grid_trailing_{symbol}_{position_side}"
        self._market_data.remove_price_listener(symbol, listener_id)
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            with self._lock:
                if not self._in_flight.get(key, False):
                    break
            time.sleep(0.05)
        self._market_data.unsubscribe(symbol)
        with self._lock:
            self._watched.pop(key, None)
            self._last_modified_at.pop(key, None)
            self._in_flight.pop(key, None)
            self._last_known_qty.pop(key, None)

    def stop_all(self) -> None:
        for symbol, position_side in list(self._watched.keys()):
            self.stop_watching(symbol, position_side)

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _reconcile_tail(self, symbol: str, position_side: str, pos_qty: float) -> None:
        if self._grid_service._reset_tp_order.get((symbol, position_side)):
            print(f"[TailReconcile] {symbol}/{position_side}  skipped due to active reset TP")
            return
        if pos_qty <= 0:
            return
        cfg = self._grid_service._grid_build_config.get((symbol, position_side))
        if not cfg:
            return
        slot_qtys    = cfg.get("slot_qtys", [])
        orders_count = cfg.get("orders_count", 0)
        if not slot_qtys or not orders_count:
            return
        _rem, lvl_in_pos = pos_qty, 0
        for sq in slot_qtys:
            if _rem >= sq * 0.5:
                _rem -= sq
                lvl_in_pos += 1
            else:
                break
        if lvl_in_pos >= orders_count:
            return
        expected = set(range(lvl_in_pos + 1, orders_count + 1))
        session = self._grid_service.get_session(symbol, position_side)
        if not session:
            return
        actual = {
            (l.slot_index if l.slot_index is not None else l.index)
            for l in session.levels if l.status == "placed"
        }
        missing = expected - actual
        orphans = actual - expected
        if not missing:
            return
        if orphans:
            print(f"[TailReconcile] {symbol}/{position_side}  orphan_slots={sorted(orphans)}  missing={sorted(missing)}  → skip (position lag)")
            return
        target = sorted(missing, reverse=True)
        print(f"[TailReconcile] {symbol}/{position_side}  pos_qty={pos_qty:.4f}  lvl_in_pos={lvl_in_pos}  missing_slots={target}  → rebuilding")
        self._grid_service.rebuild_pending_tail(symbol, position_side, target_slots=target)

    def _on_price_update(self, symbol: str, price: float) -> None:
        with self._lock:
            legs = [(s, ps) for (s, ps) in self._watched if s == symbol]
        for key in legs:
            _, position_side = key
            with self._lock:
                if key not in self._watched:
                    continue
                if self._in_flight.get(key, False):
                    continue
                elapsed = time.monotonic() - self._last_modified_at.get(key, 0.0)
                if elapsed < self._cooldown_sec:
                    continue
                self._in_flight[key] = True
            thread = threading.Thread(
                target=self._do_check,
                args=(symbol, price, position_side),
                daemon=True,
            )
            thread.start()

    def _do_check(self, symbol: str, price: float, position_side: str) -> None:
        key = (symbol, position_side)
        _qty_before_tick = self._last_known_qty.get(key)
        try:
            with self._lock:
                if key not in self._watched:
                    return

            # ── tick-start snapshot ──────────────────────────────────────
            session_snap = self._grid_service.get_session(symbol, position_side)
            if session_snap:
                by_status = {}
                for l in session_snap.levels:
                    by_status.setdefault(l.status, []).append(l.index)
                print(
                    f"[GRID-FILL] {symbol}/{position_side}  tick start"
                    f"  price={price:.8f}"
                    f"  levels={dict(by_status)}"
                )
            # ─────────────────────────────────────────────────────────────

            hit = self._grid_service.check_tpsl(symbol, position_side, price)
            if hit is not None:
                self._last_known_qty.pop(key, None)
                return

            print(f"[GRID-FILL] {symbol}/{position_side}  → calling check_reset_tp_fill")
            _joint_levels_this_tick = []
            _skip_tail_reconcile = False
            reset_filled = self._grid_service.check_reset_tp_fill(symbol, position_side)
            print(f"[GRID-FILL] {symbol}/{position_side}  check_reset_tp_fill returned: {reset_filled and reset_filled['order_id']}")
            if reset_filled:
                print(
                    f"[ResetTP] {symbol}/{position_side}"
                    f"  Reset TP fill detected  order_id={reset_filled['order_id']}"
                    f"  price={reset_filled['price']:.8f}"
                    f"  qty={reset_filled['qty']}"
                )
                detection_mode = reset_filled.get("detection_mode", "unknown")
                joint_levels   = reset_filled.get("joint_levels", [])
                _joint_levels_this_tick = joint_levels
                print(
                    f"[GRID-FILL] {symbol}/{position_side}"
                    f"  detection_mode={detection_mode}"
                    f"  joint_levels={[l.index for l in joint_levels]}"
                )
                if joint_levels:
                    for jlvl in joint_levels:
                        jlvl.status = "filled"
                        print(
                            f"[GRID-FILL] {symbol}/{position_side}"
                            f"  joint level[{jlvl.index}] marked filled"
                            f"  (will be skipped by check_grid_fills)"
                        )

                session = self._grid_service.get_session(symbol, position_side)
                pending = [l for l in (session.levels if session else []) if l.status == "placed"]
                print(
                    f"[Rebuild] {symbol}/{position_side}"
                    f"  called  pending_count={len(pending)}"
                    f"  pending_indices={[l.index for l in pending]}"
                )
                # ── reset decrease policy ────────────────────────────────
                _pos_at_placement  = reset_filled.get("position_qty_at_placement", 0.0)
                _reset_tp_qty      = reset_filled["qty"]
                _curr_qty_rt       = 0.0
                for _p in self._grid_service.exchange.get_positions(symbol):
                    if _p["positionSide"] == position_side:
                        _curr_qty_rt = abs(float(_p["positionAmt"]))
                        break
                _actual_decrease   = max(0.0, _pos_at_placement - _curr_qty_rt)
                _planned_remainder = _pos_at_placement - _reset_tp_qty
                _tolerance         = _reset_tp_qty * 0.1
                _is_pure_reset     = abs(_curr_qty_rt - _planned_remainder) <= _tolerance
                print(
                    f"[ResetDecrease] {symbol}/{position_side}"
                    f"  actual_decrease={_actual_decrease:.4f}"
                    f"  reset_tp_qty={_reset_tp_qty:.4f}"
                    f"  planned_remainder={_planned_remainder:.4f}"
                    f"  curr_qty={_curr_qty_rt:.4f}"
                    f"  is_pure_reset={_is_pure_reset}"
                )

                if _is_pure_reset:
                    # Pure reset TP: main TP already correct (set by place_reset_tp_complex)
                    print(f"[ResetDecrease] {symbol}/{position_side}  pure reset → rebuild only, main TP untouched")
                    _rtp_count = reset_filled.get("target_rebuild_count")
                    _pr_cfg = self._grid_service._grid_build_config.get((symbol, position_side), {})
                    _pr_sq  = _pr_cfg.get("slot_qtys", [])
                    _pr_oc  = _pr_cfg.get("orders_count", 0)
                    _pr_target = None
                    if _pr_sq and _pr_oc:
                        _pending_slots = sorted({
                            (l.slot_index if l.slot_index is not None else l.index)
                            for l in pending
                            if 1 <= (l.slot_index if l.slot_index is not None else l.index) <= _pr_oc
                        }, reverse=True)
                        _released_rem = reset_filled.get("qty", 0.0)
                        _freed_slots = []
                        for _slot_idx in range(_pr_oc, 0, -1):
                            if _slot_idx in _pending_slots:
                                continue
                            _slot_qty = _pr_sq[_slot_idx - 1]
                            if _released_rem >= _slot_qty * 0.9:
                                _released_rem -= _slot_qty
                                _freed_slots.append(_slot_idx)
                            else:
                                break
                        _pr_target = sorted(set(_pending_slots + _freed_slots), reverse=True)
                        print(f"[ResetDecrease] {symbol}/{position_side}  target_slots={_pr_target}  pending_slots={_pending_slots}  freed_slots={_freed_slots}  released_qty={reset_filled.get('qty', 0.0)}")
                    rebuilt = self._grid_service.rebuild_pending_tail(symbol, position_side, target_slots=_pr_target)
                else:
                    # Reset TP + extra manual close: reprice main TP and SL for new position
                    print(f"[ResetDecrease] {symbol}/{position_side}  extra decrease → reprice main TP + SL + rebuild")
                    _mode = self._grid_service._tp_update_mode.get((symbol, position_side), "fixed")
                    if _mode == "reprice":
                        self._grid_service.update_grid_tp_orders_reprice(symbol, position_side)
                    else:
                        self._grid_service.update_grid_tp_orders_fixed(symbol, position_side)
                    self._grid_service.update_sl_after_averaging(symbol, position_side)
                    _cfg = self._grid_service._grid_build_config.get((symbol, position_side), {})
                    _slot_qtys = _cfg.get("slot_qtys", [])
                    _orders_count = _cfg.get("orders_count", 0)
                    _target = None
                    if _slot_qtys and _orders_count:
                        _rem = _curr_qty_rt
                        _lvl_in_pos = 0
                        for _sq in _slot_qtys:
                            if _rem >= _sq * 0.5:
                                _rem -= _sq
                                _lvl_in_pos += 1
                            else:
                                break
                        if _orders_count > _lvl_in_pos:
                            _target = list(range(_orders_count, _lvl_in_pos, -1))
                    rebuilt = self._grid_service.rebuild_pending_tail(symbol, position_side, target_slots=_target)
                    # NOTE: new reset TP for reduced position not placed here — separate step
                # ────────────────────────────────────────────────────────

                print(f"[GRID-FILL] {symbol}/{position_side}  rebuild_pending_tail returned: {len(rebuilt) if rebuilt else 0} new levels")
                if rebuilt:
                    print(
                        f"[RebuildTail] {symbol}/{position_side}"
                        f"  tail rebuilt: {len(rebuilt)} new levels"
                    )
                else:
                    print(f"[RebuildTail] {symbol}/{position_side}  rebuild skipped")

            filled_tps = self._grid_service.check_tp_fills(symbol, position_side)
            if filled_tps:
                for tp in filled_tps:
                    print(
                        f"[GridTP] {symbol}/{position_side}"
                        f"  TP filled: order_id={tp['order_id']}"
                        f"  tp_percent={tp['tp_percent']}%"
                        f"  price={tp['price']:.8f}"
                        f"  qty={tp['qty']}"
                    )

            print(f"[GRID-FILL] {symbol}/{position_side}  → calling check_grid_fills")
            filled = self._grid_service.check_grid_fills(symbol, position_side)
            print(f"[GRID-FILL] {symbol}/{position_side}  check_grid_fills returned: filled_levels={[l.index for l in filled]}")
            if filled:
                for lvl in filled:
                    print(
                        f"[GridFills] {symbol}/{position_side}"
                        f"  level[{lvl.index}] filled"
                        f"  price={lvl.price}"
                    )
                print(
                    f"[FillDbg] {symbol}/{position_side}"
                    f"  batch=[{', '.join(f'lvl{l.index}/rtp={l.use_reset_tp}' for l in filled)}]"
                    f"  order_ids={[l.order_id for l in filled]}"
                )
                reset_trigger = next(
                    (lvl for lvl in reversed(filled + _joint_levels_this_tick) if lvl.use_reset_tp), None
                )
                print(
                    f"[FillDbg] {symbol}/{position_side}"
                    f"  reset_trigger={'lvl'+str(reset_trigger.index) if reset_trigger else None}"
                    f"  reset_tp_percent={reset_trigger.reset_tp_percent if reset_trigger else '—'}"
                )
                if reset_trigger is not None:
                    print(f"[GRID-FILL] {symbol}/{position_side}  PATH=reset_tp  → calling place_reset_tp_complex level[{reset_trigger.index}]")
                    self._grid_service.place_reset_tp_complex(symbol, position_side, reset_trigger)
                    print(f"[GRID-FILL] {symbol}/{position_side}  place_reset_tp_complex done")
                else:
                    mode = self._grid_service._tp_update_mode.get((symbol, position_side), "fixed")
                    print(f"[GRID-FILL] {symbol}/{position_side}  PATH=reprice  mode={mode}  → calling update_grid_tp_orders_{mode}")
                    if mode == "reprice":
                        updated = self._grid_service.update_grid_tp_orders_reprice(symbol, position_side)
                    else:
                        updated = self._grid_service.update_grid_tp_orders_fixed(symbol, position_side)
                    print(f"[GRID-FILL] {symbol}/{position_side}  update_grid_tp_orders_{mode} returned: {'None(skip)' if updated is None else str(len(updated))+' order(s)'}")
                    if updated is not None:
                        print(
                            f"[GridTP] {symbol}/{position_side}"
                            f"  TP orders updated after averaging fill ({mode}): {len(updated)} orders"
                        )
                self._grid_service.update_sl_after_averaging(symbol, position_side)

            # ── manual partial close detection ──────────────────────────
            # Tracked decrease events (reset TP / TP fills): clear tracking;
            # next tick re-initializes cleanly. No REST needed.
            # Quiet tick: poll position once, compare with last known.
            has_pending_reset_tp = bool(
                self._grid_service._reset_tp_order.get((symbol, position_side))
            )
            if filled_tps:
                self._last_known_qty.pop(key, None)
            elif has_pending_reset_tp:
                # Reset TP active but didn't fill this tick. Check for manual partial
                # close: position decreased but not enough for reset TP fill → stale.
                _srtp = self._grid_service._reset_tp_order.get((symbol, position_side))
                _srtp_pos_at_pl = _srtp.get("position_qty_at_placement", 0.0) if _srtp else 0.0
                if _srtp and _srtp_pos_at_pl > 0:
                    _srtp_curr = 0.0
                    for _p in self._grid_service.exchange.get_positions(symbol):
                        if _p["positionSide"] == position_side:
                            _srtp_curr = abs(float(_p["positionAmt"]))
                            break
                    _srtp_floor = _srtp_pos_at_pl - _srtp["qty"] * 0.9
                    if _srtp_curr < _srtp_pos_at_pl * 0.99 and _srtp_curr > _srtp_floor:
                        # Partial close while reset TP active: cancel stale reset TP + reconcile.
                        print(f"[StaleResetTP] {symbol}/{position_side}  manual partial close with active reset TP  pos_at_placement={_srtp_pos_at_pl}  current={_srtp_curr:.4f}  floor={_srtp_floor:.4f}  → cancel + reconcile")
                        try:
                            self._grid_service.exchange.cancel_order(symbol, _srtp["order_id"])
                            print(f"[StaleResetTP] {symbol}/{position_side}  cancelled reset TP order_id={_srtp['order_id']}")
                        except Exception as _ex:
                            print(f"[StaleResetTP] {symbol}/{position_side}  cancel error (ignored): {_ex}")
                        self._grid_service._reset_tp_order.pop((symbol, position_side), None)
                        _src_cfg = self._grid_service._grid_build_config.get((symbol, position_side), {})
                        _src_slot_qtys = _src_cfg.get("slot_qtys", [])
                        _src_orders_count = _src_cfg.get("orders_count", 0)
                        _src_target = None
                        if _src_slot_qtys and _src_orders_count:
                            _src_rem = _srtp_curr
                            _src_lvl_in_pos = 0
                            for _src_sq in _src_slot_qtys:
                                if _src_rem >= _src_sq * 0.5:
                                    _src_rem -= _src_sq
                                    _src_lvl_in_pos += 1
                                else:
                                    break
                            if _src_orders_count > _src_lvl_in_pos:
                                _src_target = list(range(_src_orders_count, _src_lvl_in_pos, -1))
                        self._grid_service.rebuild_pending_tail(symbol, position_side, target_slots=_src_target)
                        _mode = self._grid_service._tp_update_mode.get((symbol, position_side), "fixed")
                        if _mode == "reprice":
                            self._grid_service.update_grid_tp_orders_reprice(symbol, position_side)
                        else:
                            self._grid_service.update_grid_tp_orders_fixed(symbol, position_side)
                        self._grid_service.update_sl_after_averaging(symbol, position_side)
                        self._last_known_qty[key] = _srtp_curr
                    elif _srtp_curr > _srtp_pos_at_pl * 1.01:
                        # Position grew while reset TP active: old reset TP is stale for the deeper position.
                        print(f"[StaleResetTP] {symbol}/{position_side}  position grew while reset TP active  pos_at_placement={_srtp_pos_at_pl}  current={_srtp_curr:.4f}  → cancel + re-reconcile")
                        try:
                            self._grid_service.exchange.cancel_order(symbol, _srtp["order_id"])
                            print(f"[StaleResetTP] {symbol}/{position_side}  cancelled stale reset TP order_id={_srtp['order_id']}")
                        except Exception as _ex:
                            print(f"[StaleResetTP] {symbol}/{position_side}  cancel error (ignored): {_ex}")
                        self._grid_service._reset_tp_order.pop((symbol, position_side), None)
                        _sgr_cfg = self._grid_service._grid_build_config.get((symbol, position_side), {})
                        _sgr_slot_qtys = _sgr_cfg.get("slot_qtys", [])
                        _sgr_lvl_in_pos = 0
                        _sgr_rem = _srtp_curr
                        for _sgr_sq in _sgr_slot_qtys:
                            if _sgr_rem >= _sgr_sq * 0.5:
                                _sgr_rem -= _sgr_sq; _sgr_lvl_in_pos += 1
                            else:
                                break
                        if _sgr_lvl_in_pos > 0:
                            _sgr_sess = self._grid_service.get_session(symbol, position_side)
                            _sgr_candidate = next(
                                (l for l in sorted(
                                    (_sgr_sess.levels if _sgr_sess else []),
                                    key=lambda x: (x.slot_index if x.slot_index is not None else x.index),
                                    reverse=True
                                ) if l.use_reset_tp
                                   and (l.slot_index if l.slot_index is not None else l.index) <= _sgr_lvl_in_pos),
                                None
                            )
                            if _sgr_candidate:
                                print(f"[StaleResetTP] {symbol}/{position_side}  re-place reset TP → level[{_sgr_candidate.index}]  covered_slots={_sgr_lvl_in_pos}")
                                self._grid_service.place_reset_tp_complex(symbol, position_side, _sgr_candidate)
                                _sgr_entry = self._grid_service._reset_tp_order.get((symbol, position_side))
                                if _sgr_entry and _sgr_lvl_in_pos > _sgr_entry.get("trigger_slot", 0):
                                    _sgr_entry["trigger_slot"] = _sgr_lvl_in_pos
                                    print(f"[StaleResetTP] {symbol}/{position_side}  trigger_slot overridden → {_sgr_lvl_in_pos}")
                        self._grid_service.update_sl_after_averaging(symbol, position_side)
                        self._last_known_qty[key] = _srtp_curr
                    else:
                        self._last_known_qty.pop(key, None)
                else:
                    self._last_known_qty.pop(key, None)
            elif reset_filled:
                if _is_pure_reset:
                    self._last_known_qty[key] = _curr_qty_rt
                else:
                    # extra decrease: actual qty already fetched in reset_filled block above
                    self._last_known_qty[key] = _curr_qty_rt
            elif filled:
                # Grid fill already explained the position change this tick;
                # just sync last_known_qty so ManualAdd/ManualClose don't fire.
                _pos_qty = 0.0
                for _pos in self._grid_service.exchange.get_positions(symbol):
                    if _pos["positionSide"] == position_side:
                        _pos_qty = abs(float(_pos["positionAmt"]))
                        break
                self._last_known_qty[key] = _pos_qty
            else:
                _pos_qty = 0.0
                for _pos in self._grid_service.exchange.get_positions(symbol):
                    if _pos["positionSide"] == position_side:
                        _pos_qty = abs(float(_pos["positionAmt"]))
                        break
                _last_qty = self._last_known_qty.get(key)
                if _last_qty is not None and _pos_qty < _last_qty * 0.99:
                    print(
                        f"[ManualClose] {symbol}/{position_side}"
                        f"  unexplained position decrease"
                        f"  last={_last_qty}  current={_pos_qty}"
                    )
                    _mc_cfg = self._grid_service._grid_build_config.get((symbol, position_side), {})
                    _mc_slot_qtys = _mc_cfg.get("slot_qtys", [])
                    _mc_orders_count = _mc_cfg.get("orders_count", 0)
                    _mc_target = None
                    if _mc_slot_qtys and _mc_orders_count:
                        _mc_rem = _pos_qty
                        _mc_lvl_in_pos = 0
                        for _mc_sq in _mc_slot_qtys:
                            if _mc_rem >= _mc_sq * 0.5:
                                _mc_rem -= _mc_sq
                                _mc_lvl_in_pos += 1
                            else:
                                break
                        if _mc_orders_count > _mc_lvl_in_pos:
                            _mc_target = list(range(_mc_orders_count, _mc_lvl_in_pos, -1))
                    self._grid_service.rebuild_pending_tail(symbol, position_side, target_slots=_mc_target)
                    _mode = self._grid_service._tp_update_mode.get((symbol, position_side), "fixed")
                    if _mode == "reprice":
                        self._grid_service.update_grid_tp_orders_reprice(symbol, position_side)
                    else:
                        self._grid_service.update_grid_tp_orders_fixed(symbol, position_side)
                    self._grid_service.update_sl_after_averaging(symbol, position_side)
                elif _last_qty is not None and _pos_qty > _last_qty * 1.01:
                    # Fix A: guard against delayed position arrival after cleanup cancel.
                    # If last_qty==0 and session already has filled levels, the position
                    # increase was already explained by a prior grid fill tick — skip reconcile.
                    _sess_snap = self._grid_service.get_session(symbol, position_side)
                    _filled_in_sess = sum(
                        1 for l in (_sess_snap.levels if _sess_snap else [])
                        if l.status == "filled"
                    )
                    if _last_qty == 0 and _filled_in_sess > 0:
                        pass  # delayed position arrival — sync only, no reconcile
                    else:
                        # Guard: if position delta matches a placed level qty,
                        # this is likely an API-lag fill not yet detected by check_grid_fills.
                        # Skip ManualAdd reconcile — next tick will detect it properly.
                        _delta = _pos_qty - _last_qty
                        _placed_qtys = [
                            l.qty for l in (_sess_snap.levels if _sess_snap else [])
                            if l.status == "placed"
                        ]
                        _matches_fill = bool(_placed_qtys) and any(
                            abs(q - _delta) / max(_delta, 1e-9) < 0.15
                            for q in _placed_qtys
                        )
                        if _matches_fill:
                            _skip_tail_reconcile = True
                            print(f"[ManualAdd] {symbol}/{position_side}  skipped: delta={_delta:.4f} matches placed level qty  → likely API-lag fill, next tick will detect")
                            _mf_cfg = self._grid_service._grid_build_config.get((symbol, position_side), {})
                            _mf_slot_qtys = _mf_cfg.get("slot_qtys", [])
                            _mf_lvl_in_pos = 0
                            _mf_rem = _pos_qty
                            for _mf_sq in _mf_slot_qtys:
                                if _mf_rem >= _mf_sq * 0.5:
                                    _mf_rem -= _mf_sq
                                    _mf_lvl_in_pos += 1
                                else:
                                    break
                            _mf_restored = None
                            for _mf_gc in sorted(
                                [l for l in (_sess_snap.levels if _sess_snap else [])
                                 if l.status == "canceled" and l.qty > 0],
                                key=lambda l: (l.slot_index if l.slot_index is not None else l.index),
                            ):
                                _gc_slot = _mf_gc.slot_index if _mf_gc.slot_index is not None else _mf_gc.index
                                if (
                                    _gc_slot <= _mf_lvl_in_pos
                                    and abs(_mf_gc.qty - _delta) / max(_delta, 1e-9) < 0.15
                                ):
                                    _mf_gc.status = "filled"
                                    _mf_restored = _mf_gc
                                    print(f"[ManualAdd] {symbol}/{position_side}  ghost-canceled level[{_mf_gc.index}] restored to filled  qty={_mf_gc.qty:.4f}  delta={_delta:.4f}")
                                    break
                            if _mf_restored and _mf_restored.use_reset_tp:
                                print(f"[ManualAdd] {symbol}/{position_side}  ghost-canceled reset TP reconcile → level[{_mf_restored.index}]")
                                self._grid_service.place_reset_tp_complex(symbol, position_side, _mf_restored)
                            elif _mf_restored:
                                _mf_mode = self._grid_service._tp_update_mode.get((symbol, position_side), "fixed")
                                print(f"[ManualAdd] {symbol}/{position_side}  ghost-canceled non-reset fill reconcile  mode={_mf_mode}")
                                if _mf_mode == "reprice":
                                    self._grid_service.update_grid_tp_orders_reprice(symbol, position_side)
                                else:
                                    self._grid_service.update_grid_tp_orders_fixed(symbol, position_side)
                                self._grid_service.update_sl_after_averaging(symbol, position_side)
                        else:
                            print(
                                f"[ManualAdd] {symbol}/{position_side}"
                                f"  unexplained position increase"
                                f"  last={_last_qty}  current={_pos_qty}"
                            )
                            _ma_cfg = self._grid_service._grid_build_config.get((symbol, position_side), {})
                            _ma_slot_qtys = _ma_cfg.get("slot_qtys", [])
                            _ma_orders_count = _ma_cfg.get("orders_count", 0)
                            _ma_target = None
                            _ma_lvl_in_pos = 0
                            if _ma_slot_qtys and _ma_orders_count:
                                _ma_rem = _pos_qty
                                for _ma_sq in _ma_slot_qtys:
                                    if _ma_rem >= _ma_sq * 0.5:
                                        _ma_rem -= _ma_sq
                                        _ma_lvl_in_pos += 1
                                    else:
                                        break
                                if _ma_orders_count > _ma_lvl_in_pos:
                                    _ma_target = list(range(_ma_orders_count, _ma_lvl_in_pos, -1))
                            self._grid_service.rebuild_pending_tail(symbol, position_side, target_slots=_ma_target)
                            _mode = self._grid_service._tp_update_mode.get((symbol, position_side), "fixed")
                            if _mode == "reprice":
                                self._grid_service.update_grid_tp_orders_reprice(symbol, position_side)
                            else:
                                self._grid_service.update_grid_tp_orders_fixed(symbol, position_side)
                            self._grid_service.update_sl_after_averaging(symbol, position_side)
                            # Fix B: reconcile reset TP — find highest slot covered by position
                            # that has use_reset_tp=True. Uses position-based slot count
                            # (_ma_lvl_in_pos, same 0.5 threshold), not status=="filled",
                            # because position grew outside normal grid fill path.
                            _rtp_existing = self._grid_service._reset_tp_order.get((symbol, position_side))
                            if not _rtp_existing and _ma_lvl_in_pos > 0:
                                _ma_sess = self._grid_service.get_session(symbol, position_side)
                                _ma_rtp_candidate = next(
                                    (l for l in sorted(
                                        (_ma_sess.levels if _ma_sess else []),
                                        key=lambda x: (x.slot_index if x.slot_index is not None else x.index),
                                        reverse=True
                                    ) if l.use_reset_tp
                                       and (l.slot_index if l.slot_index is not None else l.index) <= _ma_lvl_in_pos),
                                    None
                                )
                                if _ma_rtp_candidate:
                                    print(
                                        f"[ManualAdd] {symbol}/{position_side}"
                                        f"  reconcile reset TP → level[{_ma_rtp_candidate.index}]"
                                        f"  slot={_ma_rtp_candidate.slot_index}  covered_slots={_ma_lvl_in_pos}"
                                    )
                                    self._grid_service.place_reset_tp_complex(symbol, position_side, _ma_rtp_candidate)
                elif _last_qty is None and _pos_qty > 0:
                    # First observation with non-zero position and uninitialized tracking.
                    # Race condition: cleanup cancel fired (qty=0 at check_grid_fills time)
                    # but position arrived in the same tick's REST poll — ManualAdd never
                    # fires because _last_qty is not None condition was never met.
                    # If TP or SL are missing, reconcile now.
                    _no_tp = not bool(self._grid_service._grid_tp_orders.get((symbol, position_side)))
                    _no_sl = not bool(self._grid_service._sl_orders.get((symbol, position_side)))
                    if _no_tp or _no_sl:
                        print(
                            f"[InitReconcile] {symbol}/{position_side}"
                            f"  first pos observation  pos={_pos_qty}  no_tp={_no_tp}  no_sl={_no_sl}"
                            f"  → reconcile TP/SL"
                        )
                        _mode = self._grid_service._tp_update_mode.get((symbol, position_side), "fixed")
                        if _mode == "reprice":
                            self._grid_service.update_grid_tp_orders_reprice(symbol, position_side)
                        else:
                            self._grid_service.update_grid_tp_orders_fixed(symbol, position_side)
                        self._grid_service.update_sl_after_averaging(symbol, position_side)
                self._last_known_qty[key] = _pos_qty

                # ── auto-stop: position zero, no active orders ───────────
                if _pos_qty == 0:
                    _sess      = self._grid_service.get_session(symbol, position_side)
                    _no_rtp    = not self._grid_service._reset_tp_order.get((symbol, position_side))
                    _no_placed = not (_sess and any(l.status == "placed" for l in _sess.levels))
                    if _no_rtp and _no_placed:
                        print(f"[GridCycle] {symbol}/{position_side}  position=0 no active orders → auto-stop")
                        for _tp in self._grid_service._grid_tp_orders.pop((symbol, position_side), []):
                            try:
                                self._grid_service.exchange.cancel_order(symbol, _tp["order_id"])
                                print(f"[GridCycle] {symbol}/{position_side}  cancelled main TP  order_id={_tp['order_id']}")
                            except Exception as _ex:
                                print(f"[GridCycle] {symbol}/{position_side}  cancel TP error (ignored): {_ex}")
                        _lid = f"grid_trailing_{symbol}_{position_side}"
                        self._market_data.remove_price_listener(symbol, _lid)
                        self._market_data.unsubscribe(symbol)
                        with self._lock:
                            self._watched.pop(key, None)
                            self._last_modified_at.pop(key, None)
                            self._last_known_qty.pop(key, None)
                        if _sess:
                            _sess.status = "stopped"
                            self._grid_service.registry.save_session(_sess)
                        return
                # ─────────────────────────────────────────────────────────
            # ────────────────────────────────────────────────────────────

            # ── position-change-triggered tail reconcile ──────────────
            _rc_qty = 0.0
            for _p in self._grid_service.exchange.get_positions(symbol):
                if _p["positionSide"] == position_side:
                    _rc_qty = abs(float(_p["positionAmt"]))
                    break
            if not reset_filled and not _skip_tail_reconcile and abs((_qty_before_tick or 0) - _rc_qty) > 1e-9:
                self._reconcile_tail(symbol, position_side, _rc_qty)
            # ──────────────────────────────────────────────────────────

            _sess_for_trail = self._grid_service.get_session(symbol, position_side)
            _in_position = _sess_for_trail and any(
                l.status == "filled" for l in _sess_for_trail.levels
            )
            if not _in_position:
                result = self._grid_service.check_trailing(symbol, position_side, price)
                if result is not None:
                    with self._lock:
                        if key in self._last_modified_at:
                            self._last_modified_at[key] = time.monotonic()
        except Exception as e:
            print(f"[GridTrailingWatcher] check error ({symbol}/{position_side}): {e}")
        finally:
            with self._lock:
                if key in self._in_flight:
                    self._in_flight[key] = False
