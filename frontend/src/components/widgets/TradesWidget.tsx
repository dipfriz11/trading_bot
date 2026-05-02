import { useState, useEffect, useRef } from "react"
import { generateTrades, formatPrice } from "@/lib/mock-data"
import { SYMBOLS } from "@/lib/mock-data"
import type { Widget, Trade } from "@/types/terminal"
import { useTerminal } from "@/contexts/TerminalContext"

interface TradesWidgetProps {
  widget: Widget
}

export function TradesWidget({ widget }: TradesWidgetProps) {
  const { updateWidget } = useTerminal()
  const symbol = widget.symbol ?? "BTC/USDT"
  const [trades, setTrades] = useState<Trade[]>([])
  const prevPriceRef = useRef<number | null>(null)
  const [flashMap, setFlashMap] = useState<Record<string, "green" | "red">>({})

  useEffect(() => {
    const initial = generateTrades(symbol, 30)
    setTrades(initial)
    if (initial.length) prevPriceRef.current = initial[0].price

    const t = setInterval(() => {
      setTrades((prev) => {
        const newTrades = generateTrades(symbol, 1)
        const newTrade = newTrades[0]
        if (!newTrade) return prev

        const flash = newTrade.side === "buy" ? "green" : "red"
        setFlashMap((fm) => ({ ...fm, [newTrade.id]: flash }))
        setTimeout(() => setFlashMap((fm) => { const n = { ...fm }; delete n[newTrade.id]; return n }), 500)

        return [{ ...newTrade, id: `t${Date.now()}` }, ...prev.slice(0, 49)]
      })
    }, 600)
    return () => clearInterval(t)
  }, [symbol])

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Symbol selector */}
      <div className="flex items-center gap-2 px-2 py-1 flex-shrink-0" style={{ borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
        <select
          value={symbol}
          onChange={(e) => updateWidget(widget.id, { symbol: e.target.value })}
          className="font-mono text-xs bg-transparent border-0 outline-none cursor-pointer"
          style={{ color: "inherit", opacity: 0.8 }}
          onMouseDown={(e) => e.stopPropagation()}
        >
          {SYMBOLS.map((s) => (
            <option key={s} value={s} style={{ background: "#0d1526" }}>{s}</option>
          ))}
        </select>
        <span className="ml-auto text-xs font-mono" style={{ opacity: 0.4 }}>LIVE</span>
        <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
      </div>

      {/* Column headers */}
      <div className="grid grid-cols-3 px-2 py-0.5 text-xs font-mono flex-shrink-0" style={{ opacity: 0.4, borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
        <span>Price</span>
        <span className="text-right">Size</span>
        <span className="text-right">Time</span>
      </div>

      {/* Trades */}
      <div className="flex-1 overflow-auto min-h-0">
        {trades.map((trade) => (
          <div
            key={trade.id}
            className={`grid grid-cols-3 px-2 text-xs font-mono ${flashMap[trade.id] === "green" ? "flash-green" : flashMap[trade.id] === "red" ? "flash-red" : ""}`}
            style={{ height: 20 }}
          >
            <span style={{ color: trade.side === "buy" ? "#00e5a0" : "#ff4757" }}>
              {formatPrice(trade.price)}
            </span>
            <span className="text-right" style={{ opacity: 0.8 }}>{trade.size.toFixed(4)}</span>
            <span className="text-right" style={{ opacity: 0.5 }}>{trade.time}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
