import React, { useState, useRef, useEffect, useCallback } from "react"
import { generateCandles, formatPrice, generateOrderBook, ACCOUNTS, EXCHANGES } from "@/lib/mock-data"
import { SYMBOLS } from "@/lib/mock-data"
import type { Widget, Candle, LivePosition } from "@/types/terminal"
import { useTerminal, posKey } from "@/contexts/TerminalContext"
import type { ChartPlacedOrder, ChartDraftOrder, ChartGridOrders, ChartGridPreview, ChartTpSl } from "@/contexts/TerminalContext"
import { ChevronDown, User, Building2 } from "lucide-react"
import { PositionBarCompact } from "./PositionBar"
import { usePositionSettings } from "@/hooks/usePositionSettings"

// Local order shape (same as context but aliased for clarity)
type PlacedOrder = ChartPlacedOrder
type DraftOrder = ChartDraftOrder

type AnchorField = "qty" | "amount"

function fmtQty(qty: number): string {
  const s = qty.toFixed(8)
  // trim trailing zeros but keep at least 2 decimal places
  return s.replace(/(\.\d*?)0+$/, "$1").replace(/\.$/, ".00")
}

function priceToString(price: number): string {
  if (price >= 1000) return price.toFixed(2)
  if (price >= 10) return price.toFixed(2)
  if (price >= 1) return price.toFixed(4)
  return price.toFixed(6)
}

interface ChartWidgetProps {
  widget: Widget
}

const CHART_COLORS = {
  up: "#00e5a0",
  down: "#ff4757",
  draft: "rgba(160,175,200,0.85)",
  draftClose: "rgba(100,115,135,0.9)",
  volume: { up: "rgba(0,229,160,0.25)", down: "rgba(255,71,87,0.25)" },
  grid: "rgba(255,255,255,0.04)",
  text: "rgba(200,214,229,0.7)",
}

// Badge for BUY (long) orders — anchored to the LEFT edge
function BuyOrderBadge({
  y, label, color, textColor, closeBtnColor, closeBtnFg, priceTagColor, priceTagFg,
  priceTag, onClose, onDragStart, onDoubleClick, axisX, padLeft, isEditing, isDraft,
}: {
  y: number; label: string; color: string; textColor?: string
  closeBtnColor: string; closeBtnFg: string
  priceTagColor: string; priceTagFg: string
  priceTag: string; isEditing: boolean; isDraft?: boolean
  onClose?: () => void
  onDragStart: (e: React.MouseEvent) => void
  onDoubleClick?: (e: React.MouseEvent) => void
  axisX: number; padLeft: number
}) {
  const PAD = 8
  const CLOSE_W = onClose ? 20 : 0
  const charW = 5.8
  const labelW = PAD + label.length * charW + PAD
  const badgeH = 20
  const by = y - badgeH / 2
  const badgeX = padLeft + 4
  const axisPriceW = 56
  const labelFill = textColor ?? color

  return (
    <g>
      {/* Editing highlight ring */}
      {isEditing && (
        <rect x={badgeX - 2} y={by - 2} width={labelW + CLOSE_W + 4} height={badgeH + 4}
          fill="none" stroke={labelFill ?? color} strokeWidth={1.5} rx={4}
          strokeDasharray="3,2" style={{ pointerEvents: "none" }} />
      )}
      {/* Badge body — acts as drag handle for draft, or select area for placed */}
      {isDraft ? (
        <g style={{ cursor: "ns-resize", pointerEvents: "auto" }} onMouseDown={onDragStart}>
          <rect x={badgeX} y={by} width={labelW} height={badgeH}
            fill={`${color}18`} stroke={color} strokeWidth={1} rx={3} />
          <text x={badgeX + PAD} y={y + 4} fontSize={9.5} fill={labelFill}
            fontFamily="Geist Variable, monospace" fontWeight="600"
            style={{ pointerEvents: "none" }}>
            {label}
          </text>
        </g>
      ) : (
        <g style={{ cursor: "grab", pointerEvents: "auto" }}
          onMouseDown={onDragStart}
          onDoubleClick={onDoubleClick}>
          <rect x={badgeX} y={by} width={labelW} height={badgeH}
            fill={color} stroke={labelFill ?? color} strokeWidth={isEditing ? 1.5 : 1} rx={3} />
          <text x={badgeX + PAD} y={y + 4} fontSize={9.5} fill={labelFill}
            fontFamily="Geist Variable, monospace" fontWeight="600"
            style={{ pointerEvents: "none" }}>
            {label}
          </text>
        </g>
      )}
      {onClose && <g style={{ cursor: "pointer", pointerEvents: "auto" }} onMouseDown={(e) => { e.stopPropagation(); onClose() }}>
        <rect x={badgeX + labelW} y={by} width={CLOSE_W} height={badgeH}
          fill={closeBtnColor} stroke={labelFill ?? closeBtnColor} strokeWidth={isEditing ? 1.5 : 1} rx={3} />
        <text x={badgeX + labelW + CLOSE_W / 2} y={y + 4.5}
          textAnchor="middle" dominantBaseline="middle"
          fontSize={11} fill={closeBtnFg}
          fontFamily="Geist Variable, monospace" fontWeight="bold"
          style={{ pointerEvents: "none" }}>
          ×
        </text>
      </g>}
      {/* Price tag on right axis */}
      <rect x={axisX} y={y - 9} width={axisPriceW} height={18}
        fill={priceTagColor} rx={2} style={{ pointerEvents: "none" }} />
      <text x={axisX + axisPriceW / 2} y={y + 4} textAnchor="middle" fontSize={9}
        fill={priceTagFg}
        fontFamily="Geist Variable, monospace" fontWeight="bold"
        style={{ pointerEvents: "none" }}>
        {priceTag}
      </text>
    </g>
  )
}

// Badge for SELL (short) orders — anchored to the RIGHT edge (just before price axis)
function SellOrderBadge({
  y, label, color, textColor, closeBtnColor, closeBtnFg, priceTagColor, priceTagFg,
  priceTag, onClose, onDragStart, onDoubleClick, axisX, isEditing, isDraft,
}: {
  y: number; label: string; color: string; textColor?: string
  closeBtnColor: string; closeBtnFg: string
  priceTagColor: string; priceTagFg: string
  priceTag: string; isEditing: boolean; isDraft?: boolean
  onClose?: () => void
  onDragStart: (e: React.MouseEvent) => void
  onDoubleClick?: (e: React.MouseEvent) => void
  axisX: number
}) {
  const PAD = 8
  const CLOSE_W = onClose ? 20 : 0
  const charW = 5.8
  const labelW = PAD + label.length * charW + PAD
  const badgeH = 20
  const by = y - badgeH / 2
  const axisPriceW = 56
  const badgeRight = axisX - 4
  const closeX = badgeRight - CLOSE_W - labelW
  const labelX = closeX + CLOSE_W
  const labelFill = textColor ?? color

  return (
    <g>
      {isEditing && (
        <rect x={closeX - 2} y={by - 2} width={labelW + CLOSE_W + 4} height={badgeH + 4}
          fill="none" stroke={labelFill ?? color} strokeWidth={1.5} rx={4}
          strokeDasharray="3,2" style={{ pointerEvents: "none" }} />
      )}
      {/* Close button */}
      {onClose && <g style={{ cursor: "pointer", pointerEvents: "auto" }} onMouseDown={(e) => { e.stopPropagation(); onClose() }}>
        <rect x={closeX} y={by} width={CLOSE_W} height={badgeH}
          fill={closeBtnColor} stroke={labelFill ?? closeBtnColor} strokeWidth={isEditing ? 1.5 : 1} rx={3} />
        <text x={closeX + CLOSE_W / 2} y={y + 4.5}
          textAnchor="middle" dominantBaseline="middle"
          fontSize={11} fill={closeBtnFg}
          fontFamily="Geist Variable, monospace" fontWeight="bold"
          style={{ pointerEvents: "none" }}>
          ×
        </text>
      </g>}
      {/* Badge body */}
      {isDraft ? (
        <g style={{ cursor: "ns-resize", pointerEvents: "auto" }} onMouseDown={onDragStart}>
          <rect x={labelX} y={by} width={labelW} height={badgeH}
            fill={`${color}18`} stroke={color} strokeWidth={1} rx={3} />
          <text x={labelX + PAD} y={y + 4} fontSize={9.5} fill={labelFill}
            fontFamily="Geist Variable, monospace" fontWeight="600"
            style={{ pointerEvents: "none" }}>
            {label}
          </text>
        </g>
      ) : (
        <g style={{ cursor: "grab", pointerEvents: "auto" }}
          onMouseDown={onDragStart}
          onDoubleClick={onDoubleClick}>
          <rect x={labelX} y={by} width={labelW} height={badgeH}
            fill={color} stroke={labelFill ?? color} strokeWidth={isEditing ? 1.5 : 1} rx={3} />
          <text x={labelX + PAD} y={y + 4} fontSize={9.5} fill={labelFill}
            fontFamily="Geist Variable, monospace" fontWeight="600"
            style={{ pointerEvents: "none" }}>
            {label}
          </text>
        </g>
      )}
      {/* Price tag on right axis */}
      <rect x={axisX} y={y - 9} width={axisPriceW} height={18}
        fill={priceTagColor} rx={2} style={{ pointerEvents: "none" }} />
      <text x={axisX + axisPriceW / 2} y={y + 4} textAnchor="middle" fontSize={9}
        fill={priceTagFg}
        fontFamily="Geist Variable, monospace" fontWeight="bold"
        style={{ pointerEvents: "none" }}>
        {priceTag}
      </text>
    </g>
  )
}

interface OrderLineProps {
  order: PlacedOrder
  orderPrice: number
  toY: (p: number) => number
  minPrice: number
  maxPrice: number
  padding: { left: number; right: number; top: number; bottom: number }
  width: number
  isEditing: boolean
  onClose: () => void
  onDragStart: (e: React.MouseEvent) => void
  onDoubleClick?: (e: React.MouseEvent) => void
  // Called once on mount so the drag handler can move the element imperatively
  registerImperativeMove?: (id: string, fn: (newY: number) => void) => void
}

function orderSideLabel(side: "buy" | "sell", marketType?: "spot" | "futures"): string {
  if (marketType === "futures") return side === "buy" ? "LONG" : "SHORT"
  return side === "buy" ? "BUY" : "SELL"
}

function getOrderColors(order: PlacedOrder, isEditing: boolean) {
  if (order.isDraft) {
    return {
      color: CHART_COLORS.draft,
      textColor: undefined as string | undefined,
      closeBtnColor: CHART_COLORS.draftClose,
      closeBtnFg: "rgba(200,214,229,0.9)",
      priceTagColor: "rgba(80,95,115,0.9)",
      priceTagFg: "rgba(200,214,229,0.9)",
      label: `${orderSideLabel(order.side, order.marketType)} | ${fmtQty(order.qty)} — draft`,
    }
  }
  const isBuy = order.side === "buy"
  const color = isEditing ? (isBuy ? "#236e52" : "#8a2030") : (isBuy ? "#1a7a5a" : "#7a1a1a")
  const textColor = isBuy ? "#00e5a0" : "#e06070"
  const gridSuffix = order.gridIndex != null ? ` #${order.gridIndex}` : ""
  return {
    color,
    textColor,
    closeBtnColor: color,
    closeBtnFg: textColor,
    priceTagColor: isBuy ? "#1a7a5a" : "#7a1a1a",
    priceTagFg: textColor,
    label: `${orderSideLabel(order.side, order.marketType)} | ${fmtQty(order.qty)}${gridSuffix}`,
  }
}

function OrderLine({ order, orderPrice, toY, minPrice, maxPrice, padding, width, isEditing, onClose, onDragStart, onDoubleClick, registerImperativeMove }: OrderLineProps) {
  const groupRef = useRef<SVGGElement>(null)
  const renderedYRef = useRef(toY(orderPrice))
  // Keep toY stable reference for imperative handler
  const toYRef = useRef(toY)
  toYRef.current = toY

  useEffect(() => {
    if (!registerImperativeMove) return
    // Handler receives price (not y) — convert imperatively via current toY
    registerImperativeMove(order.id, (newPrice: number) => {
      const el = groupRef.current
      if (!el) return
      const newY = toYRef.current(newPrice)
      const delta = newY - renderedYRef.current
      el.setAttribute("transform", `translate(0, ${delta})`)
    })
  }, [order.id, registerImperativeMove])

  // Must be declared before any conditional return to satisfy Rules of Hooks
  const isVisible = orderPrice >= minPrice && orderPrice <= maxPrice
  const y = isVisible ? toY(orderPrice) : 0
  // When React re-renders with the committed price, reset any imperative transform
  useEffect(() => {
    if (!isVisible) return
    if (groupRef.current) {
      groupRef.current.removeAttribute("transform")
    }
    renderedYRef.current = toY(orderPrice)
  })

  if (!isVisible) return null

  renderedYRef.current = y
  const axisX = width - padding.right
  const { color, textColor, closeBtnColor, closeBtnFg, priceTagColor, priceTagFg, label } = getOrderColors(order, isEditing)
  const PAD = 8
  const CLOSE_W = 20
  const labelW = PAD + label.length * 5.8 + PAD
  const badgeW = labelW + CLOSE_W
  const padLeft = padding.left

  if (order.side === "buy") {
    const badgeX = padLeft + 4
    return (
      <g ref={groupRef}>
        <line x1={padLeft} y1={y} x2={badgeX - 1} y2={y}
          stroke={color} strokeWidth={1} strokeDasharray="4,3" opacity={order.isDraft ? 0.5 : 0.85} />
        <line x1={badgeX + badgeW + 2} y1={y} x2={axisX - 1} y2={y}
          stroke={color} strokeWidth={1} strokeDasharray="4,3" opacity={order.isDraft ? 0.5 : 0.85} />
        <BuyOrderBadge
          y={y} label={label} color={color} textColor={textColor}
          closeBtnColor={closeBtnColor} closeBtnFg={closeBtnFg}
          priceTagColor={priceTagColor} priceTagFg={priceTagFg}
          priceTag={formatPrice(orderPrice)}
          onClose={onClose} onDragStart={onDragStart} onDoubleClick={onDoubleClick}
          axisX={axisX} padLeft={padLeft} isEditing={isEditing}
          isDraft={order.isDraft}
        />
      </g>
    )
  } else {
    const SELL_CLOSE_W = 20
    const sellLabelW = PAD + label.length * 5.8 + PAD
    const sellBadgeW = SELL_CLOSE_W + sellLabelW
    const badgeRight = axisX - 4
    const badgeLeft = badgeRight - sellBadgeW
    return (
      <g ref={groupRef}>
        <line x1={padLeft} y1={y} x2={badgeLeft - 2} y2={y}
          stroke={color} strokeWidth={1} strokeDasharray="4,3" opacity={order.isDraft ? 0.5 : 0.85} />
        <line x1={badgeRight + 2} y1={y} x2={axisX - 1} y2={y}
          stroke={color} strokeWidth={1} strokeDasharray="4,3" opacity={order.isDraft ? 0.5 : 0.85} />
        <SellOrderBadge
          y={y} label={label} color={color} textColor={textColor}
          closeBtnColor={closeBtnColor} closeBtnFg={closeBtnFg}
          priceTagColor={priceTagColor} priceTagFg={priceTagFg}
          priceTag={formatPrice(orderPrice)}
          onClose={onClose} onDragStart={onDragStart} onDoubleClick={onDoubleClick}
          axisX={axisX} isEditing={isEditing}
          isDraft={order.isDraft}
        />
      </g>
    )
  }
}

