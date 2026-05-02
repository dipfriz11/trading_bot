import { supabase } from "./supabase"
import type { LivePosition, ChartPlacedOrder } from "../types/terminal"

// Session ID — anonymous identifier persisted in localStorage
function getSessionId(): string {
  const key = "terminal_session_id"
  let id = localStorage.getItem(key)
  if (!id) {
    id = crypto.randomUUID()
    localStorage.setItem(key, id)
  }
  return id
}

export const SESSION_ID = getSessionId()

// ── DB row shapes ─────────────────────────────────────────────────────────────

interface PositionRow {
  id: string
  session_id: string
  account_id: string
  exchange_id: string
  market_type: string
  symbol: string
  side: string
  size: number
  real_size: number
  avg_entry: number
  leverage: number
  margin_mode: string
  mark_price: number
  unrealized_pnl: number
  unrealized_pnl_pct: number
  notional: number
  opened_at: string
  opened_date: string
  short_id: string
  status: string
  realized_pnl: number
  source_console_id: string | null
  pos_key: string
  tp_pct: number | null
  sl_pct: number | null
  tp_price: number | null
  sl_price: number | null
}

interface OrderRow {
  id: string
  session_id: string
  position_id: string
  side: string
  price: number
  qty: number
  order_type: string
  symbol: string | null
  account_id: string | null
  exchange_id: string | null
  market_type: string | null
  leverage: number | null
  margin: number | null
  time: string | null
  filled_at: string | null
  filled_pct: number | null
  status: string
  source: string
  grid_index: number | null
  grid_console_id: string | null
  bot_name: string | null
  webhook_name: string | null
}

// ── Converters ────────────────────────────────────────────────────────────────

function positionToRow(pk: string, pos: LivePosition): Omit<PositionRow, "id"> {
  return {
    session_id: SESSION_ID,
    account_id: pos.accountId,
    exchange_id: pos.exchangeId,
    market_type: pos.marketType,
    symbol: pos.symbol,
    side: pos.side,
    size: pos.size,
    real_size: pos.realSize ?? 0,
    avg_entry: pos.avgEntry,
    leverage: pos.leverage,
    margin_mode: pos.marginMode ?? "cross",
    mark_price: pos.markPrice,
    unrealized_pnl: pos.unrealizedPnl,
    unrealized_pnl_pct: pos.unrealizedPnlPct,
    notional: pos.notional,
    opened_at: pos.openedAt,
    opened_date: pos.openedDate ?? "",
    short_id: pos.shortId ?? "",
    status: pos.status,
    realized_pnl: pos.realizedPnl,
    source_console_id: pos.sourceConsoleId ?? null,
    pos_key: pk,
    tp_pct: pos.tpPct ?? null,
    sl_pct: pos.slPct ?? null,
    tp_price: pos.tpPrice ?? null,
    sl_price: pos.slPrice ?? null,
  }
}

function orderToRow(order: ChartPlacedOrder, positionDbId: string): OrderRow {
  return {
    id: order.id,
    session_id: SESSION_ID,
    position_id: positionDbId,
    side: order.side,
    price: order.price,
    qty: order.qty,
    order_type: order.orderType,
    symbol: order.symbol ?? null,
    account_id: order.accountId ?? null,
    exchange_id: order.exchangeId ?? null,
    market_type: order.marketType ?? null,
    leverage: order.leverage ?? null,
    margin: order.margin ?? null,
    time: order.time ?? null,
    filled_at: order.filledAt ?? null,
    filled_pct: order.filledPct ?? null,
    status: order.status ?? "pending",
    source: order.source ?? "manual",
    grid_index: order.gridIndex ?? null,
    grid_console_id: order.gridConsoleId ?? null,
    bot_name: order.botName ?? null,
    webhook_name: order.webhookName ?? null,
  }
}

