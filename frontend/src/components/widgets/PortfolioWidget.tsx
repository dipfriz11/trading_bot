import { useState, useRef, useEffect } from "react"
import { EXCHANGES } from "@/lib/mock-data"
import type { Widget, LivePosition, ChartPlacedOrder } from "@/types/terminal"
import type { ChartTpSl } from "@/contexts/TerminalContext"
import { useTerminal, posKey } from "@/contexts/TerminalContext"
import { X, ChevronDown, ChevronRight, Pencil, Check, CircleCheck as CheckCircle2, Circle, CircleAlert as AlertCircle } from "lucide-react"

// ─── Color palette ────────────────────────────────────────────────────────────
const C = {
  long: "#00e5a0",
  short: "#ff4757",
  buy: "#00e5a0",
  sell: "#ff4757",
  pnlPos: "#00e5a0",
  pnlNeg: "#ff4757",
  muted: "rgba(200,214,229,0.5)",
  dim: "rgba(255,255,255,0.25)",
  dimmer: "rgba(255,255,255,0.14)",
  accent: "#4d9fff",
  warn: "#ffaa44",
  border: "rgba(255,255,255,0.05)",
  rowHover: "rgba(255,255,255,0.025)",
  bg: "rgba(0,0,0,0.12)",
  filled: "#00e5a0",
}

function fmtPrice(n: number) {
  if (n >= 1000) return n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  if (n >= 1) return n.toFixed(4)
  return n.toFixed(6)
}

function fmtQty(n: number) {
  return n.toFixed(n < 1 ? 4 : 2)
}

