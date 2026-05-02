import { useState, useRef, useEffect } from "react"
import { Plus, ChartBar as BarChart2, BookOpen, Activity, Briefcase, Search, TrendingUp, Bell, Terminal, Newspaper } from "lucide-react"
import type { WidgetType } from "@/types/terminal"
import { WIDGET_LABELS } from "@/types/terminal"
import { useTerminal } from "@/contexts/TerminalContext"

type WidgetDef = {
  type: WidgetType
  icon: React.ElementType
  description: string
}

const WIDGET_DEFS: WidgetDef[] = [
  { type: "chart", icon: BarChart2, description: "Candlestick & line price chart" },
  { type: "orderbook", icon: BookOpen, description: "Live order book depth" },
  { type: "trades", icon: Activity, description: "Real-time trade feed" },
  { type: "portfolio", icon: Briefcase, description: "Positions & P&L" },
  { type: "screener", icon: Search, description: "Market screener & scanner" },
  { type: "pnl", icon: TrendingUp, description: "P&L statistics & history" },
  { type: "alerts", icon: Bell, description: "Price alerts" },
  { type: "order-console", icon: Terminal, description: "Order entry console" },
  { type: "news", icon: Newspaper, description: "Market news feed" },
]

export function AddWidgetMenu() {
  const { addWidget } = useTerminal()
  const [open, setOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    function handleClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClick)
    return () => document.removeEventListener("mousedown", handleClick)
  }, [open])

  const handleAdd = (type: WidgetType) => {
    const offset = 40 + Math.random() * 60
    addWidget(type, offset, offset)
    setOpen(false)
  }

  return (
    <div ref={menuRef} className="relative flex-shrink-0">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 text-xs font-mono px-2.5 py-1 rounded transition-all"
        style={{
          background: open ? "rgba(30,111,239,0.15)" : "rgba(255,255,255,0.05)",
          color: open ? "#1e6fef" : "rgba(255,255,255,0.6)",
          border: `1px solid ${open ? "rgba(30,111,239,0.3)" : "rgba(255,255,255,0.08)"}`,
        }}
      >
        <Plus size={12} />
        Add Widget
      </button>

      {open && (
        <div
          className="absolute top-full right-0 mt-1 z-[9999] rounded-lg overflow-hidden"
          style={{
            width: 220,
            background: "var(--terminal-surface, #0d1526)",
            border: "1px solid rgba(255,255,255,0.1)",
            boxShadow: "0 8px 32px rgba(0,0,0,0.6)",
          }}
        >
          <div className="px-3 py-2 text-xs font-mono" style={{ opacity: 0.4, borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
            Add Widget to Workspace
          </div>
          {WIDGET_DEFS.map(({ type, icon: Icon, description }) => (
            <button
              key={type}
              onClick={() => handleAdd(type)}
              className="w-full flex items-center gap-3 px-3 py-2 text-left transition-colors hover:bg-white/[0.04]"
            >
              <div
                className="flex-shrink-0 flex items-center justify-center rounded"
                style={{ width: 28, height: 28, background: "rgba(30,111,239,0.1)", border: "1px solid rgba(30,111,239,0.15)" }}
              >
                <Icon size={13} style={{ color: "#1e6fef" }} />
              </div>
              <div className="flex flex-col min-w-0">
                <span className="text-xs font-mono font-medium" style={{ color: "rgba(255,255,255,0.8)" }}>
                  {WIDGET_LABELS[type]}
                </span>
                <span className="text-xs font-mono" style={{ color: "rgba(255,255,255,0.3)", fontSize: 9 }}>
                  {description}
                </span>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
