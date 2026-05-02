import { useState } from "react"
import { Bell, BellOff, Plus, Trash2, Check } from "lucide-react"
import type { Widget } from "@/types/terminal"
import { generateAlerts } from "@/lib/mock-data"
import type { Alert } from "@/types/terminal"
import { SYMBOLS } from "@/lib/mock-data"

export function AlertsWidget(_props: { widget: Widget }) {
  const [alerts, setAlerts] = useState<Alert[]>(() => generateAlerts())
  const [showAdd, setShowAdd] = useState(false)
  const [newSymbol, setNewSymbol] = useState(SYMBOLS[0])
  const [newPrice, setNewPrice] = useState("")
  const [newCondition, setNewCondition] = useState<"above" | "below">("above")

  const handleAdd = () => {
    const price = parseFloat(newPrice)
    if (!newPrice || isNaN(price)) return
    const id = Math.random().toString(36).slice(2, 10)
    setAlerts((prev) => [
      {
        id,
        symbol: newSymbol,
        price,
        condition: newCondition,
        active: true,
        triggered: false,
        createdAt: new Date().toISOString(),
      },
      ...prev,
    ])
    setNewPrice("")
    setShowAdd(false)
  }

  const handleDelete = (id: string) => {
    setAlerts((prev) => prev.filter((a) => a.id !== id))
  }

  const handleToggle = (id: string) => {
    setAlerts((prev) =>
      prev.map((a) =>
        a.id === id ? { ...a, triggered: !a.triggered } : a
      )
    )
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Toolbar */}
      <div
        className="flex-shrink-0 flex items-center gap-2 px-2 py-1"
        style={{ borderBottom: "1px solid rgba(255,255,255,0.05)" }}
      >
        <Bell size={12} style={{ opacity: 0.5 }} />
        <span className="text-xs font-mono flex-1" style={{ opacity: 0.5 }}>
          Price Alerts
        </span>
        <button
          onClick={() => setShowAdd((v) => !v)}
          className="flex items-center gap-1 text-xs font-mono px-1.5 py-0.5 rounded transition-colors hover:opacity-100"
          style={{
            opacity: 0.6,
            background: showAdd ? "rgba(30,111,239,0.15)" : "transparent",
            color: showAdd ? "#1e6fef" : "inherit",
            border: "1px solid rgba(255,255,255,0.08)",
          }}
          onMouseDown={(e) => e.stopPropagation()}
        >
          <Plus size={10} /> Add
        </button>
      </div>

      {/* Add alert form */}
      {showAdd && (
        <div
          className="flex-shrink-0 flex flex-col gap-1.5 px-2 py-2"
          style={{ borderBottom: "1px solid rgba(255,255,255,0.05)", background: "rgba(30,111,239,0.04)" }}
        >
          <div className="flex gap-1.5">
            <select
              value={newSymbol}
              onChange={(e) => setNewSymbol(e.target.value)}
              className="text-xs font-mono bg-transparent border-0 outline-none flex-1"
              style={{ border: "1px solid rgba(255,255,255,0.12)", borderRadius: 4, padding: "2px 4px", color: "inherit" }}
              onMouseDown={(e) => e.stopPropagation()}
            >
              {SYMBOLS.map((s) => (
                <option key={s} value={s} style={{ background: "#0d1526" }}>{s}</option>
              ))}
            </select>
            <select
              value={newCondition}
              onChange={(e) => setNewCondition(e.target.value as "above" | "below")}
              className="text-xs font-mono bg-transparent outline-none"
              style={{ border: "1px solid rgba(255,255,255,0.12)", borderRadius: 4, padding: "2px 4px", color: "inherit" }}
              onMouseDown={(e) => e.stopPropagation()}
            >
              <option value="above" style={{ background: "#0d1526" }}>Above</option>
              <option value="below" style={{ background: "#0d1526" }}>Below</option>
            </select>
          </div>
          <div className="flex gap-1.5">
            <input
              type="number"
              value={newPrice}
              onChange={(e) => setNewPrice(e.target.value)}
              placeholder="Price..."
              className="text-xs font-mono bg-transparent outline-none flex-1 px-1.5 py-1"
              style={{ border: "1px solid rgba(255,255,255,0.12)", borderRadius: 4, color: "inherit" }}
              onMouseDown={(e) => e.stopPropagation()}
            />
            <button
              onClick={handleAdd}
              className="text-xs font-mono px-2 py-1 rounded"
              style={{ background: "rgba(30,111,239,0.2)", color: "#1e6fef", border: "1px solid rgba(30,111,239,0.3)" }}
              onMouseDown={(e) => e.stopPropagation()}
            >
              <Check size={12} />
            </button>
          </div>
        </div>
      )}

      {/* Alerts list */}
      <div className="flex-1 overflow-auto min-h-0">
        {alerts.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full gap-2" style={{ opacity: 0.3 }}>
            <BellOff size={24} />
            <span className="text-xs font-mono">No alerts set</span>
          </div>
        )}
        {alerts.map((alert) => (
          <div
            key={alert.id}
            className="flex items-center gap-2 px-2 text-xs font-mono"
            style={{
              height: 36,
              borderBottom: "1px solid rgba(255,255,255,0.03)",
              opacity: alert.triggered ? 0.4 : 1,
            }}
          >
            {/* Status dot */}
            <div
              className="size-1.5 rounded-full flex-shrink-0"
              style={{
                background: alert.triggered
                  ? "rgba(255,255,255,0.2)"
                  : alert.condition === "above"
                  ? "#00e5a0"
                  : "#ff4757",
              }}
            />

            {/* Symbol */}
            <span className="w-20 truncate" style={{ opacity: 0.9 }}>{alert.symbol}</span>

            {/* Condition */}
            <span style={{ opacity: 0.45, fontSize: 10 }}>{alert.condition}</span>

            {/* Price */}
            <span className="flex-1 text-right font-semibold" style={{ color: alert.condition === "above" ? "#00e5a0" : "#ff4757" }}>
              {alert.price.toLocaleString()}
            </span>

            {/* Triggered badge */}
            {alert.triggered && (
              <span className="text-xs px-1 rounded" style={{ background: "rgba(255,255,255,0.05)", color: "rgba(255,255,255,0.3)", fontSize: 9 }}>
                FIRED
              </span>
            )}

            {/* Actions */}
            <button
              onClick={() => handleToggle(alert.id)}
              className="opacity-40 hover:opacity-100 transition-opacity"
              onMouseDown={(e) => e.stopPropagation()}
            >
              {alert.triggered ? <Bell size={11} /> : <BellOff size={11} />}
            </button>
            <button
              onClick={() => handleDelete(alert.id)}
              className="opacity-30 hover:opacity-100 hover:text-red-400 transition-all"
              onMouseDown={(e) => e.stopPropagation()}
            >
              <Trash2 size={11} />
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}