function fmtUSDT(n: number) {
  return n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function fmtPct(n: number, decimals = 2) {
  const abs = Math.abs(n)
  const sign = n >= 0 ? "+" : "-"
  return `${sign}${abs.toFixed(decimals)}%`
}

// ─── Tags G / TP / SL ─────────────────────────────────────────────────────────

function PositionTags({ pos }: { pos: LivePosition }) {
  const hasGrid = pos.orders.some((o) => o.source === "grid")
  const hasTp = pos.tpPrice != null || pos.tpPct != null || pos.orders.some((o) => o.side === "sell" && o.source === "grid")
  const hasSl = pos.slPrice != null || pos.slPct != null || pos.orders.some((o) => o.orderType === "market" && o.side === "sell")

  return (
    <div className="flex items-center gap-0.5">
      {hasGrid && (
        <span className="px-1 py-0.5 rounded font-mono font-bold"
          style={{ fontSize: 8, background: "rgba(77,159,255,0.12)", color: C.accent, border: "1px solid rgba(77,159,255,0.25)" }}>
          G
        </span>
      )}
      {hasTp && (
        <span className="px-1 py-0.5 rounded font-mono font-bold"
          style={{ fontSize: 8, background: "rgba(0,229,160,0.1)", color: C.buy, border: "1px solid rgba(0,229,160,0.22)" }}>
          TP
        </span>
      )}
      {hasSl && (
        <span className="px-1 py-0.5 rounded font-mono font-bold"
          style={{ fontSize: 8, background: "rgba(255,71,87,0.1)", color: C.sell, border: "1px solid rgba(255,71,87,0.22)" }}>
          SL
        </span>
      )}
    </div>
  )
}

// ─── Collapsed position row ───────────────────────────────────────────────────

function CollapsedRow({
  pos,
  positionKey: _positionKey,
  expanded,
  onToggle,
  onClose,
}: {
  pos: LivePosition
  positionKey: string
  expanded: boolean
  onToggle: () => void
  onClose: () => void
}) {
  const isLong = pos.side === "long"
  const sideColor = isLong ? C.long : C.short
  const isActive = pos.status === "active"
  const pnlColor = pos.unrealizedPnl >= 0 ? C.pnlPos : C.pnlNeg
  const exLabel = EXCHANGES.find((e) => e.id === pos.exchangeId)?.label ?? pos.exchangeId
  const marginLabel = `${pos.marginMode === "cross" ? "Cross" : "Iso"} ×${pos.leverage}`

  return (
    <div
      className="group flex items-center gap-2 px-2 py-1.5 cursor-pointer transition-colors"
      style={{ borderBottom: `1px solid ${C.border}`, background: "transparent" }}
      onClick={onToggle}
      onMouseDown={(e) => e.stopPropagation()}
    >
      {/* Expand arrow */}
      <span style={{ color: C.dimmer, flexShrink: 0 }}>
        {expanded ? <ChevronDown size={10} /> : <ChevronRight size={10} />}
      </span>

      {/* ID block */}
      <div className="flex flex-col" style={{ minWidth: 54 }}>
        <span className="font-mono font-bold" style={{ fontSize: 10, color: "rgba(200,214,229,0.85)" }}>
          {pos.shortId || pos.accountId.slice(0, 7)}
        </span>
        <span className="font-mono" style={{ fontSize: 8, color: C.dim }}>
          {pos.accountId.slice(0, 8)}
        </span>
      </div>

      {/* Side + margin + leverage */}
      <div className="flex flex-col" style={{ minWidth: 62 }}>
        <span className="font-mono font-bold" style={{ fontSize: 10, color: sideColor, letterSpacing: "0.02em" }}>
          {isLong ? "LONG" : "SHORT"}
        </span>
        <span className="font-mono" style={{ fontSize: 8, color: C.dim }}>
          {marginLabel}
        </span>
      </div>

      {/* Symbol */}
      <div className="flex items-center gap-1" style={{ minWidth: 80 }}>
        <span className="font-mono font-semibold" style={{ fontSize: 11, color: "rgba(200,214,229,0.9)" }}>
          {pos.symbol}
        </span>
        <span className="font-mono" style={{ fontSize: 8, color: C.dim }}>{exLabel.slice(0, 3).toUpperCase()}</span>
      </div>

      {/* PnL (active) or empty (pending) */}
      {isActive ? (
        <div className="flex flex-col items-end" style={{ minWidth: 70 }}>
          <span className="font-mono font-bold" style={{ fontSize: 10, color: pnlColor }}>
            {pos.unrealizedPnl >= 0 ? "+" : ""}${fmtUSDT(pos.unrealizedPnl)}
          </span>
          <span className="font-mono" style={{ fontSize: 8, color: pnlColor, opacity: 0.75 }}>
            {fmtPct(pos.unrealizedPnlPct)}
          </span>
        </div>
      ) : (
        <div className="flex flex-col items-end" style={{ minWidth: 70 }}>
          <span className="font-mono" style={{ fontSize: 9, color: C.dim }}>virtual</span>
        </div>
      )}

      {/* Date + Tags */}
      <div className="flex flex-col items-end ml-auto gap-0.5" style={{ minWidth: 80 }}>
        <div className="flex items-center gap-1">
          <span className="font-mono" style={{ fontSize: 8, color: C.dim }}>
            {pos.openedAt} {pos.openedDate}
          </span>
        </div>
        <PositionTags pos={pos} />
      </div>

      {/* Close button */}
      <button
        className="opacity-0 group-hover:opacity-100 transition-opacity p-0.5 rounded flex-shrink-0"
        style={{ color: "rgba(255,71,87,0.7)" }}
        onClick={(e) => { e.stopPropagation(); onClose() }}
        onMouseDown={(e) => e.stopPropagation()}
        title="Close position"
      >
        <X size={11} />
      </button>
    </div>
  )
}

// ─── Order row inside expanded position ──────────────────────────────────────

function PositionOrderRow({
  order,
  positionKey,
  onCancel,
  isSynthetic = false,
  syntheticLabel,
}: {
  order: ChartPlacedOrder
  positionKey: string
  onCancel: () => void
  isSynthetic?: boolean
  syntheticLabel?: string
}) {
  const { updatePlacedOrder } = useTerminal()
  const isBuy = order.side === "buy"
  const sideColor = isBuy ? C.buy : C.sell
  const isFilled = order.status === "filled"
  const isCancelled = order.status === "cancelled"
  const isPending = order.status === "pending"

  let typeLabel = order.orderType === "market" ? "Market" : "Limit"
  if (order.source === "grid" && order.gridIndex != null) {
    typeLabel = `Limit · ${order.gridIndex}`
  }

  const isSlOrder = order.orderType === "market" && order.side === "sell" && order.source === "grid"
  const typeDisplay = syntheticLabel ?? (isSlOrder ? "SL Market" : typeLabel)

  const fillPct = order.filledPct ?? (isFilled ? 100 : 0)

  // ── Inline edit state ──────────────────────────────────────────────────────
  const [editing, setEditing] = useState(false)
  const [editPrice, setEditPrice] = useState("")
  const [editQty, setEditQty] = useState("")
  const priceRef = useRef<HTMLInputElement>(null)

  const startEdit = (e: React.MouseEvent) => {
    e.stopPropagation()
    if (!isPending) return
    setEditPrice(String(order.price))
    setEditQty(String(order.qty))
    setEditing(true)
  }

  useEffect(() => {
    if (editing) priceRef.current?.select()
  }, [editing])

  const commitEdit = (e: React.MouseEvent) => {
    e.stopPropagation()
    const newPrice = parseFloat(editPrice)
    const newQty = parseFloat(editQty)
    const updates: Partial<ChartPlacedOrder> = {}
    if (!isNaN(newPrice) && newPrice > 0) updates.price = newPrice
    if (!isNaN(newQty) && newQty > 0) updates.qty = newQty
    if (Object.keys(updates).length > 0) {
      updatePlacedOrder(positionKey, order.id, updates)
    }
    setEditing(false)
  }

  const cancelEdit = (e: React.MouseEvent) => {
    e.stopPropagation()
    setEditing(false)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      const newPrice = parseFloat(editPrice)
      const newQty = parseFloat(editQty)
      const updates: Partial<ChartPlacedOrder> = {}
      if (!isNaN(newPrice) && newPrice > 0) updates.price = newPrice
      if (!isNaN(newQty) && newQty > 0) updates.qty = newQty
      if (Object.keys(updates).length > 0) {
        updatePlacedOrder(positionKey, order.id, updates)
      }
      setEditing(false)
    } else if (e.key === "Escape") {
      setEditing(false)
    }
  }

  const inlineInput: React.CSSProperties = {
    background: "rgba(30,111,239,0.1)",
    border: "1px solid rgba(30,111,239,0.35)",
    borderRadius: 3,
    color: "rgba(200,214,229,0.95)",
    fontSize: 9,
    fontFamily: "monospace",
    padding: "1px 4px",
    outline: "none",
    width: "100%",
  }

  // ── Edit mode row ──────────────────────────────────────────────────────────
  if (editing) {
    return (
      <div
        className="flex items-center gap-2 px-3 py-1.5"
        style={{
          borderBottom: `1px solid ${C.border}`,
          background: "rgba(30,111,239,0.04)",
          border: "1px solid rgba(30,111,239,0.18)",
        }}
        onMouseDown={(e) => e.stopPropagation()}
      >
        {/* BUY/SELL badge */}
        <span
          className="px-1.5 py-0.5 rounded font-mono font-bold flex-shrink-0"
          style={{
            fontSize: 8,
            background: isBuy ? "rgba(0,229,160,0.1)" : "rgba(255,71,87,0.1)",
            color: sideColor,
            border: `1px solid ${isBuy ? "rgba(0,229,160,0.22)" : "rgba(255,71,87,0.22)"}`,
          }}
        >
          {isBuy ? "BUY" : "SELL"}
        </span>

        {/* Type label */}
        <span className="font-mono flex-shrink-0" style={{ fontSize: 9, color: "rgba(200,214,229,0.5)", minWidth: 50 }}>
          {typeDisplay}
        </span>

        {/* Price input */}
        <div className="flex flex-col gap-0.5 flex-1" style={{ minWidth: 70 }}>
          <span className="font-mono" style={{ fontSize: 7, color: C.dim }}>Price</span>
          <input
            ref={priceRef}
            value={editPrice}
            onChange={(e) => setEditPrice(e.target.value)}
            onKeyDown={handleKeyDown}
            style={inlineInput}
            type="number"
            step="any"
          />
        </div>

        {/* Qty input */}
        <div className="flex flex-col gap-0.5 flex-1" style={{ minWidth: 55 }}>
          <span className="font-mono" style={{ fontSize: 7, color: C.dim }}>Qty</span>
          <input
            value={editQty}
            onChange={(e) => setEditQty(e.target.value)}
            onKeyDown={handleKeyDown}
            style={inlineInput}
            type="number"
            step="any"
          />
        </div>

        {/* Confirm */}
        <button
          onClick={commitEdit}
          className="flex-shrink-0 p-1 rounded transition-colors"
          style={{ color: C.filled, background: "rgba(0,229,160,0.1)", border: "1px solid rgba(0,229,160,0.25)" }}
          title="Save changes"
        >
          <Check size={9} />
        </button>

        {/* Cancel edit */}
        <button
          onClick={cancelEdit}
          className="flex-shrink-0 p-1 rounded transition-colors"
          style={{ color: "rgba(255,71,87,0.7)", background: "rgba(255,71,87,0.08)", border: "1px solid rgba(255,71,87,0.2)" }}
          title="Cancel"
        >
          <X size={9} />
        </button>
      </div>
    )
  }

  // ── Normal row ─────────────────────────────────────────────────────────────
  const isTpSynthetic = isSynthetic && syntheticLabel?.startsWith("TP")
  const isSlSynthetic = isSynthetic && syntheticLabel?.startsWith("SL")
  const syntheticBorderColor = isTpSynthetic ? "rgba(0,229,160,0.35)" : isSlSynthetic ? "rgba(255,71,87,0.35)" : undefined

  return (
    <div
      className="group flex items-center gap-2 px-3 py-1.5 transition-colors hover:bg-white/[0.02]"
      style={{
        borderBottom: `1px solid ${C.border}`,
        ...(syntheticBorderColor ? { borderLeft: `2px solid ${syntheticBorderColor}`, paddingLeft: 10 } : {}),
        ...(isSynthetic ? { background: isTpSynthetic ? "rgba(0,229,160,0.025)" : "rgba(255,71,87,0.025)" } : {}),
      }}
      onMouseDown={(e) => e.stopPropagation()}
    >
      {/* Order ID */}
      <span className="font-mono" style={{ fontSize: 8, color: C.dimmer, minWidth: 66, flexShrink: 0 }}>
        {isSynthetic ? (isTpSynthetic ? "Take Profit" : "Stop Loss").slice(0, 10) : order.id.slice(0, 10)}
      </span>

      {/* BUY/SELL badge */}
      <span
        className="px-1.5 py-0.5 rounded font-mono font-bold flex-shrink-0"
        style={{
          fontSize: 8,
          background: isBuy ? "rgba(0,229,160,0.1)" : "rgba(255,71,87,0.1)",
          color: sideColor,
          border: `1px solid ${isBuy ? "rgba(0,229,160,0.22)" : "rgba(255,71,87,0.22)"}`,
        }}
      >
        {isBuy ? "BUY" : "SELL"}
      </span>

      {/* Order type */}
      <span className="font-mono flex-shrink-0" style={{ fontSize: 9, color: "rgba(200,214,229,0.7)", minWidth: 70 }}>
        {typeDisplay}
      </span>

      {/* Qty */}
      <div className="flex flex-col items-end" style={{ minWidth: 40 }}>
        <span className="font-mono" style={{ fontSize: 9, color: "rgba(200,214,229,0.85)" }}>{fmtQty(order.qty)}</span>
        {order.source === "grid" && (
          <div className="flex gap-0.5">
            <span style={{ color: C.dim, fontSize: 8 }}>≡</span>
            <span className="font-mono" style={{ fontSize: 7, color: C.dim }}>
              {order.gridIndex != null ? `${order.gridIndex}` : ""}
            </span>
          </div>
        )}
      </div>

      {/* Fill status icon */}
      <div className="flex-shrink-0">
        {isFilled ? (
          <CheckCircle2 size={10} style={{ color: C.filled }} />
        ) : isCancelled ? (
          <AlertCircle size={10} style={{ color: C.sell }} />
        ) : isSlOrder ? (
          <Circle size={10} style={{ color: C.warn }} />
        ) : (
          <div style={{
            width: 10, height: 10, borderRadius: "50%",
            border: `1.5px solid ${C.dim}`,
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            <div style={{ width: 5, height: 5, borderRadius: "50%", background: C.dim, opacity: 0 }} />
          </div>
        )}
      </div>

      {/* Price + pencil */}
      <div className="flex items-center gap-1 flex-1">
        <span className="font-mono" style={{ fontSize: 9, color: "rgba(200,214,229,0.85)" }}>
          {fmtPrice(order.price)}
        </span>
        {isPending && !isSynthetic && (
          <button
            className="opacity-0 group-hover:opacity-60 hover:!opacity-100 transition-opacity"
            style={{ color: C.accent }}
            title="Edit order"
            onClick={startEdit}
          >
            <Pencil size={8} />
          </button>
        )}
      </div>

      {/* Fill % */}
      <span className="font-mono" style={{ fontSize: 9, color: fillPct === 100 ? C.filled : C.dim, minWidth: 30, textAlign: "right" }}>
        {fillPct}%
      </span>

      {/* Notional / volume */}
      <span className="font-mono" style={{ fontSize: 9, color: C.muted, minWidth: 38, textAlign: "right" }}>
        {fmtUSDT(order.qty * order.price)}
      </span>

      {/* Date placed */}
      <div className="flex flex-col items-end" style={{ minWidth: 80 }}>
        {order.time && (
          <span className="font-mono" style={{ fontSize: 8, color: C.dim }}>
            {order.time}
          </span>
        )}
        {order.filledAt && (
          <span className="font-mono" style={{ fontSize: 8, color: C.filled, opacity: 0.8 }}>
            → {order.filledAt}
          </span>
        )}
      </div>

      {/* Cancel button */}
      {isPending && !isSynthetic && (
        <button
          className="opacity-0 group-hover:opacity-100 transition-opacity p-0.5 rounded flex-shrink-0"
          style={{ color: "rgba(255,71,87,0.65)" }}
          onClick={(e) => { e.stopPropagation(); onCancel() }}
          title="Cancel order"
        >
          <X size={9} />
        </button>
      )}
    </div>
  )
}

// ─── Expanded position details ────────────────────────────────────────────────

function ExpandedPosition({
  pos,
  positionKey,
  tpSl,
  onClose,
}: {
  pos: LivePosition
  positionKey: string
  tpSl?: ChartTpSl
  onClose: (size: number) => void
}) {
  const { removePlacedOrder } = useTerminal()
  const isActive = pos.status === "active"
  const isLong = pos.side === "long"
  const pnlColor = pos.unrealizedPnl >= 0 ? C.pnlPos : C.pnlNeg

  // Sort orders: filled first, then pending, then cancelled
  const sortedOrders = [...pos.orders].sort((a, b) => {
    const rank = (o: ChartPlacedOrder) => o.status === "filled" ? 0 : o.status === "pending" ? 1 : 2
    return rank(a) - rank(b)
  })

  // Build synthetic TP/SL rows for active (real) positions
  const tpRows: ChartPlacedOrder[] = []
  const slRow: ChartPlacedOrder | null = (() => {
    if (!isActive || !tpSl) return null
    if (tpSl.sl != null) {
      return {
        id: `${positionKey}:sl`,
        side: isLong ? "sell" : "buy",
        orderType: "market",
        price: tpSl.sl,
        qty: pos.realSize,
        status: "pending",
        source: "user",
        time: undefined,
      } as unknown as ChartPlacedOrder
    }
    return null
  })()

  if (isActive && tpSl) {
    const levels = tpSl.tpLevels && tpSl.tpLevels.length > 1 ? tpSl.tpLevels : tpSl.tp != null ? [tpSl.tp] : []
    levels.forEach((price, i) => {
      tpRows.push({
        id: `${positionKey}:tp:${i}`,
        side: isLong ? "sell" : "buy",
        orderType: "limit",
        price,
        qty: pos.realSize,
        status: "pending",
        source: "user",
        time: undefined,
      } as unknown as ChartPlacedOrder)
    })
  }

  return (
    <div
      style={{ background: C.bg, borderBottom: `1px solid rgba(255,255,255,0.07)` }}
      onMouseDown={(e) => e.stopPropagation()}
    >
      {/* Active position summary row */}
      {isActive && (
        <div
          className="flex items-center gap-2 px-3 py-1.5"
          style={{ borderBottom: `1px solid ${C.border}`, background: "rgba(255,255,255,0.015)" }}
        >
          {/* Filled size / total size */}
          <div className="flex flex-col" style={{ minWidth: 60 }}>
            <span className="font-mono font-semibold" style={{ fontSize: 10, color: "rgba(200,214,229,0.9)" }}>
              {fmtQty(pos.realSize)}
            </span>
            {pos.size !== pos.realSize && (
              <span className="font-mono" style={{ fontSize: 8, color: C.accent }}>
                +{fmtQty(pos.size)}
              </span>
            )}
          </div>

          {/* SL % */}
          {pos.slPct != null && (
            <div className="flex flex-col" style={{ minWidth: 55 }}>
              <span className="font-mono font-semibold" style={{ fontSize: 10, color: C.sell }}>
                {fmtPct(-Math.abs(pos.slPct))}
              </span>
              {pos.slPrice != null && (
                <span className="font-mono" style={{ fontSize: 8, color: C.dim }}>SL</span>
              )}
            </div>
          )}

          {/* PnL $ */}
          <div className="flex flex-col" style={{ minWidth: 58 }}>
            <span className="font-mono font-semibold" style={{ fontSize: 10, color: pnlColor }}>
              {pos.unrealizedPnl >= 0 ? "+" : ""}${fmtUSDT(pos.unrealizedPnl)}
            </span>
          </div>

          {/* Entry / Mark */}
          <div className="flex flex-col" style={{ minWidth: 72 }}>
            <span className="font-mono" style={{ fontSize: 10, color: "rgba(200,214,229,0.85)" }}>
              {fmtPrice(pos.avgEntry)}
            </span>
            <span className="font-mono" style={{ fontSize: 8, color: C.dim }}>
              {fmtPrice(pos.markPrice)}
            </span>
          </div>

          {/* TP % */}
          {pos.tpPct != null && (
            <div className="flex flex-col" style={{ minWidth: 40 }}>
              <span className="font-mono font-semibold" style={{ fontSize: 10, color: C.buy }}>
                {fmtPct(pos.tpPct)}
              </span>
              <span className="font-mono" style={{ fontSize: 8, color: C.dim }}>TP</span>
            </div>
          )}

          {/* Volume */}
          <div className="flex flex-col items-end ml-auto" style={{ minWidth: 55 }}>
            <span className="font-mono" style={{ fontSize: 10, color: C.muted }}>
              {fmtUSDT(pos.notional)}
            </span>
            {pos.leverage > 1 && (
              <span className="font-mono" style={{ fontSize: 8, color: C.dim }}>
                m: {fmtUSDT(pos.notional / pos.leverage)}
              </span>
            )}
          </div>

          {/* Progress bar for fill */}
          {pos.realSize > 0 && pos.size > 0 && (
            <div style={{ width: 48, minWidth: 48 }}>
              <div style={{ height: 3, background: "rgba(255,255,255,0.06)", borderRadius: 2, overflow: "hidden" }}>
                <div style={{
                  height: "100%",
                  width: `${Math.min(100, (pos.realSize / pos.size) * 100)}%`,
                  background: isLong ? C.long : C.short,
                  borderRadius: 2,
                }} />
              </div>
            </div>
          )}
        </div>
      )}

      {/* Orders header row */}
      <div
        className="grid px-3 py-0.5"
        style={{
          gridTemplateColumns: "70px 48px 72px 28px 1fr 32px 52px 80px 24px",
          borderBottom: `1px solid ${C.border}`,
        }}
      >
        {["ID", "Side", "Type", "Qty", "Price", "%", "Vol", "Date", ""].map((h) => (
          <span key={h} className="font-mono" style={{ fontSize: 7, color: C.dimmer, textTransform: "uppercase", letterSpacing: "0.04em" }}>
            {h}
          </span>
        ))}
      </div>

      {/* Order rows */}
      {/* TP rows at top */}
      {tpRows.map((order) => (
        <PositionOrderRow
          key={order.id}
          order={order}
          positionKey={positionKey}
          isSynthetic
          syntheticLabel="TP Limit"
          onCancel={() => {}}
        />
      ))}

      {sortedOrders.length === 0 && tpRows.length === 0 && !slRow ? (
        <div className="px-3 py-2 font-mono" style={{ fontSize: 9, color: C.dim }}>
          No orders
        </div>
      ) : (
        sortedOrders.map((order) => (
          <PositionOrderRow
            key={order.id}
            order={order}
            positionKey={positionKey}
            onCancel={() => removePlacedOrder(positionKey, order.id)}
          />
        ))
      )}

      {/* SL row at bottom */}
      {slRow && (
        <PositionOrderRow
          order={slRow}
          positionKey={positionKey}
          isSynthetic
          syntheticLabel="SL Market"
          onCancel={() => {}}
        />
      )}

      {/* Close actions */}
      <div
        className="flex items-center gap-1.5 px-3 py-1.5"
        style={{ borderTop: `1px solid ${C.border}` }}
      >
        <span className="font-mono" style={{ fontSize: 8, color: C.dim, marginRight: 4 }}>Close:</span>
        {[25, 50, 75].map((pct) => (
          <button
            key={pct}
            className="px-2 py-0.5 rounded font-mono transition-colors hover:bg-white/10"
            style={{
              fontSize: 9,
              background: "rgba(255,255,255,0.04)",
              border: `1px solid rgba(255,255,255,0.08)`,
              color: C.muted,
            }}
            onClick={() => onClose(pos.size * (pct / 100))}
          >
            {pct}%
          </button>
        ))}
        <button
          className="px-2 py-0.5 rounded font-mono transition-colors ml-auto"
          style={{
            fontSize: 9,
            background: "rgba(255,71,87,0.08)",
            border: "1px solid rgba(255,71,87,0.2)",
            color: C.sell,
          }}
          onClick={() => onClose(pos.size)}
        >
          Close All
        </button>
      </div>
    </div>
  )
}

// ─── Column headers ───────────────────────────────────────────────────────────

function PositionListHeader() {
  return (
    <div
      className="flex items-center gap-2 px-2 py-1"
      style={{ borderBottom: `1px solid rgba(255,255,255,0.06)` }}
    >
      {[
        { label: "ID", w: 54 },
        { label: "Type", w: 62 },
        { label: "Pair", w: 80 },
        { label: "PnL", w: 70 },
        { label: "Date", flex: true },
      ].map(({ label, w, flex }) => (
        <span
          key={label}
          className="font-mono"
          style={{
            fontSize: 8,
            color: C.dimmer,
            textTransform: "uppercase",
            letterSpacing: "0.04em",
            width: flex ? undefined : w,
            flex: flex ? 1 : undefined,
            textAlign: flex ? "right" : undefined,
          }}
        >
          {label}
        </span>
      ))}
      <span style={{ width: 20 }} />
    </div>
  )
}

// ─── Main widget ──────────────────────────────────────────────────────────────

export function PortfolioWidget(_props: { widget: Widget }) {
  const [expandedKeys, setExpandedKeys] = useState<Set<string>>(new Set())
  const { positions: livePositions, closePosition, partialClosePosition, tpSlOrders, activeTab } = useTerminal()

  // Build map: posKey -> ChartTpSl by matching chart widgets on symbol
  const tpSlByPosKey: Record<string, ChartTpSl> = {}
  if (activeTab) {
    for (const widget of activeTab.widgets) {
      if (widget.type !== "chart" || !widget.symbol) continue
      const tpsl = tpSlOrders[widget.id]
      if (!tpsl) continue
      // Match active positions by symbol
      for (const [pk, pos] of Object.entries(livePositions)) {
        if (pos.symbol === widget.symbol && pos.status === "active") {
          tpSlByPosKey[pk] = tpsl
        }
      }
    }
  }

  const liveList = Object.entries(livePositions)

  const totalPnl = liveList.reduce((sum, [, p]) => sum + p.unrealizedPnl, 0)
  const activeCount = liveList.filter(([, p]) => p.status === "active").length
  const pendingCount = liveList.filter(([, p]) => p.status === "pending").length
  const isPnlPos = totalPnl >= 0

  function toggleExpand(pk: string) {
    setExpandedKeys((prev) => {
      const next = new Set(prev)
      if (next.has(pk)) next.delete(pk)
      else next.add(pk)
      return next
    })
  }

  function handleClose(pos: LivePosition, size: number) {
    const pk = posKey(pos.accountId, pos.exchangeId, pos.marketType, pos.symbol, pos.side)
    if (size >= pos.size) closePosition(pk)
    else partialClosePosition(pk, size)
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div
        className="flex items-center gap-4 px-3 py-1.5 flex-shrink-0"
        style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}
        onMouseDown={(e) => e.stopPropagation()}
      >
        {/* Total PnL */}
        {liveList.length > 0 && (
          <div>
            <div className="font-mono" style={{ fontSize: 8, color: C.dim, textTransform: "uppercase", letterSpacing: "0.04em" }}>
              Total P&L
            </div>
            <div className="font-mono font-bold" style={{ fontSize: 12, color: isPnlPos ? C.pnlPos : C.pnlNeg }}>
              {isPnlPos ? "+" : ""}${totalPnl.toFixed(2)}
            </div>
          </div>
        )}

        {/* Counts */}
        <div className="flex items-center gap-2">
          {activeCount > 0 && (
            <div className="flex items-center gap-1">
              <div style={{ width: 6, height: 6, borderRadius: "50%", background: C.long }} />
              <span className="font-mono" style={{ fontSize: 9, color: C.muted }}>{activeCount} active</span>
            </div>
          )}
          {pendingCount > 0 && (
            <div className="flex items-center gap-1">
              <div style={{ width: 6, height: 6, borderRadius: "50%", background: C.warn }} />
              <span className="font-mono" style={{ fontSize: 9, color: C.muted }}>{pendingCount} virtual</span>
            </div>
          )}
        </div>
      </div>

      {/* List */}
      <div className="flex-1 overflow-auto min-h-0" onMouseDown={(e) => e.stopPropagation()}>
        {liveList.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full gap-2" style={{ opacity: 0.22 }}>
            <span className="font-mono text-sm" style={{ color: "rgba(200,214,229,0.8)" }}>No open positions</span>
            <span className="font-mono text-xs" style={{ color: "rgba(200,214,229,0.5)" }}>Place orders to see positions here</span>
          </div>
        ) : (
          <>
            <PositionListHeader />
            {liveList.map(([pk, pos]) => {
              const expanded = expandedKeys.has(pk)
              return (
                <div key={pk}>
                  <CollapsedRow
                    pos={pos}
                    positionKey={pk}
                    expanded={expanded}
                    onToggle={() => toggleExpand(pk)}
                    onClose={() => handleClose(pos, pos.size)}
                  />
                  {expanded && (
                    <ExpandedPosition
                      pos={pos}
                      positionKey={pk}
                      tpSl={tpSlByPosKey[pk]}
                      onClose={(size) => handleClose(pos, size)}
                    />
                  )}
                </div>
              )
            })}
          </>
        )}
      </div>
    </div>
  )
}
