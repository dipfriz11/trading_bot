import { useState } from "react"
import { generateScreener, formatPrice, formatVolume } from "@/lib/mock-data"
import type { Widget } from "@/types/terminal"
import { ArrowUp, ArrowDown } from "lucide-react"

const rows = generateScreener()

type SortKey = "symbol" | "price" | "changePct" | "volume" | "marketCap"
type SortDir = "asc" | "desc"

export function ScreenerWidget(_props: { widget: Widget }) {
  const [sort, setSort] = useState<{ key: SortKey; dir: SortDir }>({ key: "marketCap", dir: "desc" })
  const [search, setSearch] = useState("")

  const sorted = [...rows]
    .filter((r) => r.symbol.toLowerCase().includes(search.toLowerCase()))
    .sort((a, b) => {
      const mul = sort.dir === "asc" ? 1 : -1
      if (sort.key === "symbol") return mul * a.symbol.localeCompare(b.symbol)
      return mul * (a[sort.key] - b[sort.key])
    })

  const toggleSort = (key: SortKey) => {
    setSort((s) => s.key === key ? { key, dir: s.dir === "asc" ? "desc" : "asc" } : { key, dir: "desc" })
  }

  const SortIcon = ({ k }: { k: SortKey }) => {
    if (sort.key !== k) return <span style={{ opacity: 0.2 }}>↕</span>
    return sort.dir === "asc" ? <ArrowUp size={9} /> : <ArrowDown size={9} />
  }

  const cols: Array<{ key: SortKey; label: string; align: "left" | "right" }> = [
    { key: "symbol", label: "Symbol", align: "left" },
    { key: "price", label: "Price", align: "right" },
    { key: "changePct", label: "24h %", align: "right" },
    { key: "volume", label: "Volume", align: "right" },
    { key: "marketCap", label: "MCap", align: "right" },
  ]

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Search */}
      <div className="px-2 py-1 flex-shrink-0" style={{ borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search symbol..."
          className="w-full text-xs font-mono bg-transparent outline-none px-2 py-1 rounded"
          style={{ border: "1px solid rgba(255,255,255,0.1)", color: "inherit" }}
          onMouseDown={(e) => e.stopPropagation()}
        />
      </div>

      {/* Headers */}
      <div className="flex-shrink-0 px-2 py-0.5 text-xs font-mono flex"
        style={{ opacity: 0.5, borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
        {cols.map((col) => (
          <button
            key={col.key}
            onClick={() => toggleSort(col.key)}
            className={`flex items-center gap-0.5 hover:opacity-100 transition-opacity ${col.align === "right" ? "ml-auto" : ""}`}
            style={{ flex: col.key === "symbol" ? "1 1 0" : undefined, minWidth: 60, justifyContent: col.align === "right" ? "flex-end" : "flex-start" }}
            onMouseDown={(e) => e.stopPropagation()}
          >
            {col.label} <SortIcon k={col.key} />
          </button>
        ))}
      </div>

      {/* Rows */}
      <div className="flex-1 overflow-auto min-h-0">
        {sorted.map((row) => (
          <div
            key={row.symbol}
            className="flex items-center px-2 text-xs font-mono hover:bg-white/5 transition-colors"
            style={{ height: 28, borderBottom: "1px solid rgba(255,255,255,0.025)" }}
          >
            <span style={{ flex: "1 1 0", minWidth: 0 }}>{row.symbol}</span>
            <span className="text-right" style={{ minWidth: 70 }}>{formatPrice(row.price)}</span>
            <span
              className="text-right"
              style={{
                minWidth: 60,
                color: row.changePct >= 0 ? "#00e5a0" : "#ff4757",
              }}
            >
              {row.changePct >= 0 ? "+" : ""}{row.changePct.toFixed(2)}%
            </span>
            <span className="text-right" style={{ minWidth: 60, opacity: 0.7 }}>{formatVolume(row.volume)}</span>
            <span className="text-right" style={{ minWidth: 60, opacity: 0.6 }}>{formatVolume(row.marketCap)}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