function rowToPosition(row: PositionRow, orders: ChartPlacedOrder[]): [string, LivePosition] {
  const pos: LivePosition = {
    accountId: row.account_id,
    exchangeId: row.exchange_id,
    marketType: row.market_type as "spot" | "futures",
    symbol: row.symbol,
    side: row.side as "long" | "short",
    size: row.size,
    realSize: row.real_size ?? 0,
    avgEntry: row.avg_entry,
    leverage: row.leverage,
    marginMode: (row.margin_mode ?? "cross") as "cross" | "isolated",
    markPrice: row.mark_price,
    unrealizedPnl: row.unrealized_pnl,
    unrealizedPnlPct: row.unrealized_pnl_pct,
    notional: row.notional,
    openedAt: row.opened_at,
    openedDate: row.opened_date ?? "",
    shortId: row.short_id ?? "",
    status: row.status as "active" | "pending" | "closed",
    realizedPnl: row.realized_pnl,
    sourceConsoleId: row.source_console_id ?? undefined,
    tpPct: row.tp_pct ?? undefined,
    slPct: row.sl_pct ?? undefined,
    tpPrice: row.tp_price ?? undefined,
    slPrice: row.sl_price ?? undefined,
    orders,
  }
  return [row.pos_key, pos]
}

function rowToOrder(row: OrderRow): ChartPlacedOrder {
  return {
    id: row.id,
    side: row.side as "buy" | "sell",
    price: row.price,
    qty: row.qty,
    orderType: row.order_type as "limit" | "market",
    symbol: row.symbol ?? undefined,
    accountId: row.account_id ?? undefined,
    exchangeId: row.exchange_id ?? undefined,
    marketType: row.market_type as "spot" | "futures" | undefined,
    leverage: row.leverage ?? undefined,
    margin: row.margin ?? undefined,
    time: row.time ?? undefined,
    filledAt: row.filled_at ?? undefined,
    filledPct: row.filled_pct ?? undefined,
    status: (row.status as "pending" | "filled" | "cancelled") ?? undefined,
    source: (row.source as "manual" | "grid" | "dca" | "bot" | "webhook") ?? undefined,
    gridIndex: row.grid_index ?? undefined,
    gridConsoleId: row.grid_console_id ?? undefined,
    botName: row.bot_name ?? undefined,
    webhookName: row.webhook_name ?? undefined,
  }
}

// ── Public API ────────────────────────────────────────────────────────────────

export type PositionsMap = Record<string, LivePosition>

/** Load all positions + their orders for the current session */
export async function loadPositions(): Promise<PositionsMap> {
  const { data: posRows, error: posErr } = await supabase
    .from("positions")
    .select("*")
    .eq("session_id", SESSION_ID)

  if (posErr || !posRows) return {}

  if (posRows.length === 0) return {}

  const posIds = posRows.map((r) => r.id)
  const { data: ordRows, error: ordErr } = await supabase
    .from("orders")
    .select("*")
    .in("position_id", posIds)

  const ordersByPosId: Record<string, ChartPlacedOrder[]> = {}
  if (!ordErr && ordRows) {
    for (const row of ordRows as OrderRow[]) {
      if (!ordersByPosId[row.position_id]) ordersByPosId[row.position_id] = []
      ordersByPosId[row.position_id].push(rowToOrder(row))
    }
  }

  const result: PositionsMap = {}
  for (const row of posRows as PositionRow[]) {
    const [pk, pos] = rowToPosition(row, ordersByPosId[row.id] ?? [])
    result[pk] = pos
  }
  return result
}

/** Upsert a position row, then sync its orders (delete-all + re-insert) */
export async function upsertPosition(pk: string, pos: LivePosition): Promise<void> {
  const row = positionToRow(pk, pos)

  const { data, error } = await supabase
    .from("positions")
    .upsert(row, { onConflict: "session_id,pos_key" })
    .select("id")
    .maybeSingle()

  if (error || !data) return

  const positionDbId: string = data.id

  // Replace all orders for this position
  await supabase.from("orders").delete().eq("position_id", positionDbId)

  if (pos.orders.length > 0) {
    const orderRows = pos.orders.map((o) => orderToRow(o, positionDbId))
    await supabase.from("orders").insert(orderRows)
  }
}

/** Delete a position row (orders cascade-delete via FK) */
export async function deletePosition(pk: string): Promise<void> {
  await supabase
    .from("positions")
    .delete()
    .eq("session_id", SESSION_ID)
    .eq("pos_key", pk)
}
