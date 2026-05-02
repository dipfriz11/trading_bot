import { useRef, useCallback } from "react"
import { X, Square } from "lucide-react"
import type { Widget, ResizeHandle, WidgetRect } from "@/types/terminal"
import { WIDGET_MIN_SIZE } from "@/types/terminal"
import { useWidgetDrag } from "@/hooks/useWidgetDrag"
import { useTerminal } from "@/contexts/TerminalContext"

// Border colours per preset — widgets are transparent, only the border is coloured
const TRANSPARENT_BDR: Record<string, { bdr: string; bdr2: string; header: string }> = {
  slate:     { bdr: "rgba(110,135,180,0.38)", bdr2: "rgba(148,170,215,0.55)", header: "rgba(255,255,255,0.04)" },
  grey:      { bdr: "rgba(100,110,120,0.35)", bdr2: "rgba(140,150,160,0.50)", header: "rgba(255,255,255,0.04)" },
  lightgrey: { bdr: "rgba(140,150,160,0.35)", bdr2: "rgba(180,188,196,0.50)", header: "rgba(255,255,255,0.04)" },
  steelblue: { bdr: "rgba(58,90,120,0.40)",  bdr2: "rgba(90,130,170,0.55)",  header: "rgba(255,255,255,0.04)" },
}

interface WidgetWrapperProps {
  widget: Widget
  canvasRef: React.RefObject<HTMLDivElement | null>
  children: React.ReactNode
  headerExtra?: React.ReactNode
}

const RESIZE_HANDLES: ResizeHandle[] = ["n", "s", "e", "w", "ne", "nw", "se", "sw"]

const handleStyle = (handle: ResizeHandle): React.CSSProperties => {
  const base: React.CSSProperties = { position: "absolute", zIndex: 20 }
  const size = 8
  const edgeSize = 10
  switch (handle) {
    case "n": return { ...base, top: -edgeSize / 2, left: edgeSize, right: edgeSize, height: edgeSize, cursor: "n-resize" }
    case "s": return { ...base, bottom: -edgeSize / 2, left: edgeSize, right: edgeSize, height: edgeSize, cursor: "s-resize" }
    case "e": return { ...base, right: -edgeSize / 2, top: edgeSize, bottom: edgeSize, width: edgeSize, cursor: "e-resize" }
    case "w": return { ...base, left: -edgeSize / 2, top: edgeSize, bottom: edgeSize, width: edgeSize, cursor: "w-resize" }
    case "ne": return { ...base, top: -size / 2, right: -size / 2, width: size * 2, height: size * 2, cursor: "ne-resize" }
    case "nw": return { ...base, top: -size / 2, left: -size / 2, width: size * 2, height: size * 2, cursor: "nw-resize" }
    case "se": return { ...base, bottom: -size / 2, right: -size / 2, width: size * 2, height: size * 2, cursor: "se-resize" }
    case "sw": return { ...base, bottom: -size / 2, left: -size / 2, width: size * 2, height: size * 2, cursor: "sw-resize" }
  }
}