// Keep renderOrderLine as a thin wrapper for backward compat within OrdersOverlay
function renderOrderLine(
  order: PlacedOrder,
  orderPrice: number,
  toY: (p: number) => number,
  minPrice: number,
  maxPrice: number,
  padding: { left: number; right: number; top: number; bottom: number },
  width: number,
  onClose: () => void,
  onDragStart: (e: React.MouseEvent) => void,
  registerImperativeMove?: (id: string, fn: (newY: number) => void) => void,
  isEditing?: boolean,
  onDoubleClick?: (e: React.MouseEvent) => void,
) {
  return (
    <OrderLine
      key={order.id}
      order={order} orderPrice={orderPrice}
      toY={toY} minPrice={minPrice} maxPrice={maxPrice}
      padding={padding} width={width}
      isEditing={isEditing ?? false}
      onClose={onClose} onDragStart={onDragStart} onDoubleClick={onDoubleClick}
      registerImperativeMove={registerImperativeMove}
    />
  )
}

// ---- Position avg entry line + badge ----
function PositionLine({
  position,
  width,
  height,
  toY,
  minPrice,
  maxPrice,
  padding,
  onClose,
}: {
  position: LivePosition
  width: number
  height: number
  toY: (price: number) => number
  minPrice: number
  maxPrice: number
  padding: { left: number; right: number; top: number; bottom: number }
  onClose: () => void
}) {
  // Only show when there are real filled orders
  if (position.realSize <= 0 || position.avgEntry <= 0) return null

  // Breakeven = avgEntry adjusted for fees (currently 0%)
  const FEE_IN = 0
  const FEE_OUT = 0
  const breakeven = position.side === "long"
    ? position.avgEntry * (1 + FEE_IN + FEE_OUT)
    : position.avgEntry * (1 - FEE_IN - FEE_OUT)

  const price = breakeven
  const isOutOfRange = price < minPrice || price > maxPrice
  const chartTop = padding.top
  const chartBottom = toY(minPrice)
  const rawY = toY(price)
  const clampedY = isOutOfRange
    ? (price > maxPrice ? chartTop + 14 : chartBottom - 14)
    : rawY

  const isLong = position.side === "long"
  // LONG = green, SHORT = red — matching the badge color scheme
  const lineColor = isLong ? "#00e5a0" : "#ff4757"
  const badgeBorder = isLong ? "rgba(0,229,160,0.3)" : "rgba(255,71,87,0.3)"

  const pnl = position.unrealizedPnl
  const pnlPct = position.unrealizedPnlPct
  const isPnlPos = pnl >= 0
  const pnlColor = isPnlPos ? "#00e5a0" : "#ff4757"
  const priceStr = priceToString(price)
  const realSizeStr = position.realSize > 0 ? position.realSize.toFixed(4) : position.size.toFixed(4)

  // Badge: LONG → left side with extra offset, SHORT → right side with extra offset
  // Extra offset (16px) ensures preview/draft order badges don't hide under the position badge
  const BADGE_EXTRA_OFFSET = 32
  const badgeTop = clampedY

  return (
    <>
      {/* SVG line layer */}
      <svg
        style={{ position: "absolute", left: 0, top: 0, pointerEvents: "none", overflow: "visible" }}
        width={width}
        height={height}
      >
        {/* Dashed horizontal line across chart */}
        <line
          x1={padding.left}
          y1={clampedY}
          x2={width - padding.right}
          y2={clampedY}
          stroke={lineColor}
          strokeWidth={1}
          strokeDasharray="5,3"
          opacity={0.6}
        />
        {/* Price tag on right axis */}
        <g>
          {(() => {
            const charW = 5.8
            const PAD = 5
            const priceW = PAD + priceStr.length * charW + PAD
            const tagX = width - padding.right
            return (
              <>
                <rect x={tagX} y={clampedY - 9} width={priceW} height={18}
                  fill={lineColor} rx={2} />
                <text x={tagX + priceW / 2} y={clampedY + 4}
                  textAnchor="middle" fill="#000" fontSize={9}
                  fontFamily="'JetBrains Mono Variable', monospace" fontWeight={700}>
                  {priceStr}
                </text>
              </>
            )
          })()}
        </g>
      </svg>

      {/* HTML badge: LONG on left, SHORT on right */}
      <div
        style={{
          position: "absolute",
          ...(isLong
            ? { left: padding.left + BADGE_EXTRA_OFFSET }
            : { right: padding.right + BADGE_EXTRA_OFFSET }),
          top: badgeTop,
          transform: "translateY(-50%)",
          zIndex: 10,
          pointerEvents: "auto",
        }}
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div
          className="flex items-center font-mono"
          style={{
            background: "rgba(8,15,30,0.92)",
            border: `1px solid ${badgeBorder}`,
            backdropFilter: "blur(4px)",
            fontSize: 9,
            gap: 5,
            padding: "3px 6px",
            borderRadius: 4,
            whiteSpace: "nowrap",
          }}
        >
          {/* Side label */}
          <span style={{ color: lineColor, fontWeight: 700, letterSpacing: "0.05em" }}>
            {isLong ? "LONG" : "SHORT"}
          </span>
          {/* Separator */}
          <span style={{ color: "rgba(255,255,255,0.12)" }}>|</span>
          {/* Breakeven price */}
          <span style={{ color: "rgba(200,214,229,0.85)", fontWeight: 600 }}>
            {priceStr}
          </span>
          {/* Separator */}
          <span style={{ color: "rgba(255,255,255,0.12)" }}>|</span>
          {/* PnL */}
          <span style={{ color: pnlColor, fontWeight: 700 }}>
            {isPnlPos ? "+" : ""}${Math.abs(pnl).toFixed(2)}
          </span>
          <span style={{ color: pnlColor }}>
            {isPnlPos ? "+" : ""}{pnlPct.toFixed(2)}%
          </span>
          {/* Separator */}
          <span style={{ color: "rgba(255,255,255,0.12)" }}>|</span>
          {/* Size */}
          <span style={{ color: "rgba(200,214,229,0.6)" }}>{realSizeStr}</span>
          {/* Close button */}
          <button
            className="flex items-center justify-center rounded transition-colors"
            style={{
              width: 14, height: 14,
              color: "#ff4757",
              border: "1px solid rgba(255,71,87,0.35)",
              borderRadius: 3,
              fontSize: 10,
              lineHeight: 1,
              fontWeight: 700,
              paddingBottom: 1,
              marginLeft: 2,
              background: "transparent",
              cursor: "pointer",
            }}
            onClick={onClose}
            title="Close position"
          >
            ×
          </button>
        </div>
      </div>
    </>
  )
}

interface ChartProps {
  candles: Candle[]
  width: number
  height: number
  allOrders: PlacedOrder[]
  editingOrderId: string | null
  onOrderClose: (id: string) => void
  onOrderDragStart: (id: string, e: React.MouseEvent, toPrice: (y: number) => number, minP: number, maxP: number, chartH: number, padTop: number) => void
  onOrderDoubleClick?: (id: string, e: React.MouseEvent) => void
  onBackgroundClick?: () => void
  dragHandlers: React.MutableRefObject<Map<string, (p: number) => void>>
  previewOrdersList?: ChartGridPreview[]
  gridOrdersList?: ChartGridOrders[]
  onGridOrderDragStart?: GridOrdersOverlayProps["onGridOrderDragStart"]
  onGridTpSlDragStart?: GridOrdersOverlayProps["onGridTpSlDragStart"]
  onGridClose?: GridOrdersOverlayProps["onGridClose"]
  onGridEntryClose?: GridOrdersOverlayProps["onGridEntryClose"]
  onPreviewOrderDragStart?: GridPreviewOverlayProps["onOrderDragStart"]
  onPreviewGridTpSlDragStart?: GridPreviewOverlayProps["onGridTpSlDragStart"]
  onPreviewClose?: GridPreviewOverlayProps["onClose"]
  onPreviewEntryClose?: GridPreviewOverlayProps["onEntryClose"]
  onPreviewTpSlClose?: GridPreviewOverlayProps["onTpSlClose"]
  tpSl?: ChartTpSl | null
  tpSlSide?: "long" | "short"
  onTpSlDragStart?: PlacedTpSlOverlayProps["onDragStart"]
  onTpSlClose?: PlacedTpSlOverlayProps["onClose"]
  activePosition?: LivePosition | null
  onClosePosition?: () => void
}

interface OrdersOverlayProps {
  allOrders: PlacedOrder[]
  editingOrderId: string | null
  width: number
  height: number
  toY: (price: number) => number
  toPrice: (y: number) => number
  minPrice: number
  maxPrice: number
  chartHeight: number
  padTop: number
  padding: { left: number; right: number; top: number; bottom: number }
  onOrderClose: (id: string) => void
  onOrderDragStart: (id: string, e: React.MouseEvent, toPrice: (y: number) => number, minP: number, maxP: number, chartH: number, padTop: number) => void
  onOrderDoubleClick?: (id: string, e: React.MouseEvent) => void
  // Shared map: ChartWidget registers imperative move handlers here; OrderLine writes to it
  dragHandlers: React.MutableRefObject<Map<string, (p: number) => void>>
}

function OrdersOverlay({ allOrders, editingOrderId, width, height, toY, toPrice, minPrice, maxPrice, chartHeight, padTop, padding, onOrderClose, onOrderDragStart, onOrderDoubleClick, dragHandlers }: OrdersOverlayProps) {
  const registerImperativeMove = useCallback((id: string, fn: (newY: number) => void) => {
    dragHandlers.current.set(id, fn)
  }, [dragHandlers])

  if (!allOrders.length) return null
  return (
    <svg width={width} height={height} style={{ position: "absolute", inset: 0, overflow: "visible", pointerEvents: "none" }}>
      {allOrders.map((order) => {
        const price = order.orderType === "market" ? maxPrice : order.price
        return renderOrderLine(
          order, price, toY, minPrice, maxPrice, padding, width,
          () => onOrderClose(order.id),
          (e) => onOrderDragStart(order.id, e, toPrice, minPrice, maxPrice, chartHeight, padTop),
          registerImperativeMove,
          editingOrderId === order.id,
          onOrderDoubleClick ? (e) => onOrderDoubleClick(order.id, e) : undefined,
        )
      })}
    </svg>
  )
}

// ─── Grid Preview Overlay — dashed visual-only lines, not yet placed ─────────

interface GridPreviewOverlayProps {
  previewOrdersList: ChartGridPreview[]
  width: number
  height: number
  toY: (price: number) => number
  toPrice: (yPx: number) => number
  minPrice: number
  maxPrice: number
  padding: { left: number; right: number; top: number; bottom: number }
  dragHandlers: React.MutableRefObject<Map<string, (p: number) => void>>
  onOrderDragStart?: (consoleId: string, orderId: string, e: React.MouseEvent, toPrice: (y: number) => number, minP: number, maxP: number, chartH: number, padTop: number) => void
  onGridTpSlDragStart?: (consoleId: string, target: "tp" | "sl", tpIndex: number, e: React.MouseEvent, minP: number, maxP: number, chartH: number) => void
  onClose?: (consoleId: string) => void
  onEntryClose?: (consoleId: string, orderId: string) => void
  onTpSlClose?: (consoleId: string, target: "tp" | "sl", tpIndex?: number) => void
}

function GridPreviewOverlay({
  previewOrdersList, width, height, toY, toPrice, minPrice, maxPrice, padding, dragHandlers, onOrderDragStart, onGridTpSlDragStart, onEntryClose, onTpSlClose,
}: GridPreviewOverlayProps) {
  if (!previewOrdersList.length) return null
  return (
    <svg width={width} height={height} style={{ position: "absolute", inset: 0, overflow: "visible" }}>
      {previewOrdersList.map((preview) => {
        const isLong = preview.side === "long"
        const chartH = height - padding.top - padding.bottom
        return (
          <g key={preview.consoleId}>
            {preview.orders.map((o, idx) => {
              const isOrderSource = preview.source === "order"
              const entryLabel = isOrderSource
                ? `${orderSideLabel(isLong ? "buy" : "sell", preview.marketType)} | ${fmtQty(o.qty)} — draft`
                : `${orderSideLabel(isLong ? "buy" : "sell", preview.marketType)} | ${fmtQty(o.qty)} #${idx + 1} — draft`
              return (
                <GridOrderLine
                  key={o.id}
                  id={`preview:${preview.consoleId}:${o.id}`}
                  price={o.price}
                  label={entryLabel}
                  side={preview.side}
                  toY={toY} minPrice={minPrice} maxPrice={maxPrice}
                  width={width} padding={padding}
                  isDraft={true} {...DRAFT_COLORS}
                  onClose={() => onEntryClose?.(preview.consoleId, o.id)}
                  onDragStart={(e) => onOrderDragStart?.(preview.consoleId, o.id, e, toPrice, minPrice, maxPrice, chartH, padding.top)}
                  registerMove={(id, fn) => { dragHandlers.current.set(id, fn) }}
                />
              )
            })}
            {preview.tpLevels.map((tp, idx) => {
              const totalTp = preview.tpLevels.length
              const edgeOffset = isLong ? totalTp - 1 - idx : idx
              return (
                <GridOrderLine
                  key={`tp${idx + 1}`}
                  id={`preview:${preview.consoleId}:tp${idx === 0 ? "" : idx + 1}`}
                  price={tp}
                  label={`TP ${idx + 1} — draft`}
                  side={preview.side}
                  toY={toY} minPrice={minPrice} maxPrice={maxPrice}
                  width={width} padding={padding}
                  isDraft={true} clampToEdge edgeOffset={edgeOffset}
                  {...DRAFT_COLORS}
                  onClose={() => onTpSlClose?.(preview.consoleId, "tp", idx)}
                  onDragStart={(e) => onGridTpSlDragStart?.(preview.consoleId, "tp", idx, e, minPrice, maxPrice, chartH)}
                  registerMove={(id, fn) => { dragHandlers.current.set(id, fn) }}
                />
              )
            })}
            {preview.slPrice !== null && (
              <GridOrderLine
                id={`preview:${preview.consoleId}:sl`}
                price={preview.slPrice}
                label="SL — draft"
                side={preview.side}
                toY={toY} minPrice={minPrice} maxPrice={maxPrice}
                width={width} padding={padding}
                isDraft={true} clampToEdge
                {...DRAFT_COLORS}
                onClose={() => onTpSlClose?.(preview.consoleId, "sl")}
                onDragStart={(e) => onGridTpSlDragStart?.(preview.consoleId, "sl", 0, e, minPrice, maxPrice, chartH)}
                registerMove={(id, fn) => { dragHandlers.current.set(id, fn) }}
              />
            )}
          </g>
        )
      })}
    </svg>
  )
}

