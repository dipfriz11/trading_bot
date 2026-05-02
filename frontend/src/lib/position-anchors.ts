import type { ChartPlacedOrder } from "@/types/terminal"

export interface PositionAnchors {
  firstOrder: number   // closest order to TP direction (long = highest, short = lowest)
  extremeOrder: number // furthest pending order; falls back to avgEntry when all orders are filled
  avgEntry: number     // volume-weighted average entry price across all orders
}

export type SlMode = "extreme_order" | "avg_entry"

export function getSlBase(anchors: PositionAnchors, slMode: SlMode): number {
  if (slMode === "avg_entry") return anchors.avgEntry
  return anchors.extremeOrder
}

export function getPositionAnchors(
  orders: Pick<ChartPlacedOrder, "price" | "qty" | "status">[],
  side: "long" | "short",
): PositionAnchors | null {
  const active = orders.filter((o) => o.price > 0 && o.qty > 0)
  if (active.length === 0) return null

  const isLong = side === "long"
  const prices = active.map((o) => o.price)

  const firstOrder = isLong ? Math.max(...prices) : Math.min(...prices)

  const totalQty = active.reduce((s, o) => s + o.qty, 0)
  const avgEntry = active.reduce((s, o) => s + o.price * o.qty, 0) / totalQty

  // extremeOrder uses only pending orders. If all orders are filled, fall back to avgEntry.
  const pending = active.filter((o) => o.status !== "filled")
  const pendingPrices = pending.map((o) => o.price)
  const extremeOrder = pendingPrices.length > 0
    ? (isLong ? Math.min(...pendingPrices) : Math.max(...pendingPrices))
    : avgEntry

  const result = { firstOrder, extremeOrder, avgEntry }
  console.log("[GET_POSITION_ANCHORS] side:", side, "allOrders:", active.length, "pendingOrders:", pending.length, "→", result)
  return result
}
