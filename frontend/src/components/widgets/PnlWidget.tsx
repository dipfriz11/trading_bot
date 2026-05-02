import { useState, useEffect } from "react"
import type { Widget } from "@/types/terminal"

type PnlSnapshot = {
  time: string
  realized: number
  unrealized: number
  total: number
}

function generatePnlHistory(): PnlSnapshot[] {
  const snapshots: PnlSnapshot[] = []
  let realized = 0
  let unrealized = -420
  const now = Date.now()
  for (let i = 23; i >= 0; i--) {
    const t = new Date(now - i * 3600000)
    realized += (Math.random() - 0.42) * 200
    unrealized += (Math.random() - 0.48) * 150
    snapshots.push({
      time: t.getHours().toString().padStart(2, "0") + ":00",
      realized: Math.round(realized * 100) / 100,
      unrealized: Math.round(unrealized * 100) / 100,
      total: Math.round((realized + unrealized) * 100) / 100,
    })
  }
  return snapshots
}

const STATS = [
  { label: "Total P&L", key: "total" as const, color: (v: number) => (v >= 0 ? "#00e5a0" : "#ff4757") },
  { label: "Realized", key: "realized" as const, color: (v: number) => (v >= 0 ? "#00e5a0" : "#ff4757") },
  { label: "Unrealized", key: "unrealized" as const, color: (v: number) => (v >= 0 ? "#00e5a0" : "#ff4757") },
]

export function PnlWidget(_props: { widget: Widget }) {
  const [history, setHistory] = useState<PnlSnapshot[]>([])
  const [view, setView] = useState<"chart" | "table">("chart")

  useEffect(() => {
    setHistory(generatePnlHistory())
    const t = setInterval(() => {
      setHistory((prev) => {
        if (!prev.length) return prev
        const last = prev[prev.length - 1]
        const updated = {
          ...last,
          unrealized: last.unrealized + (Math.random() - 0.5) * 80,
          realized: last.realized + (Math.random() - 0.45) * 30,
        }
        updated.total = updated.realized + updated.unrealized
        return [...prev.slice(0, -1), updated]
      })
    }, 2000)
    return () => clearInterval(t)
  }, [])

  if (!history.length) return null

  const latest = history[history.length - 1]
  const allTotals = history.map((h) => h.total)
  const minVal = Math.min(...allTotals)
  const maxVal = Math.max(...allTotals)
  const range = maxVal - minVal || 1

  const W = 260
  const H = 80
  const points = history.map((h, i) => {
    const x = (i / (history.length - 1)) * W
    const y = H - ((h.total - minVal) / range) * H
    return `${x},${y}`
  })
  const pathD = "M" + points.join("L")
  const fillD = `${pathD}L${W},${H}L0,${H}Z`

  const isPositive = latest.total >= 0

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header stats */}
      <div className="flex-shrink-0 px-3 pt-2 pb-1 grid grid-cols-3 gap-2" style={{ borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
        {STATS.map((s) => {
          const val = latest[s.key]
          const color = s.color(val)
          return (
            <div key={s.label} className="flex flex-col gap-0.5">
              <span className="text-xs font-mono" style={{ opacity: 0.45, fontSize: 10 }}>{s.label}</span>
              <span className="text-xs font-mono font-semibold" style={{ color }}>
                {val >= 0 ? "+" : ""}{val.toFixed(2)}
              </span>
            </div>
          )
        })}
      </div>

      {/* View toggle */}
      <div className="flex-shrink-0 flex px-3 py-1 gap-2">
        {(["chart", "table"] as const).map((v) => (
          <button
            key={v}
            onClick={() => setView(v)}
            className="text-xs font-mono px-2 py-0.5 rounded transition-colors"
            style={{
              background: view === v ? "rgba(30,111,239,0.2)" : "transparent",
              color: view === v ? "#1e6fef" : "rgba(255,255,255,0.4)",
              border: view === v ? "1px solid rgba(30,111,239,0.3)" : "1px solid transparent",
            }}
            onMouseDown={(e) => e.stopPropagation()}
          >
            {v === "chart" ? "Chart" : "Table"}
          </button>
        ))}
      </div>

      {view === "chart" ? (
        <div className="flex-1 overflow-hidden px-3 pb-3 flex flex-col gap-2">
          {/* SVG line chart */}
          <svg
            width="100%"
            viewBox={`0 0 ${W} ${H}`}
            preserveAspectRatio="none"
            style={{ flex: 1, minHeight: 60 }}
          >
            <defs>
              <linearGradient id="pnl-grad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={isPositive ? "#00e5a0" : "#ff4757"} stopOpacity="0.3" />
                <stop offset="100%" stopColor={isPositive ? "#00e5a0" : "#ff4757"} stopOpacity="0.01" />
              </linearGradient>
            </defs>
            <path d={fillD} fill="url(#pnl-grad)" />
            <path d={pathD} fill="none" stroke={isPositive ? "#00e5a0" : "#ff4757"} strokeWidth="1.5" />
          </svg>

          {/* X-axis labels */}
          <div className="flex justify-between text-xs font-mono" style={{ opacity: 0.3, fontSize: 9 }}>
            <span>{history[0].time}</span>
            <span>{history[Math.floor(history.length / 2)].time}</span>
            <span>{history[history.length - 1].time}</span>
          </div>
        </div>
      ) : (
        <div className="flex-1 overflow-auto min-h-0">
          {/* Column headers */}
          <div className="grid grid-cols-4 px-3 py-1 text-xs font-mono sticky top-0" style={{ opacity: 0.4, borderBottom: "1px solid rgba(255,255,255,0.05)", background: "inherit" }}>
            <span>Time</span>
            <span className="text-right">Realized</span>
            <span className="text-right">Unrealized</span>
            <span className="text-right">Total</span>
          </div>
          {[...history].reverse().map((h, i) => (
            <div
              key={i}
              className="grid grid-cols-4 px-3 text-xs font-mono"
              style={{ height: 24, borderBottom: "1px solid rgba(255,255,255,0.025)" }}
            >
              <span style={{ opacity: 0.5 }}>{h.time}</span>
              <span className="text-right" style={{ color: h.realized >= 0 ? "#00e5a0" : "#ff4757" }}>
                {h.realized >= 0 ? "+" : ""}{h.realized.toFixed(0)}
              </span>
              <span className="text-right" style={{ color: h.unrealized >= 0 ? "#00e5a0" : "#ff4757" }}>
                {h.unrealized >= 0 ? "+" : ""}{h.unrealized.toFixed(0)}
              </span>
              <span className="text-right" style={{ color: h.total >= 0 ? "#00e5a0" : "#ff4757", fontWeight: 600 }}>
                {h.total >= 0 ? "+" : ""}{h.total.toFixed(0)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