// ─── Grid Orders Overlay ──────────────────────────────────────────────────────
// Uses BuyOrderBadge / SellOrderBadge directly — identical style to single orders.

interface GridOrdersOverlayProps {
  gridOrdersList: ChartGridOrders[]
  width: number
  height: number
  toY: (price: number) => number
  toPrice: (yPx: number) => number
  minPrice: number
  maxPrice: number
  padding: { left: number; right: number; top: number; bottom: number }
  dragHandlers: React.MutableRefObject<Map<string, (p: number) => void>>
  onGridOrderDragStart?: (consoleId: string, orderId: string, e: React.MouseEvent, toPrice: (y: number) => number, minP: number, maxP: number, chartH: number, padTop: number) => void
  onGridTpSlDragStart?: (consoleId: string, target: "tp" | "sl", tpIndex: number, e: React.MouseEvent, minP: number, maxP: number, chartH: number) => void
  onGridClose?: (consoleId: string, target: "tp" | "sl", tpIndex?: number) => void
  onGridEntryClose?: (consoleId: string, orderId: string) => void
}

// Single grid line rendered through BuyOrderBadge — identical style to single orders.
// When clampToEdge=true the line is always shown even if price is outside visible range
// (needed for TP above maxPrice / SL below minPrice).
function GridOrderLine({
  id, price, label, side, toY, minPrice, maxPrice, width, padding,
  isDraft, clampToEdge, edgeOffset,
  color, textColor, closeBtnColor, closeBtnFg, priceTagColor, priceTagFg,
  onClose, onDragStart, registerMove,
}: {
  id: string; price: number; label: string; side: "long" | "short"
  toY: (p: number) => number; minPrice: number; maxPrice: number
  width: number; padding: { left: number; right: number; top: number; bottom: number }
  isDraft: boolean; clampToEdge?: boolean; edgeOffset?: number
  color: string; textColor?: string
  closeBtnColor: string; closeBtnFg: string
  priceTagColor: string; priceTagFg: string
  onClose?: () => void
  onDragStart?: (e: React.MouseEvent) => void
  registerMove?: (id: string, fn: (p: number) => void) => void
}) {
  const groupRef = useRef<SVGGElement>(null)
  const renderedYRef = useRef(toY(price))
  const toYRef = useRef(toY)
  toYRef.current = toY
  const isDraggingThisRef = useRef(false)

  useEffect(() => {
    if (!registerMove) return
    registerMove(id, (newPrice: number) => {
      const el = groupRef.current
      if (!el) return
      isDraggingThisRef.current = true
      const newY = toYRef.current(newPrice)
      const delta = newY - renderedYRef.current
      el.setAttribute("transform", `translate(0, ${delta})`)
    })
  }, [id, registerMove])

  useEffect(() => {
    // Don't reset transform while drag is visually active — the line is being dragged
    if (isDraggingThisRef.current) {
      isDraggingThisRef.current = false
      renderedYRef.current = toY(price)
      return
    }
    if (groupRef.current) groupRef.current.removeAttribute("transform")
    renderedYRef.current = toY(price)
  })

  const outOfRange = price < minPrice || price > maxPrice
  if (outOfRange && !clampToEdge) return null

  // When out of range and clampToEdge, snap badge to top/bottom edge of chart area
  const chartTop = padding.top
  const chartBottom = toY(minPrice)
  const rawY = toY(price)
  const stackOffset = (edgeOffset ?? 0) * 22
  // Above chart (price > maxPrice): TP with higher price (larger edgeOffset) is closer
  // to the top edge. So offset pushes downward from the edge (positive y delta).
  // Below chart: offset pushes upward from the bottom edge.
  const y = outOfRange
    ? (price > maxPrice ? chartTop + 2 + stackOffset : chartBottom - 2 - stackOffset)
    : rawY
  renderedYRef.current = rawY

  const axisX = width - padding.right
  const PAD = 8
  const CLOSE_W = 20
  const charW = 5.8
  const labelW = PAD + label.length * charW + PAD
  const badgeW = labelW + CLOSE_W
  const badgeX = padding.left + 4
  const opacity = isDraft ? 0.55 : 0.85

  const isShort = side === "short"

  // For Short: badge anchors right (before price axis), lines fill left side
  const PAD_SELL = 8
  const CLOSE_W_SELL = 20
  const charW_SELL = 5.8
  const labelW_SELL = PAD_SELL + label.length * charW_SELL + PAD_SELL
  const badgeW_SELL = labelW_SELL + CLOSE_W_SELL
  const badgeRightEdge = axisX - 4  // right edge of sell badge

  return (
    <g ref={groupRef} opacity={opacity} style={{ pointerEvents: "auto" }}>
      {isShort ? (
        <>
          <line x1={padding.left} y1={y} x2={badgeRightEdge - badgeW_SELL - 1} y2={y}
            stroke={color} strokeWidth={1} strokeDasharray={isDraft ? "4,3" : undefined} />
          <line x1={badgeRightEdge + 2} y1={y} x2={axisX - 1} y2={y}
            stroke={color} strokeWidth={1} strokeDasharray={isDraft ? "4,3" : undefined} />
          <SellOrderBadge
            y={y} label={label}
            color={color} textColor={textColor}
            closeBtnColor={closeBtnColor} closeBtnFg={closeBtnFg}
            priceTagColor={priceTagColor} priceTagFg={priceTagFg}
            priceTag={formatPrice(price)}
            onClose={onClose}
            onDragStart={onDragStart ?? (() => {})}
            axisX={axisX}
            isEditing={false}
            isDraft={isDraft}
          />
        </>
      ) : (
        <>
          <line x1={padding.left} y1={y} x2={badgeX - 1} y2={y}
            stroke={color} strokeWidth={1} strokeDasharray={isDraft ? "4,3" : undefined} />
          <line x1={badgeX + badgeW + 2} y1={y} x2={axisX - 1} y2={y}
            stroke={color} strokeWidth={1} strokeDasharray={isDraft ? "4,3" : undefined} />
          <BuyOrderBadge
            y={y} label={label}
            color={color} textColor={textColor}
            closeBtnColor={closeBtnColor} closeBtnFg={closeBtnFg}
            priceTagColor={priceTagColor} priceTagFg={priceTagFg}
            priceTag={formatPrice(price)}
            onClose={onClose}
            onDragStart={onDragStart ?? (() => {})}
            axisX={axisX} padLeft={padding.left}
            isEditing={false}
            isDraft={isDraft}
          />
        </>
      )}
    </g>
  )
}

// Draft (grey) color palette — same values as getOrderColors with isDraft=true
const DRAFT_COLORS = {
  color: CHART_COLORS.draft,
  textColor: undefined as string | undefined,
  closeBtnColor: CHART_COLORS.draftClose,
  closeBtnFg: "rgba(200,214,229,0.9)",
  priceTagColor: "rgba(80,95,115,0.9)",
  priceTagFg: "rgba(200,214,229,0.9)",
}

// Placed long entry (green) — same as getOrderColors for buy+placed
const LONG_ENTRY_COLORS = {
  color: "#1a7a5a",
  textColor: "#00e5a0",
  closeBtnColor: "#1a7a5a",
  closeBtnFg: "#00e5a0",
  priceTagColor: "#1a7a5a",
  priceTagFg: "#00e5a0",
}

// Placed short entry (red)
const SHORT_ENTRY_COLORS = {
  color: "#7a1a1a",
  textColor: "#e06070",
  closeBtnColor: "#7a1a1a",
  closeBtnFg: "#e06070",
  priceTagColor: "#7a1a1a",
  priceTagFg: "#e06070",
}

// TP for long = red side (sell above)
const LONG_TP_COLORS = {
  color: "#7a1a1a",
  textColor: "#e06070",
  closeBtnColor: "#7a1a1a",
  closeBtnFg: "#e06070",
  priceTagColor: "#7a1a1a",
  priceTagFg: "#e06070",
}

// TP for short = green side (buy below)
const SHORT_TP_COLORS = {
  color: "#1a7a5a",
  textColor: "#00e5a0",
  closeBtnColor: "#1a7a5a",
  closeBtnFg: "#00e5a0",
  priceTagColor: "#1a7a5a",
  priceTagFg: "#00e5a0",
}

// SL always orange
const SL_COLORS = {
  color: "#8a4800",
  textColor: "#ffaa44",
  closeBtnColor: "#8a4800",
  closeBtnFg: "#ffaa44",
  priceTagColor: "#8a4800",
  priceTagFg: "#ffaa44",
}

// ── Placed TP/SL overlay — uses GridOrderLine (matches grid style) ────────────

interface PlacedTpSlOverlayProps {
  tpSl: ChartTpSl
  side: "long" | "short"
  width: number
  height: number
  toY: (price: number) => number
  minPrice: number
  maxPrice: number
  padding: { left: number; right: number; top: number; bottom: number }
  dragHandlers: React.MutableRefObject<Map<string, (p: number) => void>>
  onDragStart?: (key: "tp" | "sl", e: React.MouseEvent, minP: number, maxP: number, chartH: number, padTop: number, tpIndex?: number) => void
  onClose: (key: "tp" | "sl", tpIndex?: number) => void
}

function PlacedTpSlOverlay({ tpSl, side, width, height, toY, minPrice, maxPrice, padding, dragHandlers, onDragStart, onClose }: PlacedTpSlOverlayProps) {
  const chartH = height - padding.top - padding.bottom
  const tpColors = side === "long" ? LONG_TP_COLORS : SHORT_TP_COLORS

  const tpLevels = tpSl.tpLevels && tpSl.tpLevels.length > 0
    ? tpSl.tpLevels
    : tpSl.tp !== null ? [tpSl.tp] : []

  return (
    <svg width={width} height={height} style={{ position: "absolute", inset: 0, overflow: "visible", pointerEvents: "none" }}>
      {tpLevels.map((price, idx) => {
        const totalTp = tpLevels.length
        const edgeOffset = side === "long" ? totalTp - 1 - idx : idx
        const label = `TP ${idx + 1}`
        return (
          <GridOrderLine
            key={`placed-tp${idx}`}
            id={`placed-tp${idx}`}
            price={price}
            label={label}
            side={side}
            toY={toY} minPrice={minPrice} maxPrice={maxPrice}
            width={width} padding={padding}
            isDraft={false} clampToEdge edgeOffset={edgeOffset}
            {...tpColors}
            onClose={() => onClose("tp", idx)}
            onDragStart={(e) => onDragStart?.("tp", e, minPrice, maxPrice, chartH, padding.top, idx)}
            registerMove={(id, fn) => { dragHandlers.current.set(id, fn) }}
          />
        )
      })}
      {tpSl.sl !== null && (
        <GridOrderLine
          id="placed-sl"
          price={tpSl.sl}
          label="STOP LOSS"
          side={side}
          toY={toY} minPrice={minPrice} maxPrice={maxPrice}
          width={width} padding={padding}
          isDraft={false} clampToEdge
          {...SL_COLORS}
          onClose={() => onClose("sl")}
          onDragStart={(e) => onDragStart?.("sl", e, minPrice, maxPrice, chartH, padding.top)}
          registerMove={(id, fn) => { dragHandlers.current.set(id, fn) }}
        />
      )}
    </svg>
  )
}

function GridOrdersOverlay({
  gridOrdersList, width, height, toY, toPrice, minPrice, maxPrice, padding, dragHandlers, onGridOrderDragStart, onGridTpSlDragStart, onGridClose, onGridEntryClose,
}: GridOrdersOverlayProps) {
  if (!gridOrdersList.length) return null

  return (
    <svg width={width} height={height} style={{ position: "absolute", inset: 0, overflow: "visible" }}>
      {gridOrdersList.map((grid) => {
        const isLong = grid.side === "long"
        const chartH = height - padding.top - padding.bottom
        const entryColors = isLong ? LONG_ENTRY_COLORS : SHORT_ENTRY_COLORS
        const tpColors = isLong ? LONG_TP_COLORS : SHORT_TP_COLORS

        return (
          <g key={grid.consoleId}>
            {grid.orders.map((o) => (
              <GridOrderLine
                key={o.id}
                id={`grid:${grid.consoleId}:${o.id}`}
                price={o.price}
                label={`${orderSideLabel(isLong ? "buy" : "sell", grid.marketType)} | ${fmtQty(o.qty)} #${o.gridIndex}`}
                side={grid.side}
                toY={toY} minPrice={minPrice} maxPrice={maxPrice}
                width={width} padding={padding}
                isDraft={false} {...entryColors}
                onClose={() => onGridEntryClose?.(grid.consoleId, o.id)}
                onDragStart={(e) => onGridOrderDragStart?.(grid.consoleId, o.id, e, toPrice, minPrice, maxPrice, chartH, padding.top)}
                registerMove={(id, fn) => { dragHandlers.current.set(id, fn) }}
              />
            ))}
            {grid.tpLevels.map((tp, idx) => {
              const totalTp = grid.tpLevels.length
              const edgeOffset = isLong ? totalTp - 1 - idx : idx
              return (
                <GridOrderLine
                  key={`tp${idx + 1}`}
                  id={`grid:${grid.consoleId}:tp${idx === 0 ? "" : idx + 1}`}
                  price={tp}
                  label={`TP ${idx + 1}`}
                  side={grid.side}
                  toY={toY} minPrice={minPrice} maxPrice={maxPrice}
                  width={width} padding={padding}
                  isDraft={false} clampToEdge edgeOffset={edgeOffset}
                  {...tpColors}
                  onClose={() => onGridClose?.(grid.consoleId, "tp", idx)}
                  onDragStart={(e) => onGridTpSlDragStart?.(grid.consoleId, "tp", idx, e, minPrice, maxPrice, chartH)}
                  registerMove={(id, fn) => { dragHandlers.current.set(id, fn) }}
                />
              )
            })}
            {grid.slPrice !== null && (
              <GridOrderLine
                id={`grid:${grid.consoleId}:sl`}
                price={grid.slPrice}
                label="STOP LOSS"
                side={grid.side}
                toY={toY} minPrice={minPrice} maxPrice={maxPrice}
                width={width} padding={padding}
                isDraft={false} clampToEdge
                {...SL_COLORS}
                onClose={() => onGridClose?.(grid.consoleId, "sl")}
                onDragStart={(e) => onGridTpSlDragStart?.(grid.consoleId, "sl", 0, e, minPrice, maxPrice, chartH)}
                registerMove={(id, fn) => { dragHandlers.current.set(id, fn) }}
              />
            )}
          </g>
        )
      })}
    </svg>
  )
}