export function WidgetWrapper({ widget, canvasRef, children, headerExtra }: WidgetWrapperProps) {
  const { removeWidget, bringToFront, updateWidgetRect, updateWidget, activeTab, state, activeChartId } = useTerminal()
  const prevRectRef = useRef<WidgetRect | null>(null)

  const allWidgets = activeTab?.widgets ?? []

  const onMove = useCallback(
    (rect: WidgetRect) => {
      updateWidgetRect(widget.id, rect)
    },
    [widget.id, updateWidgetRect]
  )

  const onBringToFront = useCallback(() => {
    bringToFront(widget.id)
  }, [widget.id, bringToFront])

  const onUpdateAll = useCallback(
    (updates: { id: string; rect: WidgetRect }[]) => {
      for (const u of updates) {
        updateWidgetRect(u.id, u.rect)
      }
    },
    [updateWidgetRect]
  )

  const { startMove, startResize } = useWidgetDrag({
    widget,
    canvasRef,
    onMove,
    onBringToFront,
    allWidgets,
    onUpdateAll,
  })

  const handleDoubleClick = useCallback(() => {
    if (widget.prevRect) {
      const prev = widget.prevRect
      updateWidget(widget.id, { rect: prev, prevRect: undefined })
    } else {
      const canvas = canvasRef.current
      if (!canvas) return
      const expanded: WidgetRect = {
        x: 0,
        y: 0,
        width: canvas.clientWidth,
        height: canvas.clientHeight,
      }
      updateWidget(widget.id, { rect: expanded, prevRect: { ...widget.rect } })
    }
  }, [widget, canvasRef, updateWidget])

  const { rect, zIndex } = widget
  const isTransparent   = state.theme === "transparent"
  const isGlassGraphite = state.theme === "glass-graphite"
  const p = TRANSPARENT_BDR[state.transparentBg ?? "slate"] ?? TRANSPARENT_BDR["slate"]

  // Transparent theme: widget is fully see-through — only border + header separator visible
  const containerStyle: React.CSSProperties = isTransparent ? {
    background: "transparent",
    border: `1px solid ${p.bdr2}`,
    borderRadius: 6,
    boxShadow: `0 0 0 1px ${p.bdr}`,
  } : isGlassGraphite ? {
    background: "transparent",
    border: "1px solid rgba(255,255,255,0.10)",
    borderRadius: 8,
    boxShadow: "0 18px 45px rgba(0,0,0,0.32), inset 0 1px 0 rgba(255,255,255,0.06)",
  } : {}

  const headerStyle: React.CSSProperties = isTransparent ? {
    background: p.header,
    borderBottom: `1px solid ${p.bdr}`,
    color: "#e2e8f0",
    borderRadius: "5px 5px 0 0",
  } : isGlassGraphite ? {
    background: "linear-gradient(180deg, rgba(255,255,255,0.085), rgba(255,255,255,0.025))",
    backdropFilter: "blur(18px)",
    WebkitBackdropFilter: "blur(18px)",
    borderBottom: "1px solid rgba(255,255,255,0.07)",
    borderRadius: "7px 7px 0 0",
    color: "#E6EDF3",
  } : {}

  return (
    <div
      className="absolute widget-container"
      style={{
        left: rect.x,
        top: rect.y,
        width: rect.width,
        height: rect.height,
        zIndex,
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
        ...containerStyle,
      }}
      onMouseDown={() => bringToFront(widget.id)}
    >
      {/* Resize handles */}
      {RESIZE_HANDLES.map((handle) => (
        <div
          key={handle}
          style={handleStyle(handle)}
          onMouseDown={(e) => startResize(e, handle)}
        />
      ))}

      {/* Header */}
      <div
        className="widget-header flex items-center gap-1 px-2 select-none"
        style={{ height: 32, minHeight: 32, cursor: "move", flexShrink: 0, ...headerStyle }}
        onMouseDown={startMove}
        onDoubleClick={handleDoubleClick}
      >
        <span
          className="flex-1 text-xs font-mono font-medium truncate"
          style={{ color: "inherit", opacity: 0.9, letterSpacing: "0.03em" }}
        >
          {widget.title}
          {(widget.type === "order-console" || widget.type === "orderbook")
            ? (() => {
                const chartWidgets = activeTab?.widgets.filter((w) => w.type === "chart") ?? []
                const activeChart = chartWidgets.find((w) => w.id === activeChartId) ?? chartWidgets[0]
                const sym = activeChart?.symbol
                return sym ? <span style={{ opacity: 0.6, marginLeft: 6 }}>{sym}</span> : null
              })()
            : widget.symbol && widget.type !== "chart" && widget.type !== "portfolio"
              ? <span style={{ opacity: 0.6, marginLeft: 6 }}>{widget.symbol}</span>
              : null
          }
        </span>

        {headerExtra && (
          <div className="flex items-center gap-1" onMouseDown={(e) => e.stopPropagation()}>
            {headerExtra}
          </div>
        )}

        <button
          className="flex items-center justify-center rounded opacity-50 hover:opacity-100 transition-opacity"
          style={{ width: 18, height: 18 }}
          onMouseDown={(e) => e.stopPropagation()}
          onClick={(e) => {
            e.stopPropagation()
            prevRectRef.current = widget.rect
            if (widget.prevRect) {
              updateWidget(widget.id, { rect: widget.prevRect, prevRect: undefined })
            } else {
              const canvas = canvasRef.current
              if (!canvas) return
              const minSize = WIDGET_MIN_SIZE[widget.type]
              updateWidget(widget.id, {
                rect: { ...widget.rect, width: minSize.width + 80, height: minSize.height + 80 },
                prevRect: { ...widget.rect },
              })
            }
          }}
        >
          <Square size={10} />
        </button>

        <button
          className="flex items-center justify-center rounded opacity-50 hover:opacity-100 hover:text-red-400 transition-all"
          style={{ width: 18, height: 18 }}
          onMouseDown={(e) => e.stopPropagation()}
          onClick={(e) => {
            e.stopPropagation()
            removeWidget(widget.id)
          }}
        >
          <X size={10} />
        </button>
      </div>

      {/* Content */}
      <div
        className="flex-1 overflow-hidden"
        style={{ minHeight: 0 }}
      >
        {children}
      </div>
    </div>
  )
}