const CandlestickChartBody = React.memo(function CandlestickChartBody({ candles, width, height, onBackgroundClick }: {
  candles: Candle[]; width: number; height: number; onBackgroundClick?: () => void
}) {
  const chartHeight = height * 0.72
  const volumeHeight = height * 0.18
  const padding = { left: 52, right: 56, top: 10, bottom: 20 }
  const chartAreaWidth = width - padding.left - padding.right
  const displayCount = Math.min(candles.length, Math.floor(chartAreaWidth / 8))
  const visible = candles.slice(-displayCount)

  const maxPrice = Math.max(...visible.map((c) => c.high))
  const minPrice = Math.min(...visible.map((c) => c.low))
  const priceRange = maxPrice - minPrice || 1
  const maxVol = Math.max(...visible.map((c) => c.volume)) || 1

  const toY = (price: number) => padding.top + ((maxPrice - price) / priceRange) * chartHeight
  const candleW = Math.max(2, chartAreaWidth / displayCount - 1)

  const priceLabels: Array<{ price: number; y: number }> = []
  for (let i = 0; i <= 5; i++) {
    const price = minPrice + (priceRange * i) / 5
    priceLabels.push({ price, y: toY(price) })
  }

  return (
    <svg width={width} height={height} style={{ display: "block" }}
      onClick={(e) => {
        // If the click target is the SVG itself (background), cancel edit mode
        if (e.target === e.currentTarget) onBackgroundClick?.()
      }}>
      {/* Transparent background rect to catch clicks */}
      <rect x={0} y={0} width={width} height={height} fill="transparent"
        onClick={() => onBackgroundClick?.()} />
      {priceLabels.map(({ y }, i) => (
        <line key={i} x1={padding.left} y1={y} x2={width - padding.right} y2={y}
          stroke={CHART_COLORS.grid} strokeWidth={1} />
      ))}
      {priceLabels.map(({ price, y }, i) => (
        <text key={i} x={padding.left - 4} y={y + 4} textAnchor="end"
          fontSize={9} fill={CHART_COLORS.text} fontFamily="Geist Variable, monospace">
          {formatPrice(price)}
        </text>
      ))}

      {visible.map((candle, i) => {
        const cx = padding.left + i * (chartAreaWidth / displayCount) + candleW / 2
        const isUp = candle.close >= candle.open
        const color = isUp ? CHART_COLORS.up : CHART_COLORS.down
        const bodyTop = toY(Math.max(candle.open, candle.close))
        const bodyBot = toY(Math.min(candle.open, candle.close))
        const bodyH = Math.max(1, bodyBot - bodyTop)
        const volH = (candle.volume / maxVol) * volumeHeight
        const volY = padding.top + chartHeight + (height - padding.top - chartHeight - padding.bottom) * 0.1 + (volumeHeight - volH)
        return (
          <g key={candle.time}>
            <line x1={cx} y1={toY(candle.high)} x2={cx} y2={toY(candle.low)} stroke={color} strokeWidth={1} />
            <rect x={cx - candleW / 2} y={bodyTop} width={candleW} height={bodyH} fill={color} />
            <rect x={cx - candleW / 2} y={volY} width={candleW} height={volH}
              fill={isUp ? CHART_COLORS.volume.up : CHART_COLORS.volume.down} />
          </g>
        )
      })}

      {(() => {
        const last = visible[visible.length - 1]
        if (!last) return null
        const y = toY(last.close)
        const color = last.close >= last.open ? CHART_COLORS.up : CHART_COLORS.down
        return (
          <g>
            <line x1={padding.left} y1={y} x2={width - padding.right} y2={y}
              stroke={color} strokeWidth={1} strokeDasharray="3,3" opacity={0.6} />
            <rect x={width - padding.right} y={y - 9} width={padding.right} height={18} fill={color} rx={2} />
            <text x={width - padding.right + padding.right / 2} y={y + 4} textAnchor="middle" fontSize={9}
              fill="#000" fontFamily="Geist Variable, monospace" fontWeight="bold">
              {formatPrice(last.close)}
            </text>
          </g>
        )
      })()}

    </svg>
  )
})

function CandlestickChart({ candles, width, height, allOrders, editingOrderId, onOrderClose, onOrderDragStart, onOrderDoubleClick, onBackgroundClick, dragHandlers, previewOrdersList, gridOrdersList, onGridOrderDragStart, onGridTpSlDragStart, onGridClose, onGridEntryClose, onPreviewOrderDragStart, onPreviewGridTpSlDragStart, onPreviewClose, onPreviewEntryClose, onPreviewTpSlClose, tpSl, tpSlSide, onTpSlDragStart, onTpSlClose, activePosition, onClosePosition }: ChartProps) {
  if (!candles.length || width < 2 || height < 2) return null
  const chartHeight = height * 0.72
  const padding = { left: 52, right: 56, top: 10, bottom: 20 }
  const chartAreaWidth = width - padding.left - padding.right
  const displayCount = Math.min(candles.length, Math.floor(chartAreaWidth / 8))
  const visible = candles.slice(-displayCount)
  const maxPrice = Math.max(...visible.map((c) => c.high))
  const minPrice = Math.min(...visible.map((c) => c.low))
  const priceRange = maxPrice - minPrice || 1
  const toY = (price: number) => padding.top + ((maxPrice - price) / priceRange) * chartHeight
  const toPrice = (yPx: number) => minPrice + (1 - (yPx - padding.top) / chartHeight) * priceRange
  return (
    <div style={{ position: "relative", width, height }}>
      <CandlestickChartBody candles={candles} width={width} height={height} onBackgroundClick={onBackgroundClick} />
      {activePosition && (
        <PositionLine
          position={activePosition}
          width={width} height={height}
          toY={toY} minPrice={minPrice} maxPrice={maxPrice}
          padding={padding}
          onClose={onClosePosition ?? (() => {})}
        />
      )}
      {gridOrdersList && gridOrdersList.length > 0 && (
        <GridOrdersOverlay
          gridOrdersList={gridOrdersList}
          width={width} height={height}
          toY={toY} toPrice={toPrice}
          minPrice={minPrice} maxPrice={maxPrice}
          padding={padding}
          dragHandlers={dragHandlers}
          onGridOrderDragStart={onGridOrderDragStart}
          onGridTpSlDragStart={onGridTpSlDragStart}
          onGridClose={onGridClose}
          onGridEntryClose={onGridEntryClose}
        />
      )}
      <OrdersOverlay
        allOrders={allOrders} editingOrderId={editingOrderId}
        width={width} height={height}
        toY={toY} toPrice={toPrice}
        minPrice={minPrice} maxPrice={maxPrice}
        chartHeight={chartHeight} padTop={padding.top}
        padding={padding}
        onOrderClose={onOrderClose} onOrderDragStart={onOrderDragStart} onOrderDoubleClick={onOrderDoubleClick}
        dragHandlers={dragHandlers}
      />
      {previewOrdersList && previewOrdersList.length > 0 && (
        <GridPreviewOverlay
          previewOrdersList={previewOrdersList}
          width={width} height={height}
          toY={toY} toPrice={toPrice}
          minPrice={minPrice} maxPrice={maxPrice}
          padding={padding}
          dragHandlers={dragHandlers}
          onOrderDragStart={onPreviewOrderDragStart}
          onGridTpSlDragStart={onPreviewGridTpSlDragStart}
          onClose={onPreviewClose}
          onEntryClose={onPreviewEntryClose}
          onTpSlClose={onPreviewTpSlClose}
        />
      )}
      {tpSl && onTpSlClose && (tpSl.tp !== null || tpSl.sl !== null || (tpSl.tpLevels && tpSl.tpLevels.length > 0)) && (
        <PlacedTpSlOverlay
          tpSl={tpSl} side={tpSlSide ?? "long"} width={width} height={height}
          toY={toY} minPrice={minPrice} maxPrice={maxPrice}
          padding={padding} dragHandlers={dragHandlers}
          onDragStart={onTpSlDragStart} onClose={onTpSlClose}
        />
      )}
    </div>
  )
}

const LineChartBody = React.memo(function LineChartBody({ candles, width, height, onBackgroundClick }: {
  candles: Candle[]; width: number; height: number; onBackgroundClick?: () => void
}) {
  const padding = { left: 52, right: 56, top: 10, bottom: 20 }
  const chartAreaWidth = width - padding.left - padding.right
  const chartHeight = height - padding.top - padding.bottom

  const prices = candles.map((c) => c.close)
  const maxPrice = Math.max(...prices)
  const minPrice = Math.min(...prices)
  const priceRange = maxPrice - minPrice || 1

  const toX = (i: number) => padding.left + (i / (candles.length - 1)) * chartAreaWidth
  const toY = (price: number) => padding.top + ((maxPrice - price) / priceRange) * chartHeight

  const points = candles.map((c, i) => `${toX(i)},${toY(c.close)}`).join(" ")
  const areaPoints = [
    `${padding.left},${padding.top + chartHeight}`,
    ...candles.map((c, i) => `${toX(i)},${toY(c.close)}`),
    `${padding.left + chartAreaWidth},${padding.top + chartHeight}`,
  ].join(" ")

  const priceLabels: Array<{ price: number; y: number }> = []
  for (let i = 0; i <= 5; i++) {
    const price = minPrice + (priceRange * i) / 5
    priceLabels.push({ price, y: toY(price) })
  }

  const last = candles[candles.length - 1]
  const isUp = last ? last.close >= candles[0].close : true

  return (
    <svg width={width} height={height} style={{ display: "block" }}>
      <rect x={0} y={0} width={width} height={height} fill="transparent"
        onClick={() => onBackgroundClick?.()} />
      <defs>
        <linearGradient id="lineGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={isUp ? CHART_COLORS.up : CHART_COLORS.down} stopOpacity={0.25} />
          <stop offset="100%" stopColor={isUp ? CHART_COLORS.up : CHART_COLORS.down} stopOpacity={0} />
        </linearGradient>
      </defs>

      {priceLabels.map(({ y, price }, i) => (
        <g key={i}>
          <line x1={padding.left} y1={y} x2={width - padding.right} y2={y}
            stroke={CHART_COLORS.grid} strokeWidth={1} />
          <text x={padding.left - 4} y={y + 4} textAnchor="end"
            fontSize={9} fill={CHART_COLORS.text} fontFamily="Geist Variable, monospace">
            {formatPrice(price)}
          </text>
        </g>
      ))}

      <polygon points={areaPoints} fill="url(#lineGrad)" />
      <polyline points={points} fill="none"
        stroke={isUp ? CHART_COLORS.up : CHART_COLORS.down} strokeWidth={1.5} />

      {last && (() => {
        const y = toY(last.close)
        const color = isUp ? CHART_COLORS.up : CHART_COLORS.down
        return (
          <line x1={padding.left} y1={y} x2={width - padding.right} y2={y}
            stroke={color} strokeWidth={1} strokeDasharray="3,3" opacity={0.5} />
        )
      })()}
    </svg>
  )
})

function LineChart({ candles, width, height, allOrders, editingOrderId, onOrderClose, onOrderDragStart, onOrderDoubleClick, onBackgroundClick, dragHandlers, previewOrdersList, gridOrdersList, onGridOrderDragStart, onGridTpSlDragStart, onGridClose, onGridEntryClose, onPreviewOrderDragStart, onPreviewGridTpSlDragStart, onPreviewClose, onPreviewEntryClose, onPreviewTpSlClose, tpSl, tpSlSide, onTpSlDragStart, onTpSlClose, activePosition, onClosePosition }: ChartProps) {
  if (!candles.length || width < 2 || height < 2) return null
  const padding = { left: 52, right: 56, top: 10, bottom: 20 }
  const chartHeight = height - padding.top - padding.bottom
  const prices = candles.map((c) => c.close)
  const maxPrice = Math.max(...prices)
  const minPrice = Math.min(...prices)
  const priceRange = maxPrice - minPrice || 1
  const toY = (price: number) => padding.top + ((maxPrice - price) / priceRange) * chartHeight
  const toPrice = (yPx: number) => minPrice + (1 - (yPx - padding.top) / chartHeight) * priceRange
  return (
    <div style={{ position: "relative", width, height }}>
      <LineChartBody candles={candles} width={width} height={height} onBackgroundClick={onBackgroundClick} />
      {activePosition && (
        <PositionLine
          position={activePosition}
          width={width} height={height}
          toY={toY} minPrice={minPrice} maxPrice={maxPrice}
          padding={padding}
          onClose={onClosePosition ?? (() => {})}
        />
      )}
      {gridOrdersList && gridOrdersList.length > 0 && (
        <GridOrdersOverlay
          gridOrdersList={gridOrdersList}
          width={width} height={height}
          toY={toY} toPrice={toPrice}
          minPrice={minPrice} maxPrice={maxPrice}
          padding={padding}
          dragHandlers={dragHandlers}
          onGridOrderDragStart={onGridOrderDragStart}
          onGridTpSlDragStart={onGridTpSlDragStart}
          onGridClose={onGridClose}
          onGridEntryClose={onGridEntryClose}
        />
      )}
      <OrdersOverlay
        allOrders={allOrders} editingOrderId={editingOrderId}
        width={width} height={height}
        toY={toY} toPrice={toPrice}
        minPrice={minPrice} maxPrice={maxPrice}
        chartHeight={chartHeight} padTop={padding.top}
        padding={padding}
        onOrderClose={onOrderClose} onOrderDragStart={onOrderDragStart} onOrderDoubleClick={onOrderDoubleClick}
        dragHandlers={dragHandlers}
      />
      {previewOrdersList && previewOrdersList.length > 0 && (
        <GridPreviewOverlay
          previewOrdersList={previewOrdersList}
          width={width} height={height}
          toY={toY} toPrice={toPrice}
          minPrice={minPrice} maxPrice={maxPrice}
          padding={padding}
          dragHandlers={dragHandlers}
          onOrderDragStart={onPreviewOrderDragStart}
          onGridTpSlDragStart={onPreviewGridTpSlDragStart}
          onClose={onPreviewClose}
          onEntryClose={onPreviewEntryClose}
          onTpSlClose={onPreviewTpSlClose}
        />
      )}
      {tpSl && onTpSlClose && (tpSl.tp !== null || tpSl.sl !== null || (tpSl.tpLevels && tpSl.tpLevels.length > 0)) && (
        <PlacedTpSlOverlay
          tpSl={tpSl} side={tpSlSide ?? "long"} width={width} height={height}
          toY={toY} minPrice={minPrice} maxPrice={maxPrice}
          padding={padding} dragHandlers={dragHandlers}
          onDragStart={onTpSlDragStart} onClose={onTpSlClose}
        />
      )}
    </div>
  )
}

const LOCAL_DRAFT_ID = "__draft__"

export function ChartWidget({ widget }: ChartWidgetProps) {
  const {
    activeTab, updateWidget, activeChartId, setActiveChartId,
    addPlacedOrder: ctxAddPlaced,
    removePlacedOrder: ctxRemovePlaced, updatePlacedOrderPrice: ctxUpdatePrice,
    updatePlacedOrder: ctxUpdatePlacedOrder,
    positions: ctxPositions,
    closePosition: ctxClosePosition,
    setIsDraggingOrder,
    editingOrderId, setEditingOrderId,
    deductOrderBalance,
    previewOrders, gridOrders, updateGridPreviewPrice, updateGridPlacedPrice, removeGridTpSl, removeGridPreviewTpSl, removeGridEntry, removeGridPreviewEntry, applyGridTpSl, cancelOrderPreview,
    tpSlOrders, setTpSl,
    setLivePrice,
    notifyOrderDragEnd,
  } = useTerminal()

  const [size, setSize] = useState({ width: 0, height: 0 })
  const containerRef = useRef<HTMLDivElement>(null)
  const [candles, setCandles] = useState<Candle[]>([])

  // Local state: draft and editing order id for standalone mode
  const [localDraft, setLocalDraft] = useState<PlacedOrder | undefined>(undefined)
  const [localEditingOrderId, setLocalEditingOrderId] = useState<string | null>(null)
  const localDragHandlers = useRef<Map<string, (price: number) => void>>(new Map())

  const symbol = widget.symbol ?? "BTC/USDT"
  const chartType = widget.chartType ?? "candlestick"
  const marketType = widget.marketType ?? "spot"
  const futuresSide = widget.futuresSide ?? "long"
  const accountId = widget.accountId ?? "main"
  const exchangeId = widget.exchangeId ?? "binance"
  // Stable key that identifies which set of placed orders belongs to this chart
  const positionKey = posKey(accountId, exchangeId, marketType, symbol, futuresSide)

  // Whether there is an order-console widget in the current workspace
  const hasOrderConsole = !!(activeTab?.widgets.some((w) => w.type === "order-console"))
  // Whether this chart is the currently focused one
  const isActive = activeChartId === widget.id

  useEffect(() => { setCandles(generateCandles(symbol)) }, [symbol])

  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const ro = new ResizeObserver(() => setSize({ width: el.clientWidth, height: el.clientHeight }))
    ro.observe(el)
    setSize({ width: el.clientWidth, height: el.clientHeight })
    return () => ro.disconnect()
  }, [])

  const last = candles[candles.length - 1]
  const prev = candles[candles.length - 2]
  const isUp = last && prev ? last.close >= prev.close : true

  // Publish last candle close as live price for this symbol
  useEffect(() => {
    if (last?.close) setLivePrice(symbol, last.close)
  }, [symbol, last?.close, setLivePrice])

  // Standalone mode uses localEditingOrderId for the form; managed mode uses context editingOrderId
  const effectiveEditingOrderId = hasOrderConsole ? editingOrderId : localEditingOrderId

  // ---- Compose orders to render ----
  // Managed mode: read from context; standalone mode: include localDraft
  const draftForChart: PlacedOrder | undefined = hasOrderConsole ? undefined : localDraft
  // Read placed orders from the position — exclude grid orders (rendered by GridOrdersOverlay)
  const positionOrders = ctxPositions[positionKey]?.orders ?? []
  const hasNonGridOrder = positionOrders.some((o: PlacedOrder) => o.source !== "grid")
  const placedForChart: PlacedOrder[] = positionOrders.filter(
    (o: PlacedOrder) => o.source !== "grid" && o.status !== "filled"
  )
  const allOrders: PlacedOrder[] = [...(draftForChart ? [draftForChart] : []), ...placedForChart]

  // Preview lines for this chart (dashed, not yet placed)
  const previewOrdersList: ChartGridPreview[] = Object.values(previewOrders).filter(
    (g): g is ChartGridPreview => !!g && g.chartId === widget.id
  )
  // Placed grid orders for this chart (solid).
  // When the position also has non-grid orders, suppress TP/SL on grid orders —
  // the shared position TP/SL is owned by PlacedTpSlOverlay instead.
  const gridOrdersList: ChartGridOrders[] = Object.values(gridOrders)
    .filter((g): g is ChartGridOrders => !!g && g.chartId === widget.id)
    .map((g) => hasNonGridOrder ? { ...g, tpPrice: null, slPrice: null, tpLevels: [] } : g)

  // ---- Close handler ----
  const handleOrderClose = useCallback((id: string) => {
    if (id === LOCAL_DRAFT_ID) {
      setLocalDraft(undefined)
    } else {
      ctxRemovePlaced(positionKey, id)
      localDragHandlers.current.delete(id)
      // Clear TP/SL lines when the placed order is removed
      const pos = ctxPositions[positionKey]
      const remaining = pos?.orders.filter((o) => o.id !== id) ?? []
      if (remaining.length === 0) {
        setTpSl(widget.id, { tp: null, sl: null, tpLevels: undefined })
      }
    }
  }, [positionKey, ctxRemovePlaced, ctxPositions, widget.id, setTpSl])

  // Tracks whether a drag is currently active (cursor has moved enough to be a drag)
  const isDraggingRef = useRef(false)

  // ---- Drag/click handler ----
  // Short mousedown+mouseup (no movement) = click → toggle edit mode
  // Mousedown + hold/move = drag → move order price
  const handleOrderDragStart = useCallback((
    id: string,
    e: React.MouseEvent,
    _toPrice: (yPx: number) => number,
    minP: number,
    maxP: number,
    chartH: number,
    _padTop: number,
  ) => {
    e.stopPropagation()
    e.preventDefault()

    const isDraftOrder = id === LOCAL_DRAFT_ID

    let startPrice = 0
    if (isDraftOrder) {
      startPrice = draftForChart?.price ?? 0
    } else {
      startPrice = ctxPositions[positionKey]?.orders.find((o) => o.id === id)?.price ?? 0
    }

    const startY = e.clientY
    const DRAG_THRESHOLD = 4 // px
    let dragStarted = false
    isDraggingRef.current = false

    const startDrag = () => {
      if (dragStarted) return
      dragStarted = true
      isDraggingRef.current = true
      document.body.style.cursor = "grabbing"
    }

    // Track final price during drag without triggering React re-renders
    const finalPriceRef = { current: startPrice }

    const onMove = (mv: MouseEvent) => {
      const dy = mv.clientY - startY
      if (!dragStarted && Math.abs(dy) >= DRAG_THRESHOLD) startDrag()
      if (!dragStarted) return

      const pricePerPx = (maxP - minP) / chartH
      const newPrice = Math.max(minP, Math.min(maxP, startPrice - dy * pricePerPx))
      finalPriceRef.current = newPrice

      // Move the SVG element imperatively — no React state, no re-render
      localDragHandlers.current.get(isDraftOrder ? LOCAL_DRAFT_ID : id)?.(newPrice)
    }

    const onUp = () => {
      window.removeEventListener("mousemove", onMove)
      window.removeEventListener("mouseup", onUp)
      document.body.style.cursor = ""
      isDraggingRef.current = false

      if (dragStarted) {
        // Commit final price to state only once on mouseup
        const finalPrice = finalPriceRef.current
        if (isDraftOrder) {
          setLocalDraft((d) => d ? { ...d, price: finalPrice } : d)
        } else {
          ctxUpdatePrice(positionKey, id, finalPrice)
          notifyOrderDragEnd(id, finalPrice)
        }
        setIsDraggingOrder(false)
      }
      // Single click does nothing — edit mode is triggered by double click (handleOrderDoubleClick)
    }

    window.addEventListener("mousemove", onMove)
    window.addEventListener("mouseup", onUp)
  }, [hasOrderConsole, widget.id, positionKey, draftForChart, ctxPositions, ctxUpdatePrice, setIsDraggingOrder, notifyOrderDragEnd])

  // ---- Double-click on placed order → enter edit mode ----
  const handleOrderDoubleClick = useCallback((id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    if (hasOrderConsole) {
      setEditingOrderId(editingOrderId === id ? null : id)
    } else {
      setLocalEditingOrderId((prev) => prev === id ? null : id)
    }
  }, [hasOrderConsole, editingOrderId, setEditingOrderId])

  // ---- Cancel edit when clicking chart background ----
  const handleBackgroundClick = useCallback(() => {
    if (hasOrderConsole && editingOrderId) setEditingOrderId(null)
    else if (!hasOrderConsole && localEditingOrderId) setLocalEditingOrderId(null)
  }, [hasOrderConsole, editingOrderId, setEditingOrderId, localEditingOrderId])

  // ---- Place order (standalone mode — always writes to global context) ----
  const handlePlaceOrder = useCallback((order: Omit<PlacedOrder, "id" | "isDraft">, margin?: number): string => {
    const id = Math.random().toString(36).slice(2, 10)
    const now = new Date()
    const time = [now.getHours(), now.getMinutes(), now.getSeconds()]
      .map((n) => n.toString().padStart(2, "0")).join(":")
    ctxAddPlaced(positionKey, { ...order, id, isDraft: false, time, status: "pending" })
    setLocalDraft(undefined)
    const deductAmount = margin ?? order.qty * order.price
    deductOrderBalance(accountId, exchangeId, marketType, deductAmount)
    return id
  }, [positionKey, accountId, exchangeId, marketType, ctxAddPlaced, deductOrderBalance])

  const registerDragPriceHandler = useCallback((id: string, fn: (p: number) => void) => {
    localDragHandlers.current.set(id, fn)
  }, [])

  const handleGridOrderDragStart = useCallback((
    consoleId: string,
    orderId: string,
    e: React.MouseEvent,
    _toPrice: (yPx: number) => number,
    minP: number,
    maxP: number,
    chartH: number,
    _padTop: number,
  ) => {
    e.stopPropagation()
    e.preventDefault()
    // Determine if this is a preview or placed grid order
    const previewGrid = previewOrders[consoleId]
    const placedGrid = gridOrders[consoleId]
    const isPreviewDrag = !!previewGrid
    const order = isPreviewDrag
      ? previewGrid.orders.find((o) => o.id === orderId)
      : placedGrid?.orders.find((o) => o.id === orderId)
    if (!order) return

    // Drag key matches the id used in registerMove calls
    const dragKey = isPreviewDrag
      ? `preview:${consoleId}:${orderId}`
      : `grid:${consoleId}:${orderId}`

    const startPrice = order.price
    const startY = e.clientY
    const DRAG_THRESHOLD = 4
    let dragStarted = false
    const finalPriceRef = { current: startPrice }

    const onMove = (mv: MouseEvent) => {
      const dy = mv.clientY - startY
      if (!dragStarted && Math.abs(dy) >= DRAG_THRESHOLD) {
        dragStarted = true
        document.body.style.cursor = "grabbing"
      }
      if (!dragStarted) return
      const pricePerPx = (maxP - minP) / chartH
      const newPrice = Math.max(minP, Math.min(maxP, startPrice - dy * pricePerPx))
      finalPriceRef.current = newPrice
      localDragHandlers.current.get(dragKey)?.(newPrice)
    }

    const onUp = () => {
      window.removeEventListener("mousemove", onMove)
      window.removeEventListener("mouseup", onUp)
      document.body.style.cursor = ""
      if (dragStarted) {
        if (isPreviewDrag) {
          updateGridPreviewPrice(consoleId, orderId, finalPriceRef.current)
        } else {
          updateGridPlacedPrice(consoleId, orderId, finalPriceRef.current)
        }
      }
    }

    window.addEventListener("mousemove", onMove)
    window.addEventListener("mouseup", onUp)
  }, [previewOrders, gridOrders, updateGridPreviewPrice, updateGridPlacedPrice])

  const registerDraftDragHandler = useCallback((fn: (p: number) => void) => {
    localDragHandlers.current.set(LOCAL_DRAFT_ID, fn)
  }, [])

  // ---- Grid TP/SL drag handler ----
  const handleGridTpSlDragStart = useCallback((
    consoleId: string,
    target: "tp" | "sl",
    tpIndex: number,
    e: React.MouseEvent,
    minP: number,
    maxP: number,
    chartH: number,
  ) => {
    e.stopPropagation()
    e.preventDefault()

    const isPreview = !gridOrders[consoleId] && !!previewOrders[consoleId]
    const grid = gridOrders[consoleId] ?? previewOrders[consoleId]
    if (!grid) return

    const startPrice = target === "sl"
      ? (grid.slPrice ?? 0)
      : (grid.tpLevels[tpIndex] ?? 0)
    if (!startPrice) return

    const prefix = isPreview ? "preview" : "grid"
    const dragKey = target === "sl"
      ? `${prefix}:${consoleId}:sl`
      : `${prefix}:${consoleId}:tp${tpIndex === 0 ? "" : tpIndex + 1}`

    const startY = e.clientY
    const DRAG_THRESHOLD = 4
    let dragStarted = false
    const finalPriceRef = { current: startPrice }

    const onMove = (mv: MouseEvent) => {
      const dy = mv.clientY - startY
      if (!dragStarted && Math.abs(dy) >= DRAG_THRESHOLD) {
        dragStarted = true
        document.body.style.cursor = "grabbing"
      }
      if (!dragStarted) return
      const pricePerPx = (maxP - minP) / chartH
      const newPrice = Math.max(minP * 0.5, Math.min(maxP * 1.5, startPrice - dy * pricePerPx))
      finalPriceRef.current = newPrice
      localDragHandlers.current.get(dragKey)?.(newPrice)
    }

    const onUp = () => {
      window.removeEventListener("mousemove", onMove)
      window.removeEventListener("mouseup", onUp)
      document.body.style.cursor = ""
      if (!dragStarted) return

      const finalPrice = finalPriceRef.current
      const phase = isPreview ? "P1-PREVIEW" : "P2-VIRTUAL"
      if (target === "sl") {
        console.log(`[CHART-DRAG ${phase}] SL drag end. consoleId:`, consoleId, "finalPrice:", finalPrice, "startPrice:", startPrice)
        applyGridTpSl(consoleId, { slPrice: finalPrice })
        // For P2: also update tpSlOrders so TPSL_DRAG_SYNC can sync noTpSl % (used by REANCHOR)
        if (!isPreview) setTpSl(widget.id, { sl: finalPrice })
      } else {
        const newLevels = [...(grid.tpLevels ?? [])]
        newLevels[tpIndex] = finalPrice
        console.log(`[CHART-DRAG ${phase}] TP drag end. consoleId:`, consoleId, "tpIndex:", tpIndex, "finalPrice:", finalPrice, "startPrice:", startPrice, "newLevels:", newLevels)
        applyGridTpSl(consoleId, { tpLevels: newLevels, tpPrice: newLevels[0] ?? null })
        // For P2: also update tpSlOrders so TPSL_DRAG_SYNC can sync noTpSl % (used by REANCHOR)
        if (!isPreview) setTpSl(widget.id, { tpLevels: newLevels, tp: newLevels[0] ?? null })
      }
    }

    window.addEventListener("mousemove", onMove)
    window.addEventListener("mouseup", onUp)
  }, [gridOrders, previewOrders, applyGridTpSl, setTpSl, widget.id])

  // ---- TP/SL drag handler ----
  const handleTpSlDragStart = useCallback((
    key: "tp" | "sl",
    e: React.MouseEvent,
    minP: number,
    maxP: number,
    chartH: number,
    _padTop: number,
    tpIndex?: number,
  ) => {
    e.stopPropagation()
    e.preventDefault()
    const dragKey = key === "tp" ? `placed-tp${tpIndex ?? 0}` : "placed-sl"
    const current = tpSlOrders[widget.id]
    let startPrice: number
    if (key === "tp") {
      const levels = current?.tpLevels
      startPrice = levels && levels.length > 0
        ? (levels[tpIndex ?? 0] ?? levels[0])
        : (current?.tp ?? 0)
    } else {
      startPrice = current?.sl ?? 0
    }
    if (!startPrice) return

    const startY = e.clientY
    const DRAG_THRESHOLD = 4
    let dragStarted = false
    const finalPriceRef = { current: startPrice }

    const onMove = (mv: MouseEvent) => {
      const dy = mv.clientY - startY
      if (!dragStarted && Math.abs(dy) >= DRAG_THRESHOLD) {
        dragStarted = true
        document.body.style.cursor = "grabbing"
      }
      if (!dragStarted) return
      const pricePerPx = (maxP - minP) / chartH
      const newPrice = Math.max(minP * 0.5, Math.min(maxP * 1.5, startPrice - dy * pricePerPx))
      finalPriceRef.current = newPrice
      localDragHandlers.current.get(dragKey)?.(newPrice)
    }

    const onUp = () => {
      window.removeEventListener("mousemove", onMove)
      window.removeEventListener("mouseup", onUp)
      document.body.style.cursor = ""
      if (dragStarted) {
        const newPrice = finalPriceRef.current
        if (key === "sl") {
          console.log("[CHART-DRAG P3-REAL] SL drag end. chartId:", widget.id, "finalPrice:", newPrice, "startPrice:", startPrice)
          setTpSl(widget.id, { sl: newPrice })
        } else {
          const levels = current?.tpLevels
          if (levels && levels.length > 1) {
            const idx = tpIndex ?? 0
            const newLevels = levels.map((p, i) => i === idx ? newPrice : p)
            console.log("[CHART-DRAG P3-REAL] TP drag end (multi). chartId:", widget.id, "tpIndex:", idx, "finalPrice:", newPrice, "startPrice:", startPrice, "newLevels:", newLevels)
            setTpSl(widget.id, { tpLevels: newLevels, tp: newLevels[0] })
          } else {
            console.log("[CHART-DRAG P3-REAL] TP drag end (single). chartId:", widget.id, "finalPrice:", newPrice, "startPrice:", startPrice)
            setTpSl(widget.id, { tp: newPrice, tpLevels: undefined })
          }
        }
      }
    }

    window.addEventListener("mousemove", onMove)
    window.addEventListener("mouseup", onUp)
  }, [tpSlOrders, widget.id, setTpSl])

  const handleTpSlClose = useCallback((key: "tp" | "sl", tpIndex?: number) => {
    if (key === "tp") {
      const levels = tpSlOrders[widget.id]?.tpLevels
      if (levels && levels.length > 1 && tpIndex !== undefined) {
        const newLevels = levels.filter((_, i) => i !== tpIndex)
        setTpSl(widget.id, { tpLevels: newLevels, tp: newLevels[0] })
      } else {
        setTpSl(widget.id, { tp: null, tpLevels: undefined })
      }
    } else {
      setTpSl(widget.id, { sl: null })
    }
  }, [widget.id, setTpSl, tpSlOrders])

  const rawChartTpSl = tpSlOrders[widget.id] ?? null

  // Only show chartTpSl (PlacedTpSlOverlay) when at least one non-grid order exists.
  // hasNonGridOrder is computed above alongside gridOrdersList.
  const chartTpSl = hasNonGridOrder ? rawChartTpSl : null

  // Use widget rect height as fallback when size hasn't been measured yet
  const containerHeight = size.height || widget.rect.height - 60
  const chartAreaHeight = widget.showOrderForm ? containerHeight * 0.6 : containerHeight

  // Focused chart border highlight when managed mode
  const focusStyle = hasOrderConsole && isActive
    ? { outline: "2px solid rgba(30,111,239,0.5)", outlineOffset: "-2px" }
    : {}

  return (
    <div
      className="flex flex-col h-full"
      style={focusStyle}
      onClick={() => {
        if (hasOrderConsole) setActiveChartId(widget.id)
      }}
    >
      {/* Top bar — symbol, price, change only */}
      <div className="flex items-center gap-2 px-2 py-1"
        style={{ borderBottom: "1px solid rgba(255,255,255,0.05)", flexShrink: 0 }}>

        {/* Symbol selector */}
        <select
          value={symbol}
          onChange={(e) => updateWidget(widget.id, { symbol: e.target.value })}
          className="font-mono text-xs bg-transparent border-0 outline-none cursor-pointer font-bold"
          style={{ color: "inherit", opacity: 0.9 }}
          onMouseDown={(e) => e.stopPropagation()}
        >
          {SYMBOLS.map((s) => (
            <option key={s} value={s} style={{ background: "#0d1526" }}>{s}</option>
          ))}
        </select>

        {last && (
          <span className="font-mono text-xs font-bold" style={{ color: isUp ? "#00e5a0" : "#ff4757" }}>
            {formatPrice(last.close)}
          </span>
        )}
        {last && prev && (
          <span className="font-mono text-xs" style={{ color: isUp ? "#00e5a0" : "#ff4757" }}>
            {isUp ? "+" : ""}{(((last.close - prev.close) / prev.close) * 100).toFixed(2)}%
          </span>
        )}

        {/* Active chart indicator for managed mode */}
        {hasOrderConsole && (
          <span className="font-mono px-1.5 py-0.5 rounded"
            style={{
              fontSize: 9,
              background: isActive ? "rgba(30,111,239,0.15)" : "rgba(255,255,255,0.04)",
              color: isActive ? "#1e6fef" : "rgba(255,255,255,0.25)",
              border: `1px solid ${isActive ? "rgba(30,111,239,0.3)" : "rgba(255,255,255,0.07)"}`,
            }}>
            {isActive ? "● ACTIVE" : "○ CLICK"}
          </span>
        )}
      </div>

      {/* Chart + order book */}
      <div className="flex flex-1 min-h-0 flex-col">
        <div className="flex min-h-0 overflow-hidden"
          style={{ flex: (!hasOrderConsole && widget.showOrderForm) ? "1 1 auto" : "1 1 100%" }}>
          <div ref={containerRef} className="flex-1 min-w-0 overflow-hidden" style={{ minHeight: 0, position: "relative" }}>
            {size.width > 0 && (
              chartType === "candlestick"
                ? <CandlestickChart
                    candles={candles} width={size.width} height={Math.max(chartAreaHeight, 80)}
                    allOrders={allOrders}
                    editingOrderId={effectiveEditingOrderId}
                    onOrderClose={handleOrderClose}
                    onOrderDragStart={handleOrderDragStart}
                    onOrderDoubleClick={handleOrderDoubleClick}
                    onBackgroundClick={handleBackgroundClick}
                    dragHandlers={localDragHandlers}
                    previewOrdersList={previewOrdersList}
                    gridOrdersList={gridOrdersList}
                    onGridOrderDragStart={handleGridOrderDragStart}
                    onGridTpSlDragStart={handleGridTpSlDragStart}
                    onGridClose={(consoleId, target, tpIndex) => removeGridTpSl(consoleId, target, tpIndex)}
                    onGridEntryClose={(consoleId, orderId) => removeGridEntry(consoleId, orderId)}
                    onPreviewOrderDragStart={handleGridOrderDragStart}
                    onPreviewGridTpSlDragStart={handleGridTpSlDragStart}
                    onPreviewClose={undefined}
                    onPreviewEntryClose={(consoleId, orderId) => {
                      if (previewOrders[consoleId]?.source === "order") cancelOrderPreview(consoleId)
                      else removeGridPreviewEntry(consoleId, orderId)
                    }}
                    onPreviewTpSlClose={(consoleId, target, tpIndex) => removeGridPreviewTpSl(consoleId, target, tpIndex)}
                    tpSl={chartTpSl}
                    tpSlSide={futuresSide}
                    onTpSlDragStart={handleTpSlDragStart}
                    onTpSlClose={handleTpSlClose}
                    activePosition={ctxPositions[positionKey]?.status === "active" ? ctxPositions[positionKey] : null}
                    onClosePosition={() => ctxClosePosition(positionKey)}
                  />
                : <LineChart
                    candles={candles} width={size.width} height={Math.max(chartAreaHeight, 80)}
                    allOrders={allOrders}
                    editingOrderId={effectiveEditingOrderId}
                    onOrderClose={handleOrderClose}
                    onOrderDragStart={handleOrderDragStart}
                    onOrderDoubleClick={handleOrderDoubleClick}
                    onBackgroundClick={handleBackgroundClick}
                    dragHandlers={localDragHandlers}
                    previewOrdersList={previewOrdersList}
                    gridOrdersList={gridOrdersList}
                    onGridOrderDragStart={handleGridOrderDragStart}
                    onGridTpSlDragStart={handleGridTpSlDragStart}
                    onGridClose={(consoleId, target, tpIndex) => removeGridTpSl(consoleId, target, tpIndex)}
                    onGridEntryClose={(consoleId, orderId) => removeGridEntry(consoleId, orderId)}
                    onPreviewOrderDragStart={handleGridOrderDragStart}
                    onPreviewGridTpSlDragStart={handleGridTpSlDragStart}
                    onPreviewClose={undefined}
                    onPreviewEntryClose={(consoleId, orderId) => {
                      if (previewOrders[consoleId]?.source === "order") cancelOrderPreview(consoleId)
                      else removeGridPreviewEntry(consoleId, orderId)
                    }}
                    onPreviewTpSlClose={(consoleId, target, tpIndex) => removeGridPreviewTpSl(consoleId, target, tpIndex)}
                    tpSl={chartTpSl}
                    tpSlSide={futuresSide}
                    onTpSlDragStart={handleTpSlDragStart}
                    onTpSlClose={handleTpSlClose}
                    activePosition={ctxPositions[positionKey]?.status === "active" ? ctxPositions[positionKey] : null}
                    onClosePosition={() => ctxClosePosition(positionKey)}
                  />
            )}
          </div>

          {widget.showOrderBook && <OrderBookPanel symbol={symbol} />}
        </div>

        {/* Inline order form — only in standalone mode */}
        {!hasOrderConsole && widget.showOrderForm && (
          <div className="flex-shrink-0 overflow-y-auto">
            <StandaloneOrderForm
              symbol={symbol}
              currentPrice={last?.close}
              marketType={marketType}
              futuresSide={futuresSide}
              accountId={widget.accountId ?? "main"}
              exchangeId={widget.exchangeId ?? "binance"}
              onFuturesSideChange={(fs) => updateWidget(widget.id, { futuresSide: fs })}
              onDraftChange={(draft) => {
                setLocalDraft(draft ? { ...draft, id: LOCAL_DRAFT_ID, isDraft: true } : undefined)
              }}
              onPlaceOrder={handlePlaceOrder}
              registerDragPriceHandler={registerDragPriceHandler}
              registerDraftDragHandler={registerDraftDragHandler}
              editingOrder={localEditingOrderId ? (ctxPositions[positionKey]?.orders ?? []).find((o) => o.id === localEditingOrderId) : undefined}
              onUpdateOrder={(id, updates) => {
                ctxUpdatePlacedOrder(positionKey, id, updates)
                setLocalEditingOrderId(null)
              }}
              onCancelEdit={() => setLocalEditingOrderId(null)}
            />
          </div>
        )}
      </div>
    </div>
  )
}

// ---- OrderBookPanel ----

function OrderBookPanel({ symbol }: { symbol: string }) {
  const [data, setData] = useState({ asks: [], bids: [] } as { asks: any[]; bids: any[] })

  useEffect(() => {
    const update = () => setData(generateOrderBook(symbol))
    update()
    const t = setInterval(update, 1500)
    return () => clearInterval(t)
  }, [symbol])

  const maxTotal = Math.max(
    ...(data.asks.map((a) => a.total) || [1]),
    ...(data.bids.map((b) => b.total) || [1]),
    1
  )

  return (
    <div className="flex flex-col overflow-hidden"
      style={{ width: 180, borderLeft: "1px solid rgba(255,255,255,0.06)", flexShrink: 0 }}>
      <div className="px-2 py-1 text-xs font-mono"
        style={{ opacity: 0.5, borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
        <span style={{ color: "#ff4757", marginRight: 8 }}>ASKS</span>
        <span style={{ color: "#00e5a0" }}>BIDS</span>
      </div>
      <div className="flex-1 overflow-auto">
        {data.asks.slice(0, 10).reverse().map((ask, i) => (
          <div key={i} className="relative px-1 py-px flex justify-between text-xs font-mono">
            <div className="absolute inset-0"
              style={{ background: "rgba(255,71,87,0.08)", width: `${(ask.total / maxTotal) * 100}%` }} />
            <span style={{ color: "#ff4757", position: "relative" }}>{formatPrice(ask.price)}</span>
            <span style={{ opacity: 0.7, position: "relative" }}>{ask.size.toFixed(3)}</span>
          </div>
        ))}
        <div className="px-1 py-0.5 text-center text-xs font-mono"
          style={{ opacity: 0.4, borderTop: "1px solid rgba(255,255,255,0.05)", borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
          spread
        </div>
        {data.bids.slice(0, 10).map((bid, i) => (
          <div key={i} className="relative px-1 py-px flex justify-between text-xs font-mono">
            <div className="absolute inset-0"
              style={{ background: "rgba(0,229,160,0.08)", width: `${(bid.total / maxTotal) * 100}%` }} />
            <span style={{ color: "#00e5a0", position: "relative" }}>{formatPrice(bid.price)}</span>
            <span style={{ opacity: 0.7, position: "relative" }}>{bid.size.toFixed(3)}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ---- Standalone order form (only rendered when no order-console) ----

function StandaloneOrderForm({
  symbol,
  currentPrice,
  marketType = "spot",
  futuresSide = "long",
  accountId = "main",
  exchangeId = "binance",
  onFuturesSideChange,
  onDraftChange,
  onPlaceOrder,
  registerDragPriceHandler,
  registerDraftDragHandler,
  editingOrder,
  onUpdateOrder,
  onCancelEdit,
}: {
  symbol: string
  currentPrice?: number
  marketType?: "spot" | "futures"
  futuresSide?: "long" | "short"
  accountId?: string
  exchangeId?: string
  onFuturesSideChange?: (fs: "long" | "short") => void
  onDraftChange: (draft: DraftOrder | undefined) => void
  onPlaceOrder: (order: Omit<PlacedOrder, "id" | "isDraft">, margin?: number) => string
  registerDragPriceHandler: (id: string, fn: (price: number) => void) => void
  registerDraftDragHandler: (fn: (price: number) => void) => void
  editingOrder?: PlacedOrder
  onUpdateOrder?: (id: string, updates: Partial<Omit<PlacedOrder, "id" | "isDraft">>) => void
  onCancelEdit?: () => void
}) {
  // For spot: buy/sell directly. For futures: side is derived from futuresSide (long=buy, short=sell)
  const [side, setSide] = useState<"buy" | "sell">("buy")

  // In futures mode keep internal side in sync with futuresSide prop
  const effectiveSide: "buy" | "sell" = marketType === "futures"
    ? (futuresSide === "long" ? "buy" : "sell")
    : side
  const [price, setPrice] = useState(() => currentPrice ? priceToString(currentPrice) : "")
  const [qty, setQty] = useState("")
  const [amount, setAmount] = useState("")
  const [orderType, setOrderType] = useState<"limit" | "market" | "stop">("limit")
  const [stopPrice, setStopPrice] = useState("")
  const [anchor, setAnchor] = useState<AnchorField>("qty")
  const [lastResult, setLastResult] = useState<{ success: boolean; msg: string } | null>(null)

  const { getBalance, refundOrderBalance, deductOrderBalance } = useTerminal()
  const { walletBalance, inOrders } = getBalance(accountId, exchangeId, marketType)
  const { settings: posSettings } = usePositionSettings(symbol)

  // Refs so drag callbacks always read current values without re-registering
  const qtyRef = useRef(qty)
  const amountRef = useRef(amount)
  const anchorRef = useRef(anchor)
  qtyRef.current = qty
  amountRef.current = amount
  anchorRef.current = anchor

  useEffect(() => {
    if (currentPrice && !price) {
      setPrice(priceToString(currentPrice))
    }
  }, [currentPrice])

  // Load editing order into form when edit mode activated
  useEffect(() => {
    if (editingOrder) {
      setSide(editingOrder.side)
      setPrice(priceToString(editingOrder.price))
      setQty(editingOrder.qty.toString())
      setAmount((editingOrder.qty * editingOrder.price).toFixed(2))
      setOrderType(editingOrder.orderType)
      setAnchor("qty")
      onDraftChange(undefined)
    }
  }, [editingOrder?.id])

  const effectivePrice = orderType === "market" ? (currentPrice ?? 0) : parseFloat(price) || 0

  useEffect(() => {
    if (editingOrder) {
      setStopPrice("")
      return
    }
    const qtyNum = parseFloat(qty)
    if (qtyNum > 0 && effectivePrice > 0) {
      onDraftChange({ side: effectiveSide, price: effectivePrice, qty: qtyNum, orderType: orderType === "stop" ? "limit" : orderType })
    } else {
      onDraftChange(undefined)
    }
  }, [effectiveSide, price, qty, orderType, effectivePrice, editingOrder])

  // Register draft drag handler once — uses refs to always read current state
  useEffect(() => {
    registerDraftDragHandler((newPrice: number) => {
      setPrice(priceToString(newPrice))
      if (anchorRef.current === "qty") {
        const q = parseFloat(qtyRef.current)
        if (!isNaN(q) && q > 0) setAmount((q * newPrice).toFixed(2))
      } else {
        const a = parseFloat(amountRef.current)
        if (!isNaN(a) && a > 0 && newPrice > 0) setQty((a / newPrice).toFixed(6))
      }
    })
  }, [registerDraftDragHandler])

  const handlePriceChange = (v: string) => {
    setPrice(v)
    const p = parseFloat(v)
    if (isNaN(p) || p <= 0) return
    if (anchor === "qty") {
      const q = parseFloat(qty)
      if (!isNaN(q)) setAmount((q * p).toFixed(2))
    } else {
      const a = parseFloat(amount)
      if (!isNaN(a) && p > 0) setQty((a / p).toFixed(6))
    }
  }

  const handleQtyChange = (v: string) => {
    setAnchor("qty")
    setQty(v)
    const q = parseFloat(v)
    if (!isNaN(q) && q > 0 && effectivePrice > 0) setAmount((q * effectivePrice).toFixed(2))
    else if (v === "") setAmount("")
  }

  const handleAmountChange = (v: string) => {
    setAnchor("amount")
    setAmount(v)
    const a = parseFloat(v)
    if (!isNaN(a) && a > 0 && effectivePrice > 0) setQty((a / effectivePrice).toFixed(6))
    else if (v === "") setQty("")
  }

  const handlePctClick = (pct: number) => {
    const freeMargin = Math.max(0, walletBalance - inOrders)
    const availableForOrder = marketType === "futures" ? freeMargin * posSettings.leverage : freeMargin
    if (anchor === "qty") {
      const maxQty = effectivePrice > 0 ? availableForOrder / effectivePrice : 0
      const q = (pct / 100) * maxQty
      setQty(q.toFixed(6))
      if (effectivePrice > 0) setAmount((q * effectivePrice).toFixed(2))
    } else {
      const a = (pct / 100) * availableForOrder
      setAnchor("amount")
      setAmount(a.toFixed(2))
      if (effectivePrice > 0) setQty((a / effectivePrice).toFixed(6))
    }
  }

  const stopProp = (e: React.MouseEvent) => e.stopPropagation()

  const handleSubmit = () => {
    const qtyNum = parseFloat(qty)
    if (!qtyNum || qtyNum <= 0) return
    if (orderType !== "market" && !price) return

    if (editingOrder && onUpdateOrder) {
      const newNotional = qtyNum * effectivePrice
      const newMargin = marketType === "futures" ? newNotional / posSettings.leverage : newNotional
      if (editingOrder.accountId && editingOrder.exchangeId && editingOrder.marketType && editingOrder.margin != null) {
        refundOrderBalance(editingOrder.accountId, editingOrder.exchangeId, editingOrder.marketType, editingOrder.margin)
        deductOrderBalance(editingOrder.accountId, editingOrder.exchangeId, editingOrder.marketType, newMargin)
      }
      onUpdateOrder(editingOrder.id, { side: effectiveSide, price: effectivePrice, qty: qtyNum, orderType: orderType === "stop" ? "limit" : orderType, margin: newMargin })
      setQty("")
      setAmount("")
      setAnchor("qty")
      setLastResult({ success: true, msg: `Updated ${effectiveSide.toUpperCase()} ${qty} @ ${price}` })
      setTimeout(() => setLastResult(null), 1500)
      return
    }

    const notional = qtyNum * effectivePrice
    const margin = marketType === "futures" ? notional / posSettings.leverage : notional
    const id = onPlaceOrder({
      side: effectiveSide,
      price: effectivePrice,
      qty: qtyNum,
      orderType: orderType === "stop" ? "limit" : orderType,
      symbol,
      accountId,
      exchangeId,
      marketType,
      leverage: posSettings.leverage,
      margin,
      status: "pending",
    }, margin)
    registerDragPriceHandler(id, (newPrice: number) => {
      setPrice(priceToString(newPrice))
      if (anchorRef.current === "qty") {
        const q = parseFloat(qtyRef.current)
        if (!isNaN(q) && q > 0) setAmount((q * newPrice).toFixed(2))
      } else {
        const a = parseFloat(amountRef.current)
        if (!isNaN(a) && a > 0 && newPrice > 0) setQty((a / newPrice).toFixed(6))
      }
    })

    const ticker = symbol.split("/")[0]
    setLastResult({ success: true, msg: `${effectiveSide.toUpperCase()} ${qty} ${ticker} ${orderType === "market" ? "@ MKT" : `@ ${price}`}` })
    setTimeout(() => setLastResult(null), 1500)

    setQty("")
    setAmount("")
    setAnchor("qty")
    setStopPrice("")
  }

  const handleCancelEdit = () => {
    onCancelEdit?.()
    setQty("")
    setAmount("")
    setAnchor("qty")
    setStopPrice("")
  }

  const accentColor = effectiveSide === "buy" ? "#00e5a0" : "#ff4757"
  const accentBg = effectiveSide === "buy" ? "rgba(0,229,160,0.5)" : "rgba(255,71,87,0.5)"

  const qtyBorder = anchor === "qty"
    ? `1px solid ${accentBg}`
    : "1px solid rgba(255,255,255,0.1)"
  const amtBorder = anchor === "amount"
    ? `1px solid ${accentBg}`
    : "1px solid rgba(255,255,255,0.1)"

  const freeMarginCalc = Math.max(0, walletBalance - inOrders)
  const availableForOrder = marketType === "futures" ? freeMarginCalc * posSettings.leverage : freeMarginCalc
  const maxQty = effectivePrice > 0 ? availableForOrder / effectivePrice : 0
  const maxAmount = availableForOrder
  const fmtQty = (n: number) => n < 0.001 ? n.toFixed(6) : n < 1 ? n.toFixed(4) : n.toFixed(2)
  const fmtAmt = (n: number) => n.toLocaleString("en-US", { maximumFractionDigits: 2 })

  const ticker = symbol.split("/")[0]

  return (
    <div className="px-2 py-1.5 flex-shrink-0 text-xs"
      style={{ borderTop: "1px solid rgba(255,255,255,0.06)" }}>

      {/* Position context: balance + leverage + margin mode */}
      <div className="mb-1.5 flex items-center" onMouseDown={stopProp}>
        <PositionBarCompact
          symbol={symbol}
          marketType={marketType}
          availableBalance={walletBalance}
          inOrders={inOrders}
        />
      </div>

      {/* Spot: Buy/Sell toggle | Futures: Long/Short toggle */}
      {marketType === "spot" ? (
        <div className="flex gap-0.5 mb-1">
          {(["buy", "sell"] as const).map((s) => (
            <button key={s}
              onClick={() => setSide(s)}
              className="flex-1 py-0.5 text-xs font-mono font-bold rounded transition-all"
              style={{
                background: side === s ? (s === "buy" ? "rgba(0,229,160,0.2)" : "rgba(255,71,87,0.2)") : "transparent",
                border: `1px solid ${side === s ? (s === "buy" ? "#00e5a0" : "#ff4757") : "rgba(255,255,255,0.1)"}`,
                color: side === s ? (s === "buy" ? "#00e5a0" : "#ff4757") : "rgba(255,255,255,0.4)",
              }}
              onMouseDown={stopProp}
            >
              {s === "buy" ? "BUY" : "SELL"}
            </button>
          ))}
        </div>
      ) : (
        <div className="flex gap-0.5 mb-1">
          {(["long", "short"] as const).map((fs) => (
            <button key={fs}
              onClick={() => onFuturesSideChange?.(fs)}
              className="flex-1 py-0.5 text-xs font-mono font-bold rounded transition-all"
              style={{
                background: futuresSide === fs
                  ? (fs === "long" ? "rgba(0,229,160,0.2)" : "rgba(255,71,87,0.2)")
                  : "transparent",
                border: `1px solid ${futuresSide === fs ? (fs === "long" ? "#00e5a0" : "#ff4757") : "rgba(255,255,255,0.1)"}`,
                color: futuresSide === fs
                  ? (fs === "long" ? "#00e5a0" : "#ff4757")
                  : "rgba(255,255,255,0.4)",
              }}
              onMouseDown={stopProp}
            >
              {fs === "long" ? "LONG" : "SHORT"}
            </button>
          ))}
        </div>
      )}

      {/* Order type */}
      <div className="flex gap-0.5 mb-1">
        {(["limit", "market", "stop"] as const).map((t) => (
          <button key={t}
            onClick={() => setOrderType(t)}
            className="flex-1 px-1 py-0.5 text-xs font-mono rounded capitalize"
            style={{
              background: orderType === t ? "rgba(30,111,239,0.2)" : "transparent",
              border: `1px solid ${orderType === t ? "#1e6fef" : "rgba(255,255,255,0.1)"}`,
              color: orderType === t ? "#1e6fef" : "rgba(255,255,255,0.4)",
              fontSize: 10,
            }}
            onMouseDown={stopProp}
          >
            {t}
          </button>
        ))}
      </div>

      {/* Stop trigger price */}
      {orderType === "stop" && (
        <div className="mb-1">
          <label className="text-xs font-mono" style={{ opacity: 0.5, fontSize: 10 }}>Stop Price</label>
          <input
            type="number"
            value={stopPrice}
            onChange={(e) => setStopPrice(e.target.value)}
            placeholder="0.00"
            className="w-full px-1.5 py-0.5 text-xs font-mono rounded outline-none"
            style={{ border: "1px solid rgba(255,255,255,0.1)", color: "inherit", background: "rgba(255,255,255,0.04)" }}
            onMouseDown={stopProp}
          />
        </div>
      )}

      {/* Limit / Stop limit price */}
      {orderType !== "market" && (
        <div className="mb-1">
          <label className="text-xs font-mono" style={{ opacity: 0.5, fontSize: 10 }}>
            {orderType === "stop" ? "Limit Price" : "Price"}
          </label>
          <input
            type="number"
            value={price}
            onChange={(e) => handlePriceChange(e.target.value)}
            placeholder="0.00"
            className="w-full px-1.5 py-0.5 text-xs font-mono rounded outline-none"
            style={{ border: "1px solid rgba(255,255,255,0.1)", color: "inherit", background: "rgba(255,255,255,0.04)" }}
            onMouseDown={stopProp}
          />
        </div>
      )}

      <div className="grid grid-cols-2 gap-0.5 mb-1">
        <div>
          <div className="flex items-center justify-between">
            <label className="text-xs font-mono" style={{ opacity: anchor === "qty" ? 1 : 0.5, fontSize: 10 }}>Qty</label>
            {maxQty > 0 && (
              <span
                className="text-xs font-mono cursor-pointer"
                style={{ opacity: 0.3, fontSize: 9 }}
                onClick={() => handlePctClick(100)}
                onMouseDown={stopProp}
              >
                max {fmtQty(maxQty)}
              </span>
            )}
          </div>
          <input
            type="number"
            value={qty}
            onChange={(e) => handleQtyChange(e.target.value)}
            onFocus={() => setAnchor("qty")}
            placeholder="0.00"
            className="w-full px-1.5 py-0.5 text-xs font-mono rounded outline-none"
            style={{ border: qtyBorder, color: "inherit", background: "rgba(255,255,255,0.04)" }}
            onMouseDown={stopProp}
          />
        </div>
        <div>
          <div className="flex items-center justify-between">
            <label className="text-xs font-mono" style={{ opacity: anchor === "amount" ? 1 : 0.5, fontSize: 10 }}>Amount</label>
            {maxAmount > 0 && (
              <span
                className="text-xs font-mono cursor-pointer"
                style={{ opacity: 0.3, fontSize: 9 }}
                onClick={() => handlePctClick(100)}
                onMouseDown={stopProp}
              >
                max {fmtAmt(maxAmount)}
              </span>
            )}
          </div>
          <input
            type="number"
            value={amount}
            onChange={(e) => handleAmountChange(e.target.value)}
            onFocus={() => setAnchor("amount")}
            placeholder="0.00"
            className="w-full px-1.5 py-0.5 text-xs font-mono rounded outline-none"
            style={{ border: amtBorder, color: "inherit", background: "rgba(255,255,255,0.04)" }}
            onMouseDown={stopProp}
          />
        </div>
      </div>

      {/* Quick % buttons */}
      <div className="flex gap-0.5 mb-1" onMouseDown={stopProp}>
        {[25, 50, 75, 100].map((pct) => (
          <button
            key={pct}
            onClick={() => handlePctClick(pct)}
            className="flex-1 py-0.5 text-xs font-mono rounded"
            style={{
              background: "rgba(255,255,255,0.05)",
              border: "1px solid rgba(255,255,255,0.08)",
              color: "rgba(255,255,255,0.4)",
              fontSize: 10,
            }}
            onMouseDown={stopProp}
          >
            {pct}%
          </button>
        ))}
      </div>

      {/* Edit mode banner */}
      {editingOrder && (
        <div className="flex items-center gap-1 px-1.5 py-0.5 rounded mb-1 text-xs font-mono"
          style={{ background: "rgba(30,111,239,0.08)", border: "1px solid rgba(30,111,239,0.25)", color: "rgba(30,111,239,0.9)", fontSize: 10 }}
          onMouseDown={stopProp}
        >
          <span style={{ flex: 1 }}>Editing placed order</span>
          <button onClick={handleCancelEdit} className="opacity-60 hover:opacity-100" onMouseDown={stopProp}>✕</button>
        </div>
      )}

      {editingOrder ? (
        <div className="flex gap-0.5">
          <button
            onClick={handleSubmit}
            className="flex-1 py-1.5 text-xs font-mono font-semibold rounded transition-all"
            style={{
              background: "rgba(30,111,239,0.15)",
              border: "1px solid rgba(30,111,239,0.4)",
              color: "#1e6fef",
            }}
            onMouseDown={stopProp}
          >
            Update Order
          </button>
          <button
            onClick={handleCancelEdit}
            className="px-2 py-1.5 text-xs font-mono rounded"
            style={{
              background: "rgba(255,255,255,0.05)",
              border: "1px solid rgba(255,255,255,0.15)",
              color: "rgba(255,255,255,0.5)",
            }}
            onMouseDown={stopProp}
          >
            Cancel
          </button>
        </div>
      ) : (
        <button
          onClick={handleSubmit}
          className="w-full py-1.5 text-sm font-mono font-semibold rounded transition-all"
          style={{
            background: effectiveSide === "buy" ? "#0d3d2e" : "#3d0d0d",
            border: `1px solid ${effectiveSide === "buy" ? "#1a7a5a" : "#c02030"}`,
            color: accentColor,
          }}
          onMouseDown={stopProp}
        >
          {marketType === "futures"
            ? (futuresSide === "long" ? `Long / ${ticker}` : `Short / ${ticker}`)
            : (effectiveSide === "buy" ? `Buy / ${ticker}` : `Sell / ${ticker}`)
          }
        </button>
      )}

      {/* Last result feedback */}
      {lastResult && (
        <div
          className="text-xs font-mono px-2 py-1 rounded text-center mt-1"
          style={{
            background: lastResult.success ? "rgba(0,229,160,0.1)" : "rgba(255,71,87,0.1)",
            color: lastResult.success ? "#00e5a0" : "#ff4757",
            border: `1px solid ${lastResult.success ? "rgba(0,229,160,0.2)" : "rgba(255,71,87,0.2)"}`,
            fontSize: 10,
          }}
        >
          {lastResult.success ? "✓ " : "✗ "}{lastResult.msg}
        </div>
      )}
    </div>
  )
}

// Hover tooltip shown over the Account button
function AccountBalanceTooltip({
  accountId,
  exchangeId,
  marketType,
}: {
  accountId: string
  exchangeId: string
  marketType: "spot" | "futures"
}) {
  const acc = ACCOUNTS.find((a) => a.id === accountId)
  const { getBalance } = useTerminal()
  if (!acc) return null

  const { walletBalance, inOrders } = getBalance(accountId, exchangeId, marketType)
  const freeMargin = walletBalance - inOrders
  const exLabel = EXCHANGES.find((e) => e.id === exchangeId)?.label ?? exchangeId

  const fmt = (n: number) =>
    n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })

  return (
    <div
      className="absolute z-50 flex flex-col gap-1.5 p-3 rounded-lg pointer-events-none"
      style={{
        top: "calc(100% + 5px)",
        left: 0,
        minWidth: 230,
        background: "#0a1220",
        border: "1px solid rgba(255,255,255,0.1)",
        boxShadow: "0 8px 24px rgba(0,0,0,0.6)",
      }}
    >
      <div className="flex items-center justify-between gap-4">
        <span className="font-mono font-semibold" style={{ color: "rgba(200,214,229,0.9)", fontSize: 10, letterSpacing: "0.05em" }}>
          {acc.label.toUpperCase()}
        </span>
        <span className="font-mono" style={{ color: "rgba(255,255,255,0.3)", fontSize: 9 }}>
          {exLabel} · {marketType.toUpperCase()}
        </span>
      </div>

      <div className="flex flex-col gap-1">
        <div className="flex justify-between gap-6">
          <span className="font-mono" style={{ color: "rgba(255,255,255,0.4)", fontSize: 10 }}>Total balance</span>
          <span className="font-mono font-semibold" style={{ color: "rgba(200,214,229,0.85)", fontSize: 10 }}>
            {fmt(walletBalance)} USDT
          </span>
        </div>
        <div className="flex justify-between gap-6">
          <span className="font-mono" style={{ color: "rgba(255,255,255,0.4)", fontSize: 10 }}>In open orders</span>
          <span className="font-mono" style={{ color: "rgba(255,71,87,0.85)", fontSize: 10 }}>
            −{fmt(inOrders)} USDT
          </span>
        </div>
      </div>

      <div style={{ borderTop: "1px solid rgba(255,255,255,0.07)" }} />

      <div className="flex justify-between gap-6">
        <span className="font-mono font-semibold" style={{ color: "rgba(255,255,255,0.5)", fontSize: 10 }}>Free margin</span>
        <span className="font-mono font-bold" style={{ color: "rgba(200,214,229,0.95)", fontSize: 10 }}>
          {fmt(freeMargin)} USDT
        </span>
      </div>
    </div>
  )
}

function HeaderDropdown({
  icon,
  label,
  items,
  selected,
  onSelect,
  onOpenChange,
}: {
  icon: React.ReactNode
  label: string
  items: { id: string; label: string }[]
  selected: string
  onSelect: (id: string) => void
  onOpenChange?: (open: boolean) => void
}) {
  const [open, setOpen] = useState(false)

  const setOpenWithCb = (v: boolean) => {
    setOpen(v)
    onOpenChange?.(v)
  }
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpenWithCb(false)
    }
    document.addEventListener("mousedown", handler)
    return () => document.removeEventListener("mousedown", handler)
  }, [open])

  const selectedLabel = items.find((i) => i.id === selected)?.label ?? label

  return (
    <div ref={ref} className="relative" style={{ userSelect: "none" }}>
      <button
        onClick={() => setOpenWithCb(!open)}
        className="flex items-center gap-0.5 px-1.5 py-0.5 font-mono rounded transition-all"
        style={{
          fontSize: 9,
          border: `1px solid ${open ? "rgba(30,111,239,0.5)" : "rgba(255,255,255,0.1)"}`,
          background: open ? "rgba(30,111,239,0.1)" : "transparent",
          color: open ? "#1e6fef" : "rgba(255,255,255,0.55)",
          whiteSpace: "nowrap",
        }}
      >
        <span style={{ opacity: 0.7, display: "flex", alignItems: "center" }}>{icon}</span>
        <span className="ml-0.5">{selectedLabel}</span>
        <ChevronDown size={8} style={{ opacity: 0.6, marginLeft: 1 }} />
      </button>

      {open && (
        <div
          className="absolute right-0 z-50 py-0.5 rounded font-mono"
          style={{
            top: "calc(100% + 3px)",
            minWidth: 130,
            background: "#0d1526",
            border: "1px solid rgba(255,255,255,0.12)",
            boxShadow: "0 4px 16px rgba(0,0,0,0.5)",
          }}
        >
          {items.map((item) => (
            <button
              key={item.id}
              onClick={() => { onSelect(item.id); setOpenWithCb(false) }}
              className="w-full text-left px-2 py-1 transition-colors"
              style={{
                fontSize: 10,
                background: selected === item.id ? "rgba(30,111,239,0.12)" : "transparent",
                color: selected === item.id ? "#1e6fef" : "rgba(200,214,229,0.8)",
                borderLeft: selected === item.id ? "2px solid #1e6fef" : "2px solid transparent",
              }}
            >
              {item.label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

// ---- Header extra buttons rendered inside the WidgetWrapper header bar ----
export function ChartHeaderExtra({ widget }: { widget: Widget }) {
  const { updateWidget, activeTab } = useTerminal()
  const hasOrderConsole = !!(activeTab?.widgets.some((w) => w.type === "order-console"))

  const marketType = widget.marketType ?? "spot"
  const selectedAccount = widget.accountId ?? "main"
  const selectedExchange = widget.exchangeId ?? "binance"

  const [accountHover, setAccountHover] = useState(false)
  const [accountDropdownOpen, setAccountDropdownOpen] = useState(false)

  const stopProp = (e: React.MouseEvent) => e.stopPropagation()

  return (
    <div className="flex items-center gap-1" onMouseDown={stopProp}>
      {/* Account selector with balance tooltip on hover (hidden when dropdown is open) */}
      <div
        className="relative"
        onMouseEnter={() => setAccountHover(true)}
        onMouseLeave={() => setAccountHover(false)}
      >
        <HeaderDropdown
          icon={<User size={8} />}
          label="Account"
          items={ACCOUNTS}
          selected={selectedAccount}
          onSelect={(id) => updateWidget(widget.id, { accountId: id })}
          onOpenChange={setAccountDropdownOpen}
        />
        {accountHover && !accountDropdownOpen && (
          <AccountBalanceTooltip accountId={selectedAccount} exchangeId={selectedExchange} marketType={marketType} />
        )}
      </div>

      {/* Exchange selector */}
      <HeaderDropdown
        icon={<Building2 size={8} />}
        label="Exchange"
        items={EXCHANGES}
        selected={selectedExchange}
        onSelect={(id) => updateWidget(widget.id, { exchangeId: id })}
      />

      {/* Spot / Futures toggle */}
      <div className="flex rounded overflow-hidden" style={{ border: "1px solid rgba(255,255,255,0.1)" }}>
        {(["spot", "futures"] as const).map((mt) => (
          <button
            key={mt}
            onClick={() => updateWidget(widget.id, { marketType: mt })}
            className="px-1.5 py-0.5 font-mono transition-all"
            style={{
              fontSize: 9,
              fontWeight: 600,
              background: marketType === mt
                ? (mt === "futures" ? "rgba(255,165,0,0.18)" : "rgba(30,111,239,0.18)")
                : "transparent",
              color: marketType === mt
                ? (mt === "futures" ? "#ffa500" : "#1e6fef")
                : "rgba(255,255,255,0.3)",
              borderRight: mt === "spot" ? "1px solid rgba(255,255,255,0.1)" : "none",
            }}
          >
            {mt === "spot" ? "SPOT" : "PERP"}
          </button>
        ))}
      </div>

      {/* Book toggle */}
      <button
        onClick={() => updateWidget(widget.id, { showOrderBook: !widget.showOrderBook })}
        className="px-1.5 py-0.5 font-mono rounded transition-all"
        style={{
          fontSize: 9,
          opacity: widget.showOrderBook ? 1 : 0.55,
          border: `1px solid ${widget.showOrderBook ? "#1e6fef" : "rgba(255,255,255,0.1)"}`,
          color: widget.showOrderBook ? "#1e6fef" : "inherit",
        }}
      >
        ≡ Book
      </button>

      {/* Order toggle — hidden when order-console is in workspace */}
      {!hasOrderConsole && (
        <button
          onClick={() => updateWidget(widget.id, { showOrderForm: !widget.showOrderForm })}
          className="px-1.5 py-0.5 font-mono rounded transition-all"
          style={{
            fontSize: 9,
            opacity: widget.showOrderForm ? 1 : 0.55,
            border: `1px solid ${widget.showOrderForm ? "#00e5a0" : "rgba(255,255,255,0.1)"}`,
            color: widget.showOrderForm ? "#00e5a0" : "inherit",
          }}
        >
          ⌤ Order
        </button>
      )}
    </div>
  )
}
