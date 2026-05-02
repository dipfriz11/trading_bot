import { useState, useCallback, useEffect, useRef, useMemo, memo } from "react"
import { createPortal } from "react-dom"
import { ChevronDown, ChevronUp, Play, RotateCcw } from "lucide-react"
import type { GridConfig, GridMultiTpLevel, GridSharedTpSl } from "@/types/terminal"
import { DEFAULT_GRID_CONFIG, DEFAULT_GRID_SHARED_TP_SL } from "@/types/terminal"
import { TemplateBar } from "@/components/terminal/TemplateBar"
import { useTemplates } from "@/hooks/useTemplates"
import { useTerminal, useGridOrderEntry, useGridPreviewEntry, posKey } from "@/contexts/TerminalContext"
import { calcGridPrices, calcGridVisualization } from "@/lib/grid-math"
import { getPositionAnchors } from "@/lib/position-anchors"
import { nanoid } from "@/lib/nanoid"

// ─── Shared style constants ───────────────────────────────────────────────────

const inputBase: React.CSSProperties = {
  background: "rgba(255,255,255,0.04)",
  border: "1px solid rgba(255,255,255,0.1)",
  borderRadius: 4,
  color: "rgba(200,214,229,0.9)",
  padding: "3px 7px",
  fontSize: 11,
  fontFamily: "monospace",
  width: "100%",
  outline: "none",
}

const readonlyBase: React.CSSProperties = {
  ...inputBase,
  background: "rgba(30,111,239,0.05)",
  border: "1px solid rgba(30,111,239,0.12)",
  color: "rgba(120,170,255,0.8)",
  cursor: "default",
}

// ─── Primitive UI helpers ─────────────────────────────────────────────────────

function TinyTooltipIcon({ text, color }: { text: string; color?: string }) {
  const [pos, setPos] = useState<{ x: number; y: number } | null>(null)
  const anchorRef = useRef<HTMLSpanElement>(null)

  const openTooltip = () => {
    const r = anchorRef.current?.getBoundingClientRect()
    if (r) setPos({ x: r.left + r.width / 2, y: r.top })
  }

  return (
    <span
      ref={anchorRef}
      onMouseEnter={openTooltip}
      onMouseLeave={() => setPos(null)}
      onMouseDown={(e) => e.stopPropagation()}
      style={{ display: "inline-flex", alignItems: "center", cursor: "help", padding: "2px", pointerEvents: "auto" }}
    >
      <svg width="9" height="9" viewBox="0 0 10 10" fill="none" style={{ opacity: color ? 0.7 : 0.45, display: "block" }}>
        <circle cx="5" cy="5" r="4.5" stroke={color ?? "rgba(200,214,229,0.6)"} />
        <text x="5" y="7.5" textAnchor="middle" fontSize="6.5" fill={color ?? "rgba(200,214,229,0.8)"} fontFamily="monospace">?</text>
      </svg>
      {pos && createPortal(
        <div style={{
          position: "fixed",
          left: Math.max(8, Math.min(pos.x - 110, window.innerWidth - 248)),
          top: pos.y - 8,
          transform: "translateY(-100%)",
          zIndex: 99999, width: 220,
          background: "rgba(13,20,35,0.98)", border: `1px solid ${color ? "rgba(255,171,0,0.3)" : "rgba(30,111,239,0.25)"}`,
          borderRadius: 5, padding: "7px 9px",
          fontSize: 9, fontFamily: "monospace", color: "rgba(200,214,229,0.75)", lineHeight: 1.6,
          boxShadow: "0 4px 16px rgba(0,0,0,0.5)", pointerEvents: "none", whiteSpace: "normal",
        }}>
          {text}
        </div>,
        document.body
      )}
    </span>
  )
}

function NI({
  value, onChange, placeholder, title, min, suffix, label, labelColor, tooltip,
}: {
  value: number | string; onChange: (v: number) => void
  placeholder?: string; title?: string; min?: number; step?: number; suffix?: string; label?: string; labelColor?: string; tooltip?: string
}) {
  const ref = useRef<HTMLInputElement>(null)
  const [localVal, setLocalVal] = useState(String(value))
  const isFocused = useRef(false)

  useEffect(() => {
    if (!isFocused.current) setLocalVal(String(value))
  }, [value])

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const handler = (e: WheelEvent) => {
      e.preventDefault()
      e.stopPropagation()
      const delta = e.deltaY < 0 ? 1 : -1
      const current = parseFloat(String(value)) || 0
      const next = current + delta
      const result = min !== undefined ? Math.max(min, next) : next
      onChange(result)
      setLocalVal(String(result))
    }
    el.addEventListener("wheel", handler, { passive: false })
    return () => el.removeEventListener("wheel", handler)
  }, [onChange, min, value])

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const raw = e.target.value.replace(/[^0-9.-]/g, "")
    setLocalVal(raw)
  }

  const handleBlur = () => {
    isFocused.current = false
    const parsed = parseFloat(localVal)
    if (!isNaN(parsed)) {
      const result = min !== undefined ? Math.max(min, parsed) : parsed
      onChange(result)
      setLocalVal(String(result))
    } else {
      setLocalVal(String(value))
    }
  }

  const tag = suffix ?? label
  const tagW = tag ? tag.length * 5.5 + 8 : 0

  const tooltipExtraW = tooltip ? 12 : 0

  return (
    <div style={{ position: "relative" }}>
      <input
        ref={ref}
        type="text" inputMode="decimal" value={localVal}
        onChange={handleChange}
        onFocus={() => { isFocused.current = true }}
        onBlur={handleBlur}
        placeholder={placeholder ?? "0"} title={tooltip ? undefined : (title ?? placeholder)}
        style={{ ...inputBase, paddingRight: tag ? tagW + tooltipExtraW + 2 : undefined }}
        onMouseDown={(e) => e.stopPropagation()}
      />
      {tag && (
        <span style={{ position: "absolute", right: tooltip ? 16 : 5, top: "50%", transform: "translateY(-50%)", fontSize: 7.5, opacity: labelColor ? 1 : 0.32, fontFamily: "monospace", pointerEvents: "none", whiteSpace: "nowrap", letterSpacing: "0.03em", color: labelColor }}>
          {tag}
        </span>
      )}
      {tooltip && (
        <span style={{ position: "absolute", right: 5, top: "50%", transform: "translateY(-50%)", display: "flex", alignItems: "center" }}>
          <TinyTooltipIcon text={tooltip} color={labelColor} />
        </span>
      )}
    </div>
  )
}

function NITooltip({
  value, onChange, label, min, title, tooltip,
}: {
  value: number; onChange: (v: number) => void
  label?: string; min?: number; step?: number; title?: string; tooltip: string
}) {
  const [show, setShow] = useState(false)
  const [localVal, setLocalVal] = useState(String(value))
  const labelText = label ?? ""

  // Sync external value only when input is not focused
  const inputRef = useRef<HTMLInputElement>(null)
  useEffect(() => {
    if (document.activeElement !== inputRef.current) {
      setLocalVal(String(value))
    }
  }, [value])

  return (
    <div style={{ position: "relative" }}>
      <input
        ref={inputRef}
        type="text" inputMode="decimal" value={localVal}
        onChange={(e) => {
          const raw = e.target.value.replace(/[^0-9.]/g, "")
          setLocalVal(raw)
          const parsed = parseFloat(raw)
          if (!isNaN(parsed)) onChange(min !== undefined ? Math.max(min, parsed) : parsed)
        }}
        onBlur={() => {
          const parsed = parseFloat(localVal)
          if (isNaN(parsed) || localVal === "") {
            setLocalVal(String(value))
          }
        }}
        placeholder="0" title={title ?? label}
        style={{ ...inputBase, paddingRight: 60 }}
        onMouseDown={(e) => e.stopPropagation()}
      />
      {/* ? icon + label as one inline group, flush right */}
      <div style={{ position: "absolute", right: 5, top: "50%", transform: "translateY(-50%)", display: "flex", alignItems: "center", gap: 3, pointerEvents: "none" }}>
        <button
          onMouseEnter={() => setShow(true)}
          onMouseLeave={() => setShow(false)}
          onClick={() => setShow((s) => !s)}
          style={{ background: "none", border: "none", cursor: "pointer", padding: 0, display: "flex", alignItems: "center", pointerEvents: "auto" }}
          onMouseDown={(e) => e.stopPropagation()}
        >
          <svg width="9" height="9" viewBox="0 0 10 10" fill="none" style={{ opacity: 0.5 }}>
            <circle cx="5" cy="5" r="4.5" stroke="rgba(200,214,229,0.6)" />
            <text x="5" y="7.5" textAnchor="middle" fontSize="6.5" fill="rgba(200,214,229,0.8)" fontFamily="monospace">?</text>
          </svg>
        </button>
        <span style={{ fontSize: 7.5, opacity: 0.32, fontFamily: "monospace", whiteSpace: "nowrap", letterSpacing: "0.03em" }}>
          {labelText}
        </span>
      </div>
      {show && (
        <div style={{
          position: "absolute", top: "calc(100% + 4px)", left: 0, right: 0, zIndex: 999,
          background: "rgba(13,20,35,0.98)", border: "1px solid rgba(30,111,239,0.25)",
          borderRadius: 5, padding: "7px 9px",
          fontSize: 9, fontFamily: "monospace", color: "rgba(200,214,229,0.75)", lineHeight: 1.6,
          boxShadow: "0 4px 16px rgba(0,0,0,0.5)",
          pointerEvents: "none",
        }}>
          {tooltip}
        </div>
      )}
    </div>
  )
}

function LabelTooltip({ label, tooltip, color, align = "left" }: { label: string; tooltip: string; color?: string; align?: "left" | "right" }) {
  const [show, setShow] = useState(false)
  return (
    <div style={{ position: "relative", display: "inline-flex", alignItems: "center", gap: 3 }}>
      <span style={{ fontSize: 9, fontFamily: "monospace", letterSpacing: "0.08em", textTransform: "uppercase", color: color ?? "rgba(200,214,229,0.55)", fontWeight: 600 }}>
        {label}
      </span>
      <button
        onMouseEnter={() => setShow(true)}
        onMouseLeave={() => setShow(false)}
        style={{ background: "none", border: "none", cursor: "pointer", padding: 0, display: "flex", alignItems: "center", lineHeight: 1 }}
        onMouseDown={(e) => e.stopPropagation()}
      >
        <svg width="9" height="9" viewBox="0 0 10 10" fill="none" style={{ opacity: 0.45 }}>
          <circle cx="5" cy="5" r="4.5" stroke="rgba(200,214,229,0.6)" />
          <text x="5" y="7.5" textAnchor="middle" fontSize="6.5" fill="rgba(200,214,229,0.8)" fontFamily="monospace">?</text>
        </svg>
      </button>
      {show && (
        <div style={{
          position: "absolute", top: "calc(100% + 4px)",
          ...(align === "right" ? { right: 0 } : { left: 0 }),
          zIndex: 999, minWidth: 160, maxWidth: 220,
          background: "rgba(13,20,35,0.98)", border: "1px solid rgba(30,111,239,0.25)",
          borderRadius: 5, padding: "7px 9px",
          fontSize: 9, fontFamily: "monospace", color: "rgba(200,214,229,0.75)", lineHeight: 1.6,
          boxShadow: "0 4px 16px rgba(0,0,0,0.5)", pointerEvents: "none", whiteSpace: "normal",
        }}>
          {tooltip}
        </div>
      )}
    </div>
  )
}

function BudgetInput({
  value, onChange, mode, onModeChange, baseSymbol,
}: {
  value: number; onChange: (v: number) => void
  mode: "quote" | "base"; onModeChange: (m: "quote" | "base") => void
  baseSymbol: string
}) {
  const ref = useRef<HTMLInputElement>(null)
  const valueRef = useRef(value)
  valueRef.current = value

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const handler = (e: WheelEvent) => {
      e.preventDefault()
      e.stopPropagation()
      const delta = e.deltaY < 0 ? 1 : -1
      const next = Math.max(0, (typeof valueRef.current === "number" ? valueRef.current : 0) + delta)
      onChange(next)
    }
    el.addEventListener("wheel", handler, { passive: false })
    return () => el.removeEventListener("wheel", handler)
  }, [onChange])

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const raw = e.target.value.replace(/[^0-9.]/g, "")
    const parsed = parseFloat(raw)
    if (!isNaN(parsed)) onChange(Math.max(0, parsed))
    else if (raw === "" || raw === ".") onChange(0)
  }

  const label = mode === "quote" ? "USDT" : baseSymbol
  const labelW = label.length * 7 + 8

  return (
    <div style={{ position: "relative", flex: 1 }}>
      <input
        ref={ref}
        type="text" inputMode="decimal" value={value}
        onChange={handleChange}
        placeholder="1000" title={`Total budget in ${label}`}
        style={{ ...inputBase, paddingRight: labelW + 34 }}
        onMouseDown={(e) => e.stopPropagation()}
      />
      <div style={{ position: "absolute", right: 4, top: "50%", transform: "translateY(-50%)", display: "flex", alignItems: "center", gap: 2 }} onMouseDown={(e) => e.stopPropagation()}>
        <button
          onClick={() => onModeChange("quote")}
          title="Budget in USDT"
          style={{
            fontSize: 8, fontFamily: "monospace", padding: "1px 4px", borderRadius: 2, cursor: "pointer", border: "none",
            background: mode === "quote" ? "rgba(30,111,239,0.35)" : "rgba(255,255,255,0.06)",
            color: mode === "quote" ? "rgba(120,170,255,0.9)" : "rgba(200,214,229,0.4)",
            transition: "all 0.15s",
          }}
        >USDT</button>
        <button
          onClick={() => onModeChange("base")}
          title={`Budget in ${baseSymbol}`}
          style={{
            fontSize: 8, fontFamily: "monospace", padding: "1px 4px", borderRadius: 2, cursor: "pointer", border: "none",
            background: mode === "base" ? "rgba(30,111,239,0.35)" : "rgba(255,255,255,0.06)",
            color: mode === "base" ? "rgba(120,170,255,0.9)" : "rgba(200,214,229,0.4)",
            transition: "all 0.15s",
          }}
        >{baseSymbol}</button>
      </div>
    </div>
  )
}

function Seg<T extends string>({
  options, value, onChange, style,
}: { options: { v: T; label: string; title?: string; pro?: boolean }[]; value: T; onChange: (v: T) => void; style?: React.CSSProperties }) {
  return (
    <div className="flex rounded overflow-hidden" style={{ border: "1px solid rgba(255,255,255,0.1)", flexShrink: 0, ...style }}>
      {options.map((o) => (
        <button key={o.v} onClick={() => onChange(o.v)} title={o.title}
          style={{
            flex: 1, fontSize: 9, fontFamily: "monospace", padding: "2px 0",
            background: value === o.v ? "rgba(30,111,239,0.18)" : "transparent",
            color: value === o.v ? "#1e6fef" : "rgba(255,255,255,0.35)",
            border: "none", cursor: "pointer",
            fontWeight: value === o.v ? 700 : 400, letterSpacing: "0.04em",
          }}
          onMouseDown={(e) => e.stopPropagation()}
        >
          {o.label}{o.pro && <span style={{ fontSize: 7, marginLeft: 2, opacity: 0.5, color: "#ffaa00" }}>PRO</span>}
        </button>
      ))}
    </div>
  )
}

function MiniToggle({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <div
      onClick={() => onChange(!checked)}
      onMouseDown={(e) => e.stopPropagation()}
      style={{
        width: 32, height: 16, borderRadius: 8, flexShrink: 0, cursor: "pointer",
        background: checked ? "rgba(0,229,160,0.35)" : "rgba(255,255,255,0.1)",
        border: `1px solid ${checked ? "rgba(0,229,160,0.5)" : "rgba(255,255,255,0.15)"}`,
        position: "relative", transition: "background 0.15s",
      }}
    >
      <div style={{
        position: "absolute", top: 2, left: checked ? 16 : 2,
        width: 10, height: 10, borderRadius: "50%",
        background: checked ? "#00e5a0" : "rgba(255,255,255,0.4)",
        transition: "left 0.15s",
      }} />
    </div>
  )
}


function SectionHead({
  title, expanded, onToggle, badge, pro, rightSlot,
}: {
  title: string; expanded: boolean; onToggle: () => void
  badge?: React.ReactNode; pro?: boolean; rightSlot?: React.ReactNode
}) {
  return (
    <div
      className="flex items-center justify-between w-full"
      style={{ padding: "5px 0" }}
    >
      <button
        className="flex items-center gap-1.5"
        style={{ background: "transparent", border: "none", cursor: "pointer", padding: 0, flex: 1, textAlign: "left" }}
        onClick={onToggle}
        onMouseDown={(e) => e.stopPropagation()}
      >
        <span className="flex items-center gap-1.5" style={{ fontSize: 10, fontFamily: "monospace", color: "rgba(255,255,255,0.55)", textTransform: "uppercase", letterSpacing: "0.06em", fontWeight: 600 }}>
          {title}
          {pro && <span style={{ fontSize: 7, background: "rgba(255,170,0,0.2)", color: "#ffaa00", border: "1px solid rgba(255,170,0,0.3)", borderRadius: 2, padding: "0 3px" }}>PRO</span>}
          {badge}
        </span>
      </button>
      <div className="flex items-center gap-1.5">
        {rightSlot && (
          <div
            className="flex items-center gap-1.5"
            onClick={(e) => e.stopPropagation()}
            onMouseDown={(e) => e.stopPropagation()}
          >
            {rightSlot}
          </div>
        )}
        <button
          style={{ background: "transparent", border: "none", cursor: "pointer", padding: 0, display: "flex", alignItems: "center" }}
          onClick={onToggle}
          onMouseDown={(e) => e.stopPropagation()}
        >
          {expanded ? <ChevronUp size={9} style={{ opacity: 0.4 }} /> : <ChevronDown size={9} style={{ opacity: 0.4 }} />}
        </button>
      </div>
    </div>
  )
}

function Divider() {
  return <div style={{ height: 1, background: "rgba(255,255,255,0.05)", marginBottom: 6 }} />
}

function PctBtns({ onPct }: { onPct: (p: number) => void }) {
  return (
    <div className="flex gap-1">
      {[10, 20, 30, 50, 75, 100].map((p) => (
        <button key={p} onClick={() => onPct(p)} title={`${p}% of available balance`}
          style={{
            flex: 1, fontSize: 9, fontFamily: "monospace", padding: "1px 0",
            background: "rgba(255,255,255,0.04)", color: "rgba(255,255,255,0.4)",
            border: "1px solid rgba(255,255,255,0.07)", borderRadius: 3, cursor: "pointer",
          }}
          onMouseDown={(e) => e.stopPropagation()}
        >{p}%</button>
      ))}
    </div>
  )
}

// ─── Close % helpers ─────────────────────────────────────────────────────────

function distributeClose(count: number): number[] {
  const base = Math.floor(100 / count)
  const remainder = 100 - base * count
  return Array.from({ length: count }, (_, i) =>
    i === count - 1 ? base + remainder : base
  )
}

function rebalanceClose(levels: GridMultiTpLevel[], changedIndex: number, newValue: number): GridMultiTpLevel[] {
  if (levels.length <= 1) return [{ ...levels[0], closePercent: 100 }]
  const clamped = Math.min(100, Math.max(1, newValue))
  const lastIdx = levels.length - 1
  const updated = levels.map((l, i) =>
    i === changedIndex ? { ...l, closePercent: clamped } : l
  )
  if (changedIndex !== lastIdx) {
    const sumOthers = updated.slice(0, lastIdx).reduce((s, l) => s + l.closePercent, 0)
    const lastVal = Math.max(1, 100 - sumOthers)
    updated[lastIdx] = { ...updated[lastIdx], closePercent: lastVal }
  }
  return updated
}

// ─── Props ────────────────────────────────────────────────────────────────────

interface GridConfigTabProps {
  symbol?: string
  marketType?: "spot" | "futures"
  futuresSide?: "long" | "short"
  entryPrice?: number
  availableBalance?: number
  inOrders?: number
  leverage?: number
  onSideChange?: (side: "long" | "short") => void
  consoleWidgetId?: string
  activeChartId?: string | null
  accountId?: string
  exchangeId?: string
  isVisible?: boolean
}

// ─── Main component ───────────────────────────────────────────────────────────

export const GridConfigTab = memo(function GridConfigTab({
  symbol: externalSymbol,
  marketType = "futures",
  futuresSide: externalFuturesSide,
  entryPrice: externalEntryPrice,
  availableBalance = 10000,
  inOrders = 0,
  leverage: externalLeverage,
  onSideChange,
  consoleWidgetId,
  activeChartId,
  accountId,
  exchangeId,
  isVisible = true,
}: GridConfigTabProps) {
  // ── Multi-grid slots (separate per side) ─────────────────────────────────
  const [longSlots, setLongSlots] = useState<{ slotId: string }[]>(() => [{ slotId: nanoid() }])
  const [shortSlots, setShortSlots] = useState<{ slotId: string }[]>(() => [{ slotId: nanoid() }])
  const [activeLongIdx, setActiveLongIdx] = useState(0)
  const [activeShortIdx, setActiveShortIdx] = useState(0)
  // Persisted cfg per slot (keyed by "chartId\0slotId" to isolate per chart)
  const slotCfgMapRef = useRef<Record<string, GridConfig>>({})
  // Slot tabs scroll
  const slotScrollRef = useRef<HTMLDivElement>(null)
  const [slotCanScrollLeft, setSlotCanScrollLeft] = useState(false)
  const [slotCanScrollRight, setSlotCanScrollRight] = useState(false)
  // Cooldown after arrow click to prevent accidental tab/close-button clicks
  const slotScrollCooldownRef = useRef(false)
  const updateSlotScroll = () => {
    const el = slotScrollRef.current
    if (!el) return
    setSlotCanScrollLeft(el.scrollLeft > 2)
    setSlotCanScrollRight(el.scrollLeft + el.clientWidth < el.scrollWidth - 2)
  }
  useEffect(() => {
    // Wait for DOM paint before measuring
    const id = setTimeout(updateSlotScroll, 80)
    return () => clearTimeout(id)
  }, [longSlots.length, shortSlots.length])
  // Also update when the scroll container resizes (widget resize)
  useEffect(() => {
    const el = slotScrollRef.current
    if (!el) return
    const ro = new ResizeObserver(updateSlotScroll)
    ro.observe(el)
    updateSlotScroll()
    return () => ro.disconnect()
  }, [])

  const [cfg, _setCfg] = useState<GridConfig>({
    ...DEFAULT_GRID_CONFIG,
    symbol: externalSymbol ?? DEFAULT_GRID_CONFIG.symbol,
    side: externalFuturesSide ?? DEFAULT_GRID_CONFIG.side,
    entryPrice: externalEntryPrice ?? DEFAULT_GRID_CONFIG.entryPrice,
    leverage: externalLeverage ?? DEFAULT_GRID_CONFIG.leverage,
  })
  const setCfg = _setCfg
  // Always-current cfg ref for use in effects/callbacks without stale closure
  const cfgRef = useRef(cfg)

  // Derived slot helpers — computed after cfg is available
  const activeSide = cfg.side
  const gridSlots = activeSide === "long" ? longSlots : shortSlots
  const activeSlotIndex = activeSide === "long" ? activeLongIdx : activeShortIdx
  const setGridSlots = activeSide === "long" ? setLongSlots : setShortSlots
  const setActiveSlotIndex = activeSide === "long" ? setActiveLongIdx : setActiveShortIdx
  const activeSlot = gridSlots[activeSlotIndex] ?? gridSlots[0]
  cfgRef.current = cfg

  const { templates, saveTemplate, deleteTemplate } = useTemplates<GridConfig>("grid")
  const [activeTemplateId, setActiveTemplateId] = useState<string | null>(null)
  const [savedCfgJson, setSavedCfgJson] = useState<string | null>(null)

  const cfgForTemplate = { ...cfg, entryPrice: 0, symbol: "" }
  const isDirty = activeTemplateId !== null && savedCfgJson !== JSON.stringify(cfgForTemplate)

  const handleSelectTemplate = (t: { id: string; config: GridConfig }) => {
    setCfg((prev) => ({ ...t.config, symbol: prev.symbol, entryPrice: prev.entryPrice, side: prev.side, leverage: prev.leverage }))
    setActiveTemplateId(t.id)
    setSavedCfgJson(JSON.stringify({ ...t.config, entryPrice: 0, symbol: "" }))
    if (isPlacedRef.current) markGridPendingUpdate(consoleIdRef.current)
  }

  const handleSaveTemplate = (name: string) => {
    saveTemplate(name, cfgForTemplate)
    setTimeout(() => {
      const all = JSON.parse(localStorage.getItem("crypterm:templates:grid") ?? "[]") as Array<{ id: string; name: string }>
      const found = all.find((t) => t.name === name)
      if (found) { setActiveTemplateId(found.id); setSavedCfgJson(JSON.stringify(cfgForTemplate)) }
    }, 0)
  }

  // Init price range on chart/symbol change — mirrors the same pattern as the single-order
  // form in OrderConsoleWidget (initialisedKeyRef keyed on chartId:symbol).
  // Runs exactly once per unique chart+symbol combination; skip if key unchanged.
  const initialisedKeyRef = useRef<string>("")
  useEffect(() => {
    if (!externalSymbol) return
    const key = `${activeChartId ?? ""}:${externalSymbol}`
    if (initialisedKeyRef.current === key) return
    initialisedKeyRef.current = key
    const ref = externalEntryPrice && externalEntryPrice > 0 ? externalEntryPrice : 0
    const top = ref > 0 ? Math.round(ref * 1.03 * 100) / 100 : 0
    const bottom = ref > 0 ? Math.round(ref * 0.97 * 100) / 100 : 0
    // Mark as init change so pendingUpdate effect doesn't fire for this

    setCfg((p) => ({
      ...p,
      symbol: externalSymbol,
      entryPrice: ref > 0 ? ref : p.entryPrice,
      topPrice: top > 0 ? top : p.topPrice,
      bottomPrice: bottom > 0 ? bottom : p.bottomPrice,
    }))
  }, [activeChartId, externalSymbol, externalEntryPrice])

  // Update entryPrice live when market price changes (after initial init)
  const prevExternalPriceRef = useRef(externalEntryPrice)
  useEffect(() => {
    if (!externalEntryPrice || externalEntryPrice <= 0) return
    if (externalEntryPrice === prevExternalPriceRef.current) return
    prevExternalPriceRef.current = externalEntryPrice
    // Only update entryPrice if the key has already been initialised (skip on first run)
    if (!initialisedKeyRef.current) return
    setCfg((p) => {
      if (p.entryPrice === externalEntryPrice) return p
      // Recalculate top/bottom proportionally if they were auto-set (±3%)
      const ratio = p.entryPrice > 0 ? externalEntryPrice / p.entryPrice : 1
      const newTop = Math.round(p.topPrice * ratio * 100) / 100
      const newBottom = Math.round(p.bottomPrice * ratio * 100) / 100
      return { ...p, entryPrice: externalEntryPrice, topPrice: newTop, bottomPrice: newBottom }
    })
  }, [externalEntryPrice])

  useEffect(() => {
    if (externalLeverage && externalLeverage > 0) {
      setCfg((p) => p.leverage === externalLeverage ? p : { ...p, leverage: externalLeverage })
    }
  }, [externalLeverage])
  useEffect(() => {
    if (externalFuturesSide) {
      setCfg((p) => p.side === externalFuturesSide ? p : { ...p, side: externalFuturesSide })
    }
  }, [externalFuturesSide])


  // Pro mode toggle + multi-position mode
  const [proMode, setProMode] = useState(false)
  // When false (default): TP/SL is shared across all grids on the same side.
  // When true (Pro + multiPos): each slot has independent TP/SL (legacy per-slot behavior).
  const [multiPositionMode, setMultiPositionMode] = useState(false)

  // Shared TP/SL state per side — used when multiPositionMode is OFF
  const [longSharedTpSl, setLongSharedTpSl] = useState<GridSharedTpSl>({ ...DEFAULT_GRID_SHARED_TP_SL })
  const [shortSharedTpSl, setShortSharedTpSl] = useState<GridSharedTpSl>({ ...DEFAULT_GRID_SHARED_TP_SL })
  const activeSideSharedTpSl = cfg.side === "long" ? longSharedTpSl : shortSharedTpSl

  // Keys that belong to TP/SL config — used to route updates to shared state
  const TP_SL_KEYS = new Set<keyof GridConfig>([
    "tpEnabled", "tpMode", "tpPercent", "tpClosePercent",
    "multiTpEnabled", "multiTpCount", "multiTpLevels",
    "tpRepositionEnabled", "perLevelTpEnabled", "perLevelTpGroups",
    "slEnabled", "slMode", "slPercent", "slClosePercent",
    "resetTpEnabled", "resetTpTriggerLevels", "defaultResetTpPercent",
    "defaultResetTpClosePercent", "resetTpRebuildTail",
    "resetTpPerLevelEnabled", "resetTpPerLevelSettings",
  ])

  // Effective TP/SL values: shared when !multiPositionMode, from cfg otherwise
  const tpSl: GridSharedTpSl = multiPositionMode
    ? {
        tpEnabled: cfg.tpEnabled,
        tpMode: cfg.tpMode,
        tpPercent: cfg.tpPercent,
        tpClosePercent: cfg.tpClosePercent,
        multiTpEnabled: cfg.multiTpEnabled,
        multiTpCount: cfg.multiTpCount,
        multiTpLevels: cfg.multiTpLevels,
        tpRepositionEnabled: cfg.tpRepositionEnabled,
        perLevelTpEnabled: cfg.perLevelTpEnabled,
        perLevelTpGroups: cfg.perLevelTpGroups,
        slEnabled: cfg.slEnabled,
        slMode: cfg.slMode,
        slPercent: cfg.slPercent,
        slClosePercent: cfg.slClosePercent,
        resetTpEnabled: cfg.resetTpEnabled,
        resetTpTriggerLevels: cfg.resetTpTriggerLevels,
        defaultResetTpPercent: cfg.defaultResetTpPercent,
        defaultResetTpClosePercent: cfg.defaultResetTpClosePercent,
        resetTpRebuildTail: cfg.resetTpRebuildTail,
        resetTpPerLevelEnabled: cfg.resetTpPerLevelEnabled,
        resetTpPerLevelSettings: cfg.resetTpPerLevelSettings,
      }
    : activeSideSharedTpSl

  // Keep cfg TP/SL fields in sync with shared state when !multiPositionMode
  // so that calcGridVisualization always works correctly from cfg
  useEffect(() => {
    if (multiPositionMode) return
    setCfg((p) => {
      const s = activeSideSharedTpSl
      // Bail out (return same reference) if all TP/SL scalar fields match
      // and array fields are reference-equal (they come from shared state)
      if (
        p.tpEnabled === s.tpEnabled && p.tpMode === s.tpMode &&
        p.tpPercent === s.tpPercent && p.tpClosePercent === s.tpClosePercent &&
        p.multiTpEnabled === s.multiTpEnabled && p.multiTpCount === s.multiTpCount &&
        p.multiTpLevels === s.multiTpLevels &&
        p.tpRepositionEnabled === s.tpRepositionEnabled &&
        p.perLevelTpEnabled === s.perLevelTpEnabled &&
        p.perLevelTpGroups === s.perLevelTpGroups &&
        p.slEnabled === s.slEnabled && p.slMode === s.slMode &&
        p.slPercent === s.slPercent && p.slClosePercent === s.slClosePercent &&
        p.resetTpEnabled === s.resetTpEnabled &&
        p.resetTpTriggerLevels === s.resetTpTriggerLevels &&
        p.defaultResetTpPercent === s.defaultResetTpPercent &&
        p.defaultResetTpClosePercent === s.defaultResetTpClosePercent &&
        p.resetTpRebuildTail === s.resetTpRebuildTail &&
        p.resetTpPerLevelEnabled === s.resetTpPerLevelEnabled &&
        p.resetTpPerLevelSettings === s.resetTpPerLevelSettings
      ) return p
      return { ...p, ...s }
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeSideSharedTpSl, multiPositionMode])

  const [availTooltip, setAvailTooltip] = useState(false)
  // Collapsed sections
  const [open, setOpen] = useState({
    entry: true,
    gridSetup: true,
    summary: false,
    trail: true,
    tp: true,
    sl: true,
    resetTp: false,
    gridTable: false,
    configJson: false,
    perLevelGroups: true,
  })
  const tog = (k: keyof typeof open) => setOpen((p) => ({ ...p, [k]: !p[k] }))

  // Auto-sync perLevelTpGroups count with ordersCount when perLevelTpEnabled
  useEffect(() => {
    if (!tpSl.perLevelTpEnabled) return
    const n = cfg.ordersCount
    const cur = tpSl.perLevelTpGroups
    if (cur.length === n) return
    if (cur.length < n) {
      const extra = Array.from({ length: n - cur.length }, (_, i) => ({
        afterLevel: cur.length + i + 1,
        tpCount: 1,
        levels: [{ tpPercent: 1.0, closePercent: 100 }],
        resetTpEnabled: false,
      }))
      upd("perLevelTpGroups", [...cur, ...extra])
    } else {
      upd("perLevelTpGroups", cur.slice(0, n))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cfg.ordersCount, tpSl.perLevelTpEnabled])

  const freeMargin = Math.max(0, availableBalance - inOrders)
  const availableForGrid = marketType === "futures" ? freeMargin * cfg.leverage : freeMargin

  const handlePct = (pct: number) => {
    const amt = parseFloat(((pct / 100) * availableForGrid).toFixed(2))
    upd("totalQuote", amt)
  }

  // ── Grid chart integration ────────────────────────────────────────────────
  const { setGridPreview, placeGridOrders, cancelGridOrders, cancelGridPreview, applyGridTpSl, gridOrdersRef, markGridPendingUpdate, clearGridPendingUpdate, positions } = useTerminal()
  const baseConsoleId = consoleWidgetId ?? "__grid_console__"
  // Each console+chart+side+slot combination is its own independent slot
  const consoleId = `${baseConsoleId}:${activeChartId ?? ""}:${cfg.side}:${activeSlot?.slotId ?? "0"}`
  // Subscribe only to this specific consoleId to avoid re-renders from other grids
  const currentGridState = useGridOrderEntry(consoleId)
  const currentPreviewState = useGridPreviewEntry(consoleId)
  const isPlaced = !!currentGridState
  const hasPendingUpdate = isPlaced && currentGridState?.pendingUpdate

  // Lock grid editing only if THIS slot has fills — not the whole position —
  // so a second grid slot isn't blocked by fills from the first slot.
  const activePositionKey = posKey(accountId ?? "", exchangeId ?? "", marketType ?? "futures", cfg.symbol, cfg.side)
  const activePosition = positions[activePositionKey]
  const positionHasFills = (activePosition?.orders ?? []).some(
    (o) => o.gridConsoleId === consoleId && o.status === "filled"
  )
  // For drag-sync: use placed state when placed, otherwise use preview state
  const currentDragState = currentGridState ?? currentPreviewState

  // Refs so that upd() and drag-sync effects can call markGridPendingUpdate
  // without capturing stale closures over isPlaced/consoleId
  const isPlacedRef = useRef(false)
  const consoleIdRef = useRef("")
  isPlacedRef.current = isPlaced
  consoleIdRef.current = consoleId

  // Refs for shared TP/SL routing — avoids stale closures in upd()
  const multiPositionModeRef = useRef(multiPositionMode)
  multiPositionModeRef.current = multiPositionMode
  const activeSideRef = useRef(cfg.side)
  activeSideRef.current = cfg.side
  const setLongSharedTpSlRef = useRef(setLongSharedTpSl)
  setLongSharedTpSlRef.current = setLongSharedTpSl
  const setShortSharedTpSlRef = useRef(setShortSharedTpSl)
  setShortSharedTpSlRef.current = setShortSharedTpSl
  // Slot refs so setTimeout callbacks always see latest slot arrays
  const longSlotsRef = useRef(longSlots)
  longSlotsRef.current = longSlots
  const shortSlotsRef = useRef(shortSlots)
  shortSlotsRef.current = shortSlots
  // Per-chart slot state storage: keyed by chartId
  const slotsStateByChartRef = useRef<Record<string, {
    longSlots: { slotId: string }[]
    shortSlots: { slotId: string }[]
    activeLongIdx: number
    activeShortIdx: number
  }>>({})
  // Stable ref for active indices so the chart-switch effect can read current values
  const activeLongIdxRef = useRef(activeLongIdx)
  activeLongIdxRef.current = activeLongIdx
  const activeShortIdxRef = useRef(activeShortIdx)
  activeShortIdxRef.current = activeShortIdx
  // Stable ref for activeChartId so callbacks don't form stale closures
  const activeChartIdRef = useRef(activeChartId)
  activeChartIdRef.current = activeChartId
  // Helper: build slotCfgMapRef key scoped to current chart
  const slotKey = (slotId: string) => `${activeChartIdRef.current ?? ""}:${slotId}`

  const TP_SL_KEYS_REF = useRef(TP_SL_KEYS)
  TP_SL_KEYS_REF.current = TP_SL_KEYS

  const upd = useCallback(<K extends keyof GridConfig>(key: K, val: GridConfig[K]) => {
    if (!multiPositionModeRef.current && TP_SL_KEYS_REF.current.has(key)) {
      // Route to shared TP/SL state for the active side
      const setter = activeSideRef.current === "long" ? setLongSharedTpSlRef.current : setShortSharedTpSlRef.current
      setter((p) => ({ ...p, [key]: val }))
      // Also update cfg so preview recalculates immediately
      setCfg((p) => ({ ...p, [key]: val }))
    } else if (key === "stepPercent") {
      // When user manually sets stepPercent, clear lastOffsetPercent so stepPercent takes effect
      setCfg((p) => ({ ...p, stepPercent: val as number, lastOffsetPercent: 0 }))
    } else if (key === "lastOffsetPercent") {
      // When user sets lastOffsetPercent, also recompute stepPercent to keep it consistent
      setCfg((p) => {
        const n = Math.max(2, p.ordersCount)
        const entryPrice = p.entryPrice > 0 ? p.entryPrice : 67000
        const isLong = p.side === "long"
        const firstOffset = p.firstOffsetPercent / 100
        const lastOffset = (val as number) / 100
        const firstPrice = isLong ? entryPrice * (1 - firstOffset) : entryPrice * (1 + firstOffset)
        const lastPrice = isLong ? entryPrice * (1 - lastOffset) : entryPrice * (1 + lastOffset)
        const ratio = firstPrice > 0 ? lastPrice / firstPrice : 1
        let newStep = p.stepPercent
        if (ratio > 0 && ratio !== 1) {
          const rawStep = isLong
            ? (1 - Math.pow(ratio, 1 / (n - 1))) * 100
            : (Math.pow(ratio, 1 / (n - 1)) - 1) * 100
          newStep = Math.max(0.01, Math.round(rawStep * 100) / 100)
        }
        return { ...p, lastOffsetPercent: val as number, stepPercent: newStep }
      })
    } else {
      setCfg((p) => ({ ...p, [key]: val }))
    }
    if (isPlacedRef.current) markGridPendingUpdate(consoleIdRef.current)
    // Cancel preview immediately when totalQuote is cleared to zero
    if (key === "totalQuote" && (val as number) <= 0) {
      cancelGridPreview(consoleIdRef.current)
    }
  }, [markGridPendingUpdate, cancelGridPreview])

  // Ref always pointing at latest cfg — used by chart-switch effect to pre-sync before saving
  const prevCfgRef = useRef(cfg)

  // Per-chart per-side cfg storage: keyed by "chartId:side"
  // Saves full cfg when leaving a chart/side and restores it when returning
  const cfgByChartSideRef = useRef<Partial<Record<string, GridConfig>>>({})
  const prevChartSideKeyRef = useRef(`${activeChartId ?? ""}:${cfg.side}`)

  // Track side switches (within the same chart) — save/restore cfg.
  // Runs only when cfg.side changes; does NOT trigger when activeChartId changes
  // (that is handled by the chart-switch effect below, which fires first).
  const prevSideRef = useRef<"long" | "short">(cfg.side)
  useEffect(() => {
    const prevSide = prevSideRef.current
    if (prevSide === cfg.side) return
    // Save cfg for the side we're leaving, preserving the correct side value
    const prevKey = `${activeChartId ?? ""}:${prevSide}`
    cfgByChartSideRef.current[prevKey] = { ...cfgRef.current, side: prevSide }
    prevSideRef.current = cfg.side
    orderIdRefs.current = []
    // Restore cfg for the side we're switching to, if previously saved
    const savedKey = `${activeChartId ?? ""}:${cfg.side}`
    const saved = cfgByChartSideRef.current[savedKey]
    if (saved) {
      setCfg((p) => ({
        ...saved,
        symbol: p.symbol,
        entryPrice: p.entryPrice,
        leverage: p.leverage,
        side: cfg.side,
      }))
      if (isPlacedRef.current) markGridPendingUpdate(consoleIdRef.current)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cfg.side])

  // Track chart switches — save cfg + slot state for old chart, restore for new chart.
  // Depends only on activeChartId so it never fires on side-only changes.
  useEffect(() => {
    const currentSide = prevSideRef.current
    const newKey = `${activeChartId ?? ""}:${currentSide}`
    const oldKey = prevChartSideKeyRef.current
    if (oldKey === newKey) return

    // Derive old chartId from oldKey (everything before the last ":")
    const oldChartId = oldKey.split(":").slice(0, -1).join(":")

    // Save cfg for the chart+side we're leaving
    const oldSide = oldKey.split(":").pop() as "long" | "short"
    cfgByChartSideRef.current[oldKey] = { ...cfgRef.current, side: oldSide }

    // Save slot state for the chart we're leaving
    slotsStateByChartRef.current[oldChartId] = {
      longSlots: longSlotsRef.current,
      shortSlots: shortSlotsRef.current,
      activeLongIdx: activeLongIdxRef.current,
      activeShortIdx: activeShortIdxRef.current,
    }

    prevChartSideKeyRef.current = newKey
    orderIdRefs.current = []

    // Restore slot state for the new chart (or reset to a single fresh slot per side)
    const newChartId = activeChartId ?? ""
    const savedSlots = slotsStateByChartRef.current[newChartId]
    if (savedSlots) {
      setLongSlots(savedSlots.longSlots)
      setShortSlots(savedSlots.shortSlots)
      setActiveLongIdx(savedSlots.activeLongIdx)
      setActiveShortIdx(savedSlots.activeShortIdx)
    } else {
      setLongSlots([{ slotId: nanoid() }])
      setShortSlots([{ slotId: nanoid() }])
      setActiveLongIdx(0)
      setActiveShortIdx(0)
    }

    const saved = cfgByChartSideRef.current[newKey]
    if (saved) {
      setCfg(saved)
      prevCfgRef.current = saved
      initialisedKeyRef.current = `${activeChartId ?? ""}:${saved.symbol}`
    }
    const newConsoleId = `${baseConsoleId}:${activeChartId ?? ""}:${currentSide}`
    clearGridPendingUpdate(newConsoleId)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeChartId])

  // Stable ID refs for order levels
  const orderIdRefs = useRef<string[]>([])

  // Sync ordersCount when a placed entry is removed from the chart (x button)
  const chartOrdersLen = currentGridState?.orders.length
  const prevChartOrdersLenRef = useRef<number | undefined>(undefined)
  useEffect(() => {
    if (chartOrdersLen === undefined) { prevChartOrdersLenRef.current = undefined; return }
    if (prevChartOrdersLenRef.current !== undefined && chartOrdersLen < prevChartOrdersLenRef.current) {
      setCfg((p) => ({ ...p, ordersCount: chartOrdersLen }))
      orderIdRefs.current = currentGridState!.orders.map((o) => o.id)
    }
    prevChartOrdersLenRef.current = chartOrdersLen
  }, [chartOrdersLen])

  // Sync ordersCount when a preview entry is removed from the chart (x button)
  const chartPreviewOrdersLen = currentPreviewState?.orders.length
  const prevChartPreviewOrdersLenRef = useRef<number | undefined>(undefined)
  useEffect(() => {
    if (chartPreviewOrdersLen === undefined) { prevChartPreviewOrdersLenRef.current = undefined; return }
    if (prevChartPreviewOrdersLenRef.current !== undefined && chartPreviewOrdersLen < prevChartPreviewOrdersLenRef.current) {
      setCfg((p) => ({ ...p, ordersCount: chartPreviewOrdersLen }))
    }
    prevChartPreviewOrdersLenRef.current = chartPreviewOrdersLen
  }, [chartPreviewOrdersLen])

  // ── SL sync: chart x → form deactivation ────────────────────────────────
  // When slPrice is nulled out on the chart (user clicked x), deactivate slEnabled in form
  const chartSlPrice = currentDragState?.slPrice
  const prevChartSlPriceRef = useRef<number | null | undefined>(undefined)
  useEffect(() => {
    // React whenever slPrice transitions from non-null to null (user clicked x on chart)
    if (prevChartSlPriceRef.current !== undefined && prevChartSlPriceRef.current !== null && chartSlPrice === null) {
      setCfg((p) => ({ ...p, slEnabled: false }))
      // Also update shared state so the shared→cfg sync effect doesn't overwrite this
      const setter = activeSideRef.current === "long" ? setLongSharedTpSlRef.current : setShortSharedTpSlRef.current
      setter((p) => ({ ...p, slEnabled: false }))
    }
    prevChartSlPriceRef.current = chartSlPrice
  }, [chartSlPrice])

  // When slEnabled is turned ON while placed → immediately apply SL to chart from config
  const prevSlEnabledRef = useRef(cfg.slEnabled)
  useEffect(() => {
    const wasEnabled = prevSlEnabledRef.current
    prevSlEnabledRef.current = cfg.slEnabled
    if (!isPlaced || !activeChartId) return
    if (!isSharedTpSlOwner()) return
    if (!wasEnabled && cfg.slEnabled) {
      const viz = calcGridVisualization(cfg)
      expectedSlPriceRef.current = viz.slPrice
      applyGridTpSl(consoleId, { slPrice: viz.slPrice })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cfg.slEnabled, isPlaced])

  // ── TP sync: chart x button on individual TP lines ──────────────────────
  // Stabilize by value so array-reference churn in context doesn't re-fire effects
  const rawChartTpLevels = currentDragState?.tpLevels
  const chartTpLevels = useMemo(
    () => rawChartTpLevels,
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [rawChartTpLevels?.join(",") ?? ""]
  )
  const chartTpLevelsLen = chartTpLevels?.length
  const prevChartTpLevelsLenRef = useRef<number | undefined>(undefined)
  // Track how many TPs were active at placement so we know when "all" are removed
  const placedTpCountRef = useRef<number>(0)
  useEffect(() => {
    if (isPlaced && currentGridState) {
      if (chartTpLevelsLen !== undefined && chartTpLevelsLen > 0) {
        placedTpCountRef.current = chartTpLevelsLen
      }
    }
  }, [isPlaced, chartTpLevelsLen])

  useEffect(() => {
    const prev = prevChartTpLevelsLenRef.current
    prevChartTpLevelsLenRef.current = chartTpLevelsLen

    if (prev === undefined || chartTpLevelsLen === undefined) return
    // Count decreased — user removed a TP on the chart
    if (chartTpLevelsLen >= prev) return

    if (chartTpLevelsLen === 0) {
      // All TPs removed → deactivate block; also update shared state to prevent overwrite
      setCfg((p) => ({ ...p, tpEnabled: false }))
      const setter = activeSideRef.current === "long" ? setLongSharedTpSlRef.current : setShortSharedTpSlRef.current
      setter((p) => ({ ...p, tpEnabled: false }))
      return
    }

    // Partial removal — user removed one TP on the chart
    const remaining = chartTpLevels ?? []
    let newTpPercent: number | null = null
    let newMultiLevels: { tpPercent: number; closePercent: number }[] | null = null
    setCfg((p) => {
      const isLong = p.side === "long"
      const viz = calcGridVisualization(p)
      const firstOrderPrice = viz.orders[0]?.price ?? p.entryPrice
      const basePrice = p.tpMode === "avg_entry" ? firstOrderPrice : p.entryPrice
      const n = remaining.length
      const base = Math.floor(100 / n)
      const remainder = 100 - base * n
      const newLevels = remaining.map((price, i) => {
        const pct = isLong
          ? (price / basePrice - 1) * 100
          : (1 - price / basePrice) * 100
        const closePercent = i === n - 1 ? base + remainder : base
        return { tpPercent: Math.max(0.01, Math.round(pct * 100) / 100), closePercent }
      })
      newTpPercent = newLevels[0]?.tpPercent ?? p.tpPercent
      newMultiLevels = newLevels
      return {
        ...p,
        tpPercent: newTpPercent,
        multiTpCount: n,
        multiTpLevels: newLevels,
        multiTpEnabled: n > 1,
      }
    })
    // Also sync shared state to prevent shared→cfg effect from overwriting
    if (newTpPercent !== null && newMultiLevels !== null) {
      const tp = newTpPercent
      const levels = newMultiLevels as { tpPercent: number; closePercent: number }[]
      const n = levels.length
      const setter = activeSideRef.current === "long" ? setLongSharedTpSlRef.current : setShortSharedTpSlRef.current
      setter((p) => ({ ...p, tpPercent: tp, multiTpCount: n, multiTpLevels: levels, multiTpEnabled: n > 1 }))
    }
  }, [chartTpLevelsLen, isPlaced])

  // When tpEnabled is turned ON while placed → immediately apply TP to chart from config
  const prevTpEnabledRef = useRef(cfg.tpEnabled)
  useEffect(() => {
    const wasEnabled = prevTpEnabledRef.current
    prevTpEnabledRef.current = cfg.tpEnabled
    if (!isPlaced || !activeChartId) return
    if (!isSharedTpSlOwner()) return
    if (!wasEnabled && cfg.tpEnabled) {
      const viz = calcGridVisualization(cfg)
      applyGridTpSl(consoleId, { tpPrice: viz.tpPrice, tpLevels: viz.tpLevels })
      placedTpCountRef.current = viz.tpLevels.length
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cfg.tpEnabled, isPlaced])

  // ── SL drag sync: chart drag → update cfg.slPercent ────────────────────
  const prevChartSlPriceValueRef = useRef<number | null | undefined>(undefined)
  useEffect(() => {
    const prev = prevChartSlPriceValueRef.current
    prevChartSlPriceValueRef.current = chartSlPrice ?? null
    // Only react to non-null→non-null changes (i.e. drag moved the price)
    if (prev === undefined || prev === null || chartSlPrice === null || chartSlPrice === undefined) return
    if (Math.abs(chartSlPrice - prev) < 1e-8) return
    // Skip if this is a form-driven update (form just pushed this exact slPrice to the chart)
    const expSl = expectedSlPriceRef.current
    if (expSl !== undefined && expSl !== null && Math.abs(chartSlPrice - expSl) < 1e-8) return
    // Compute the new slPercent from the dragged price
    let computedSlPercent: number | null = null
    setCfg((p) => {
      const viz = calcGridVisualization(p)
      const isLong = p.side === "long"
      let basePrice: number
      if (p.slMode === "avg_entry") {
        basePrice = viz.avgEntryEstimate > 0 ? viz.avgEntryEstimate : p.entryPrice
      } else if (p.slMode === "extreme_order") {
        const prices = viz.orders.map((o) => o.price)
        basePrice = prices.length > 0
          ? (isLong ? Math.min(...prices) : Math.max(...prices))
          : p.entryPrice
      } else {
        // default: first order price
        basePrice = viz.orders[0]?.price ?? p.entryPrice
      }
      if (basePrice === 0) return p
      const newPct = isLong
        ? (1 - chartSlPrice / basePrice) * 100
        : (chartSlPrice / basePrice - 1) * 100
      computedSlPercent = Math.max(0.01, Math.round(newPct * 100) / 100)
      return { ...p, slPercent: computedSlPercent }
    })
    // In non-multipos mode, drag must also update shared state so the form shows the new value
    if (!multiPositionModeRef.current && computedSlPercent !== null) {
      const setter = activeSideRef.current === "long" ? setLongSharedTpSlRef.current : setShortSharedTpSlRef.current
      const pct = computedSlPercent
      setter((p) => ({ ...p, slPercent: pct }))
    }
    if (isPlacedRef.current) markGridPendingUpdate(consoleIdRef.current)
  }, [chartSlPrice])

  // Expected prices that form last pushed to chart — used to distinguish form-driven vs drag-driven changes
  const expectedFirstPriceRef = useRef<number | undefined>(undefined)
  const expectedLastPriceRef = useRef<number | undefined>(undefined)
  const expectedSlPriceRef = useRef<number | null | undefined>(undefined)

  // ── TP drag sync: chart drag → update cfg tpPercent / multiTpLevels ─────
  const prevChartTpLevelsRef = useRef<number[] | undefined>(undefined)

  // Reset all prev-value tracking refs when switching chart (consoleId changes).
  // Without this, stale prev-values from the old chart trigger spurious sync effects
  // (e.g. computing SL % against a BTC price when now on AVAX chart).
  const prevConsoleIdRef = useRef(consoleId)
  if (prevConsoleIdRef.current !== consoleId) {
    prevConsoleIdRef.current = consoleId
    orderIdRefs.current = []
    prevChartOrdersLenRef.current = undefined
    prevChartSlPriceRef.current = undefined
    prevChartTpLevelsLenRef.current = undefined
    prevChartSlPriceValueRef.current = undefined
    prevChartTpLevelsRef.current = undefined
    expectedFirstPriceRef.current = undefined
    expectedLastPriceRef.current = undefined
    expectedSlPriceRef.current = undefined
    // Reset init flag so pendingUpdate effect skips the first settle cycle on the new chart

  }

  useEffect(() => {
    const prev = prevChartTpLevelsRef.current
    const cur = chartTpLevels
    prevChartTpLevelsRef.current = cur ? [...cur] : undefined
    if (!prev || !cur || prev.length !== cur.length || cur.length === 0) return
    // Check if any price changed
    const changed = cur.some((p, i) => Math.abs(p - prev[i]) > 1e-8)
    if (!changed) return
    // Sync cfg tpPercent from first TP, and multiTpLevels from all
    let computedTpPercent: number | null = null
    let computedMultiLevels: { tpPercent: number; closePercent: number }[] | null = null
    setCfg((p) => {
      const isLong = p.side === "long"
      const viz = calcGridVisualization(p)
      const firstOrderPrice = viz.orders[0]?.price ?? p.entryPrice
      const basePrice = p.tpMode === "avg_entry" ? firstOrderPrice : p.entryPrice
      if (basePrice === 0) return p
      const newMultiLevels = cur.map((price, i) => {
        const pct = isLong
          ? (price / basePrice - 1) * 100
          : (1 - price / basePrice) * 100
        return {
          tpPercent: Math.max(0.01, Math.round(pct * 100) / 100),
          closePercent: p.multiTpLevels[i]?.closePercent ?? Math.floor(100 / cur.length),
        }
      })
      computedTpPercent = newMultiLevels[0]?.tpPercent ?? p.tpPercent
      computedMultiLevels = newMultiLevels
      return {
        ...p,
        tpPercent: computedTpPercent,
        multiTpLevels: newMultiLevels,
      }
    })
    // In non-multipos mode, drag must also update shared state so the form shows the new value
    if (!multiPositionModeRef.current && computedTpPercent !== null && computedMultiLevels !== null) {
      const setter = activeSideRef.current === "long" ? setLongSharedTpSlRef.current : setShortSharedTpSlRef.current
      const tp = computedTpPercent
      const levels = computedMultiLevels
      setter((p) => ({ ...p, tpPercent: tp, multiTpLevels: levels }))
    }
    if (isPlacedRef.current) markGridPendingUpdate(consoleIdRef.current)
  }, [chartTpLevels])

  // Sync form fields when first or last grid order is dragged on the chart
  // Stabilize by value to avoid firing when context creates a new array reference with same prices
  const rawChartFirstPrice = currentDragState?.orders[0]?.price
  const rawChartLastPrice = currentDragState?.orders.length
    ? currentDragState.orders[currentDragState.orders.length - 1]?.price
    : undefined
  const chartFirstPrice = useMemo(() => rawChartFirstPrice, [rawChartFirstPrice])
  const chartLastPrice = useMemo(() => rawChartLastPrice, [rawChartLastPrice])
  useEffect(() => {
    if (chartFirstPrice === undefined || chartLastPrice === undefined) return

    // Skip if this matches what the form itself pushed (form-driven update, not a drag)
    const expFirst = expectedFirstPriceRef.current
    const expLast = expectedLastPriceRef.current
    const firstChanged = expFirst === undefined || Math.abs(chartFirstPrice - expFirst) > 0.001
    const lastChanged = expLast === undefined || Math.abs(chartLastPrice - expLast) > 0.001
    if (!firstChanged && !lastChanged) return

    setCfg((p) => {
      const entryPrice = p.entryPrice > 0 ? p.entryPrice : 67000
      const isLong = p.side === "long"

      if (p.placementMode === "price_range") {
        // Long:  orders[0]=topPrice, orders[N-1]=bottomPrice
        // Short: orders[0]=bottomPrice, orders[N-1]=topPrice
        const newTop = isLong ? chartFirstPrice : chartLastPrice
        const newBottom = isLong ? chartLastPrice : chartFirstPrice
        if (Math.abs(newTop - p.topPrice) < 0.001 && Math.abs(newBottom - p.bottomPrice) < 0.001) return p
        return { ...p, topPrice: Math.round(newTop * 100) / 100, bottomPrice: Math.round(newBottom * 100) / 100 }
      } else {
        // step_percent mode
        const rawFirstOffset = isLong
          ? (entryPrice - chartFirstPrice) / entryPrice * 100
          : (chartFirstPrice - entryPrice) / entryPrice * 100
        const newFirstOffset = Math.round(rawFirstOffset * 100) / 100

        const n = p.ordersCount
        let newStep = p.stepPercent
        if (n > 1) {
          const firstP = isLong
            ? entryPrice * (1 - newFirstOffset / 100)
            : entryPrice * (1 + newFirstOffset / 100)
          if (firstP > 0 && chartLastPrice > 0) {
            const ratio = chartLastPrice / firstP
            const exponent = 1 / (n - 1)
            const rawStep = isLong
              ? (1 - Math.pow(ratio, exponent)) * 100
              : (Math.pow(ratio, exponent) - 1) * 100
            newStep = Math.max(0.01, Math.round(rawStep * 100) / 100)
          }
        }

        // Compute lastOffsetPercent from chartLastPrice
        const rawLastOffset = isLong
          ? (entryPrice - chartLastPrice) / entryPrice * 100
          : (chartLastPrice - entryPrice) / entryPrice * 100
        const newLastOffset = Math.round(rawLastOffset * 100) / 100

        if (Math.abs(newFirstOffset - p.firstOffsetPercent) < 0.005 && Math.abs(newStep - p.stepPercent) < 0.005 && Math.abs(newLastOffset - p.lastOffsetPercent) < 0.005) return p
        return { ...p, firstOffsetPercent: newFirstOffset, stepPercent: newStep, lastOffsetPercent: newLastOffset }
      }
    })
    if (isPlacedRef.current) markGridPendingUpdate(consoleIdRef.current)
  }, [chartFirstPrice, chartLastPrice])

  // In non-multipos mode, only the first slot (index 0) of a side owns TP/SL on chart.
  // Returns whether the current active slot should render TP/SL lines.
  const isSharedTpSlOwner = (): boolean => {
    if (multiPositionModeRef.current) return true
    const side = activeSideRef.current
    return (side === "long" ? activeLongIdx : activeShortIdx) === 0
  }

  // Push preview whenever config changes and totalQuote > 0
  useEffect(() => {
    if (!isVisible) {
      cancelGridPreview(consoleId)
      return
    }
    if (!activeChartId) {
      if (gridOrdersRef.current[consoleId]) cancelGridOrders(consoleId)
      return
    }
    if (cfg.totalQuote <= 0) {
      cancelGridOrders(consoleId)
      return
    }
    // Don't overwrite placed orders automatically — just mark pending
    if (isPlaced) {
      return
    }

    const viz = calcGridVisualization(cfg)
    // Ensure stable IDs for drag handlers
    while (orderIdRefs.current.length < viz.orders.length) {
      orderIdRefs.current.push(nanoid())
    }
    orderIdRefs.current = orderIdRefs.current.slice(0, viz.orders.length)

    // In non-multipos mode only slot 0 of each side shows TP/SL on chart
    const showTpSl = isSharedTpSlOwner()

    // If a virtual position already exists, suppress draft TP/SL lines (same logic as Order tab)
    const positionHasOrders = accountId && exchangeId && marketType && cfg.symbol && cfg.side
      ? (positions[posKey(accountId, exchangeId, marketType, cfg.symbol, cfg.side)]?.orders ?? []).length > 0
      : false

    // Record expected prices so drag-sync effects can ignore form-driven updates
    const ordersForPreview = viz.orders.map((o, i) => ({ id: orderIdRefs.current[i], price: o.price, qty: o.qty }))
    expectedFirstPriceRef.current = ordersForPreview[0]?.price
    expectedLastPriceRef.current = ordersForPreview[ordersForPreview.length - 1]?.price
    expectedSlPriceRef.current = (showTpSl && !positionHasOrders) ? viz.slPrice : null

    setGridPreview(consoleId, {
      chartId: activeChartId,
      side: cfg.side,
      orders: ordersForPreview,
      tpPrice: (showTpSl && !positionHasOrders) ? viz.tpPrice : null,
      slPrice: (showTpSl && !positionHasOrders) ? viz.slPrice : null,
      tpLevels: (showTpSl && !positionHasOrders) ? viz.tpLevels : [],
      symbol: cfg.symbol,
      leverage: cfg.leverage,
      entryPrice: cfg.entryPrice,
      accountId,
      exchangeId,
      marketType,
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cfg, activeChartId, isPlaced, activeLongIdx, activeShortIdx, multiPositionMode, isVisible])

  // When side switches, cancel preview for the OLD consoleId but leave placed grids intact
  const prevSideConsoleIdRef = useRef<string | null>(null)
  useEffect(() => {
    const prev = prevSideConsoleIdRef.current
    if (prev && prev !== consoleId) {
      cancelGridPreview(prev)
    }
    prevSideConsoleIdRef.current = consoleId
  }, [consoleId, cancelGridPreview])

  // On full unmount, cancel only preview slots (placed grids must survive tab switching)
  useEffect(() => {
    return () => {
      const prefix = `${baseConsoleId}:`
      Object.keys(gridOrdersRef.current).forEach((id) => {
        if (id.startsWith(prefix)) cancelGridPreview(id)
      })
    }
  }, [baseConsoleId])

  // ── Shared TP/SL sync: when !multiPositionMode, propagate TP/SL changes
  // to the FIRST slot (index 0) of the active side — that slot is the sole TP/SL owner.
  // TP/SL are anchored to the "best" first order across ALL placed slots so that adding
  // a deeper grid never moves TP/SL in the wrong direction.
  const activeSideSharedTpSlRef = useRef(activeSideSharedTpSl)
  activeSideSharedTpSlRef.current = activeSideSharedTpSl
  useEffect(() => {
    if (multiPositionMode) return
    if (!activeChartId) return
    const shared = activeSideSharedTpSlRef.current
    const side = activeSideRef.current
    const isLong = side === "long"
    const allSlots = side === "long" ? longSlots : shortSlots
    // Only slot 0 owns TP/SL; all others get nulled out
    allSlots.forEach((slot, idx) => {
      const slotId = `${baseConsoleId}:${activeChartId}:${side}:${slot.slotId}`
      const slotEntry = gridOrdersRef.current[slotId]
      if (!slotEntry) return
      if (idx !== 0) {
        // Ensure non-owner slots have no TP/SL on chart
        if (slotEntry.tpPrice !== null || slotEntry.slPrice !== null || slotEntry.tpLevels.length > 0) {
          applyGridTpSl(slotId, { tpPrice: null, slPrice: null, tpLevels: [] })
        }
        return
      }
      // Slot 0: build TP/SL using best first order / extreme across ALL placed slots
      const isActiveSlot = (side === "long" ? activeLongIdx : activeShortIdx) === 0
      const slotStoredCfg = isActiveSlot ? cfgRef.current : slotCfgMapRef.current[slotKey(slot.slotId)]
      if (!slotStoredCfg) return
      const mergedCfg: GridConfig = { ...slotStoredCfg, ...shared }

      // Collect prices from all slots that have been placed (have an entry in gridOrdersRef)
      const allSlotPrices: number[][] = allSlots.map((s) => {
        const sCfg = (isLong ? activeLongIdx : activeShortIdx) === allSlots.indexOf(s)
          ? cfgRef.current
          : slotCfgMapRef.current[slotKey(s.slotId)]
        const sId = `${baseConsoleId}:${activeChartId}:${side}:${s.slotId}`
        if (!sCfg || !gridOrdersRef.current[sId]) return []
        return calcGridPrices(sCfg)
      }).filter((p) => p.length > 0)

      if (allSlotPrices.length === 0) {
        const viz = calcGridVisualization(mergedCfg)
        applyGridTpSl(slotId, { tpPrice: viz.tpPrice, slPrice: viz.slPrice, tpLevels: viz.tpLevels })
        return
      }

      // Prefer anchors from the full virtual position (includes single orders + all grids).
      const livePos = accountId && exchangeId && marketType && mergedCfg.symbol && side
        ? positions[posKey(accountId, exchangeId, marketType, mergedCfg.symbol, side)]
        : undefined
      const posAnchors = livePos ? getPositionAnchors(livePos.orders, side) : null

      const firstOrders = allSlotPrices.map((p) => p[0])
      const allPrices = allSlotPrices.flat()

      const bestFirstOrder = posAnchors?.firstOrder ?? (isLong ? Math.max(...firstOrders) : Math.min(...firstOrders))
      const extremeForSl = posAnchors?.extremeOrder ?? (isLong ? Math.min(...allPrices) : Math.max(...allPrices))
      const avgEntryAll = posAnchors?.avgEntry ?? (allPrices.reduce((s, p) => s + p, 0) / allPrices.length)

      let tpPrice: number | null = null
      let tpLevels: number[] = []
      if (mergedCfg.tpEnabled) {
        const base = bestFirstOrder
        if (mergedCfg.multiTpEnabled && mergedCfg.multiTpLevels.length > 0) {
          tpLevels = mergedCfg.multiTpLevels.slice(0, mergedCfg.multiTpCount).map((lvl) => {
            const pct = Math.max(0.01, lvl.tpPercent) / 100
            return isLong ? base * (1 + pct) : base * (1 - pct)
          })
          tpPrice = tpLevels[0] ?? null
        } else {
          const tpPct = Math.max(0.01, mergedCfg.tpPercent) / 100
          tpPrice = isLong ? base * (1 + tpPct) : base * (1 - tpPct)
          tpLevels = tpPrice !== null ? [tpPrice] : []
        }
      }

      let slPrice: number | null = null
      if (mergedCfg.slEnabled) {
        const slPct = Math.max(0.01, mergedCfg.slPercent) / 100
        if (mergedCfg.slMode === "avg_entry") {
          slPrice = isLong ? avgEntryAll * (1 - slPct) : avgEntryAll * (1 + slPct)
        } else {
          // extreme_order mode (default)
          slPrice = isLong ? extremeForSl * (1 - slPct) : extremeForSl * (1 + slPct)
        }
      }

      applyGridTpSl(slotId, { tpPrice, slPrice, tpLevels })
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeSideSharedTpSl, multiPositionMode, activeChartId, longSlots, shortSlots, positions])

  const handlePlaceGrid = () => {
    if (!activeChartId) return
    // Capture everything synchronously before any async work
    const snapshotCfg = { ...cfgRef.current }
    const snapshotShared = activeSideSharedTpSlRef.current
    const snapshotSide = activeSideRef.current
    const snapshotConsoleId = consoleId
    const snapshotChartId = activeChartId

    // Save current slot cfg so shared TP/SL sync can recalculate prices for this slot later
    if (activeSlot) slotCfgMapRef.current[slotKey(activeSlot.slotId)] = stripTpSlIfShared(snapshotCfg)
    const viz = calcGridVisualization(snapshotCfg)
    while (orderIdRefs.current.length < viz.orders.length) {
      orderIdRefs.current.push(nanoid())
    }
    orderIdRefs.current = orderIdRefs.current.slice(0, viz.orders.length)
    const showTpSl = isSharedTpSlOwner()
    expectedFirstPriceRef.current = viz.orders[0]?.price
    expectedLastPriceRef.current = viz.orders[viz.orders.length - 1]?.price
    expectedSlPriceRef.current = showTpSl ? viz.slPrice : null
    const newData = {
      chartId: snapshotChartId,
      consoleId: snapshotConsoleId,
      side: snapshotCfg.side,
      orders: viz.orders.map((o, i) => ({ id: orderIdRefs.current[i], price: o.price, qty: o.qty })),
      tpPrice: showTpSl ? viz.tpPrice : null,
      slPrice: showTpSl ? viz.slPrice : null,
      tpLevels: showTpSl ? viz.tpLevels : [],
      symbol: snapshotCfg.symbol,
      leverage: snapshotCfg.leverage,
      entryPrice: snapshotCfg.entryPrice,
      accountId,
      exchangeId,
      marketType,
    }

    // Capture owner TP/SL for non-multipos mode.
    // TP/SL must be anchored to the "best" order across ALL placed slots, not just the new one:
    //   LONG  TP → highest firstOrder (MAX prices[0] across slots)
    //   SHORT TP → lowest  firstOrder (MIN prices[0] across slots)
    //   LONG  SL extreme_order → lowest  of ALL prices across slots
    //   SHORT SL extreme_order → highest of ALL prices across slots
    //   avg_entry SL → weighted avg of all orders across slots
    let ownerUpdate: { consoleId: string; tpPrice: number | null; slPrice: number | null; tpLevels: number[] } | null = null
    if (!multiPositionModeRef.current) {
      const allSlots = snapshotSide === "long" ? longSlotsRef.current : shortSlotsRef.current
      const ownerSlot = allSlots[0]
      if (ownerSlot) {
        const ownerConsoleId = `${baseConsoleId}:${snapshotChartId}:${snapshotSide}:${ownerSlot.slotId}`
        const mergedCfg: GridConfig = { ...snapshotCfg, ...snapshotShared }
        const isLong = snapshotSide === "long"

        // Collect prices from ALL slots (including the one just placed via snapshotCfg)
        const allSlotPrices: number[][] = allSlots.map((slot) => {
          const storedCfg = slot.slotId === activeSlot?.slotId
            ? snapshotCfg
            : slotCfgMapRef.current[`${snapshotChartId ?? ""}:${slot.slotId}`]
          if (!storedCfg) return []
          return calcGridPrices(storedCfg)
        }).filter((p) => p.length > 0)

        if (allSlotPrices.length === 0) {
          // No placed slots yet — fall back to current viz
          const ownerViz = calcGridVisualization(mergedCfg)
          ownerUpdate = {
            consoleId: ownerConsoleId,
            tpPrice: ownerViz.tpPrice,
            slPrice: ownerViz.slPrice,
            tpLevels: ownerViz.tpLevels,
          }
        } else {
          // Prefer anchors from the full virtual position (includes single orders + all grids).
          // Include the new grid orders being placed now so anchors reflect the post-placement state.
          // Fall back to slot prices only if the position doesn't exist yet.
          const livePos = accountId && exchangeId && marketType && snapshotCfg.symbol && snapshotSide
            ? positions[posKey(accountId, exchangeId, marketType, snapshotCfg.symbol, snapshotSide)]
            : undefined
          const newGridOrdersAsPlaced = newData.orders.map((o) => ({
            id: o.id, price: o.price, qty: o.qty,
            side: snapshotSide === "long" ? "buy" as const : "sell" as const,
            source: "grid" as const,
            status: "pending" as const,
          }))
          const existingWithoutNew = livePos
            ? livePos.orders.filter((o) => o.gridConsoleId !== snapshotConsoleId)
            : []
          const combinedOrders = [...existingWithoutNew, ...newGridOrdersAsPlaced]
          const posAnchors = combinedOrders.length > 0
            ? getPositionAnchors(combinedOrders, snapshotSide)
            : null

          const allPrices = allSlotPrices.flat()
          const firstOrders = allSlotPrices.map((p) => p[0])

          const bestFirstOrder = posAnchors?.firstOrder ?? (isLong
            ? Math.max(...firstOrders)
            : Math.min(...firstOrders))

          const extremeForSl = posAnchors?.extremeOrder ?? (isLong
            ? Math.min(...allPrices)
            : Math.max(...allPrices))

          const avgEntryAll = posAnchors?.avgEntry ?? (allPrices.reduce((s, p) => s + p, 0) / allPrices.length)

          // Build TP price(s) from bestFirstOrder
          let tpPrice: number | null = null
          let tpLevels: number[] = []
          if (mergedCfg.tpEnabled) {
            const base = bestFirstOrder
            if (mergedCfg.multiTpEnabled && mergedCfg.multiTpLevels.length > 0) {
              tpLevels = mergedCfg.multiTpLevels.slice(0, mergedCfg.multiTpCount).map((lvl) => {
                const pct = Math.max(0.01, lvl.tpPercent) / 100
                return isLong ? base * (1 + pct) : base * (1 - pct)
              })
              tpPrice = tpLevels[0] ?? null
            } else {
              const tpPct = Math.max(0.01, mergedCfg.tpPercent) / 100
              tpPrice = isLong ? base * (1 + tpPct) : base * (1 - tpPct)
              tpLevels = tpPrice !== null ? [tpPrice] : []
            }
          }

          // Build SL price from correct base depending on mode
          let slPrice: number | null = null
          if (mergedCfg.slEnabled) {
            const slPct = Math.max(0.01, mergedCfg.slPercent) / 100
            if (mergedCfg.slMode === "avg_entry") {
              slPrice = isLong
                ? avgEntryAll * (1 - slPct)
                : avgEntryAll * (1 + slPct)
            } else {
              // extreme_order mode (default)
              slPrice = isLong
                ? extremeForSl * (1 - slPct)
                : extremeForSl * (1 + slPct)
            }
          }

          ownerUpdate = { consoleId: ownerConsoleId, tpPrice, slPrice, tpLevels }
        }
      }
    }

    // Cancel placed grid first, then set fresh preview and place
    cancelGridOrders(snapshotConsoleId)
    // Pass newData directly to placeGridOrders so there is no intermediate render
    // showing draft (dashed) lines — the grid goes directly from cleared → placed.
    setTimeout(() => {
      placeGridOrders(snapshotConsoleId, newData)
      // In non-multipos mode, re-anchor owner's TP/SL to the just-placed grid's geometry
      if (ownerUpdate) {
        applyGridTpSl(ownerUpdate.consoleId, {
          tpPrice: ownerUpdate.tpPrice,
          slPrice: ownerUpdate.slPrice,
          tpLevels: ownerUpdate.tpLevels,
        })
      }
    }, 0)
  }

  const stopProp = (e: React.MouseEvent) => e.stopPropagation()
  const baseSymbol = cfg.symbol.split("/")[0] ?? "BTC"

  // ── Slot management ───────────────────────────────────────────────────────

  // Strip TP/SL keys from a cfg before storing in slotCfgMapRef when !multiPositionMode
  // so that switching slots never restores stale per-slot TP/SL over the shared values.
  const stripTpSlIfShared = (c: GridConfig): GridConfig => {
    if (multiPositionModeRef.current) return c
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const { tpEnabled, tpMode, tpPercent, tpClosePercent, multiTpEnabled, multiTpCount, multiTpLevels,
      tpRepositionEnabled, perLevelTpEnabled, perLevelTpGroups, slEnabled, slMode, slPercent, slClosePercent,
      resetTpEnabled, resetTpTriggerLevels, defaultResetTpPercent, defaultResetTpClosePercent,
      resetTpRebuildTail, resetTpPerLevelEnabled, resetTpPerLevelSettings, ...rest } = c
    return rest as GridConfig
  }

  const handleAddSlot = () => {
    // Save current cfg to current slot before switching
    if (activeSlot) slotCfgMapRef.current[slotKey(activeSlot.slotId)] = stripTpSlIfShared({ ...cfgRef.current })
    const newSlot = { slotId: nanoid() }
    setGridSlots((prev) => [...prev, newSlot])
    setActiveSlotIndex(gridSlots.length)
    // New slot gets fresh config inheriting symbol/side/entry/leverage (+ shared TP/SL when !multiPos)
    const shared = activeSideRef.current === "long" ? longSharedTpSl : shortSharedTpSl
    setCfg({
      ...DEFAULT_GRID_CONFIG,
      ...(multiPositionModeRef.current ? {} : shared),
      symbol: cfgRef.current.symbol,
      side: cfgRef.current.side,
      entryPrice: cfgRef.current.entryPrice,
      leverage: cfgRef.current.leverage,
    })
    orderIdRefs.current = []
  }

  const handleSwitchSlot = (idx: number) => {
    if (idx === activeSlotIndex) return
    // Save current cfg to current slot (TP/SL stripped when !multiPositionMode)
    if (activeSlot) slotCfgMapRef.current[slotKey(activeSlot.slotId)] = stripTpSlIfShared({ ...cfgRef.current })
    setActiveSlotIndex(idx)
    const targetSlot = gridSlots[idx]
    if (targetSlot) {
      const saved = slotCfgMapRef.current[slotKey(targetSlot.slotId)]
      const shared = activeSideRef.current === "long" ? longSharedTpSl : shortSharedTpSl
      const tpSlOverride = multiPositionModeRef.current ? {} : shared
      if (saved) {
        setCfg({ ...saved, ...tpSlOverride, symbol: cfgRef.current.symbol, entryPrice: cfgRef.current.entryPrice, leverage: cfgRef.current.leverage })
      } else {
        setCfg({ ...DEFAULT_GRID_CONFIG, ...tpSlOverride, symbol: cfgRef.current.symbol, side: cfgRef.current.side, entryPrice: cfgRef.current.entryPrice, leverage: cfgRef.current.leverage })
      }
    }
    orderIdRefs.current = []
  }



  // Side button
  const gap4: React.CSSProperties = { display: "flex", flexDirection: "column", gap: 4 }

  return (
    <div className="flex flex-col h-full overflow-auto" onMouseDown={stopProp}>

      {/* ── Templates ─────────────────────────────────── */}
      <TemplateBar
        templates={templates}
        activeId={activeTemplateId}
        onSelect={handleSelectTemplate}
        onSave={handleSaveTemplate}
        onDelete={(id) => { deleteTemplate(id); if (id === activeTemplateId) { setActiveTemplateId(null); setSavedCfgJson(null) } }}
        isDirty={isDirty}
      />

      <div style={{ padding: "8px 10px" }}>
      {/* ── LEV + GRID SLOTS + PRO row ───────────────── */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6, gap: 6 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <span style={{ fontSize: 9, fontFamily: "monospace", opacity: 0.35 }}>LEV</span>
          <div style={{ width: 52 }}>
            <NI value={cfg.leverage} onChange={(v) => upd("leverage", Math.max(1, v))} min={1} suffix="×" title="Leverage multiplier" />
          </div>
        </div>

        {/* ── Grid slot tabs with overlay scroll arrows ─── */}
        <div style={{ display: "flex", alignItems: "center", gap: 4, flex: 1, minWidth: 0 }}>
          {/* Viewport: relative container so overlay arrows are positioned inside */}
          <div style={{ flex: 1, minWidth: 0, position: "relative" }}>

            {/* Left fade+arrow overlay — does NOT affect layout */}
            {slotCanScrollLeft && (
              <button
                onMouseDown={stopProp}
                onClick={() => {
                  slotScrollRef.current?.scrollBy({ left: -60, behavior: "smooth" })
                  slotScrollCooldownRef.current = true
                  setTimeout(() => { slotScrollCooldownRef.current = false }, 400)
                }}
                style={{
                  position: "absolute", left: 0, top: 0, bottom: 0, zIndex: 2,
                  width: 20, border: "none", cursor: "pointer", padding: 0,
                  background: "linear-gradient(to right, rgba(18,18,18,1) 30%, transparent 100%)",
                  display: "flex", alignItems: "center", paddingLeft: 2,
                  color: "rgba(255,255,255,0.5)",
                }}
              >
                <svg width="5" height="8" viewBox="0 0 5 8" fill="none">
                  <path d="M4 1L1 4L4 7" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </button>
            )}

            {/* Scrollable slot tabs */}
            <div
              ref={slotScrollRef}
              onScroll={updateSlotScroll}
              style={{
                display: "flex", alignItems: "center", gap: 2,
                overflowX: "auto", overflowY: "hidden",
                scrollbarWidth: "none",
              }}
            >
            {(["long", "short"] as const).map((slotSide) => {
              const sideSlots = slotSide === "long" ? longSlots : shortSlots
              const sideActiveIdx = slotSide === "long" ? activeLongIdx : activeShortIdx
              const isSideActive = slotSide === cfg.side
              const longColor = "#00e5a0"
              const shortColor = "#f87171"
              const sideColor = slotSide === "long" ? longColor : shortColor
              return sideSlots.map((slot, idx) => {
                const slotConsoleId = `${baseConsoleId}:${activeChartId ?? ""}:${slotSide}:${slot.slotId}`
                const slotState = gridOrdersRef.current[slotConsoleId]
                const slotPlaced = !!slotState
                const slotPending = slotPlaced && slotState?.pendingUpdate
                const isActive = isSideActive && idx === sideActiveIdx
                return (
                  <div
                    key={slot.slotId}
                    onClick={() => {
                      if (slotScrollCooldownRef.current) return
                      if (!isSideActive) {
                        if (activeSlot) slotCfgMapRef.current[slotKey(activeSlot.slotId)] = stripTpSlIfShared({ ...cfgRef.current })
                        const targetSlots = slotSide === "long" ? longSlots : shortSlots
                        const targetSlot = targetSlots[idx]
                        const saved = targetSlot ? slotCfgMapRef.current[slotKey(targetSlot.slotId)] : undefined
                        const targetShared = slotSide === "long" ? longSharedTpSl : shortSharedTpSl
                        const tpSlOverride = multiPositionModeRef.current ? {} : targetShared
                        const newCfg = saved
                          ? { ...saved, ...tpSlOverride, symbol: cfgRef.current.symbol, entryPrice: cfgRef.current.entryPrice, leverage: cfgRef.current.leverage }
                          : { ...DEFAULT_GRID_CONFIG, ...tpSlOverride, symbol: cfgRef.current.symbol, side: slotSide, entryPrice: cfgRef.current.entryPrice, leverage: cfgRef.current.leverage }
                        setCfg(newCfg)
                        if (slotSide === "long") { setActiveLongIdx(idx) } else { setActiveShortIdx(idx) }
                        orderIdRefs.current = []
                      } else {
                        handleSwitchSlot(idx)
                      }
                    }}
                    onMouseDown={stopProp}
                    style={{
                      display: "flex", alignItems: "center", gap: 3,
                      padding: "2px 5px 2px 6px",
                      borderRadius: 4, flexShrink: 0,
                      cursor: "pointer",
                      opacity: isSideActive ? 1 : 0.55,
                      border: isActive
                        ? `1px solid ${slotPending ? "rgba(251,191,36,0.5)" : `${sideColor}55`}`
                        : `1px solid ${sideColor}22`,
                      background: isActive
                        ? (slotPending ? "rgba(251,191,36,0.1)" : `${sideColor}18`)
                        : `${sideColor}08`,
                      transition: "all 0.15s",
                    }}
                    title={`${slotSide === "long" ? "Long" : "Short"} Grid ${idx + 1}${slotPlaced ? " (placed)" : ""}`}
                  >
                    <span style={{
                      fontSize: 9, fontFamily: "monospace", fontWeight: isActive ? 700 : 500, letterSpacing: "0.04em",
                      color: isActive
                        ? (slotPending ? "rgba(251,191,36,0.9)" : sideColor)
                        : `${sideColor}66`,
                    }}>
                      {idx + 1}
                    </span>
                    {slotPlaced && (
                      <div style={{
                        width: 4, height: 4, borderRadius: "50%", flexShrink: 0,
                        background: slotPending ? "rgba(251,191,36,0.8)" : sideColor,
                        opacity: isSideActive ? 1 : 0.6,
                      }} />
                    )}
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        if (slotScrollCooldownRef.current) return
                        // Find the actual consoleId from gridOrders — the chartId captured at place time
                        // may differ from the current activeChartId (e.g. after chart switch).
                        const suffix = `:${slotSide}:${slot.slotId}`
                        const prefix = `${baseConsoleId}:`
                        const matchedId = Object.keys(gridOrdersRef.current).find(
                          (id) => id.startsWith(prefix) && id.endsWith(suffix)
                        )
                        const cancelId = matchedId ?? `${baseConsoleId}:${activeChartId ?? ""}:${slotSide}:${slot.slotId}`
                        cancelGridOrders(cancelId)
                        delete slotCfgMapRef.current[slotKey(slot.slotId)]
                        const targetSlots = slotSide === "long" ? longSlots : shortSlots
                        const setSlots = slotSide === "long" ? setLongSlots : setShortSlots
                        const targetActiveIdx = slotSide === "long" ? activeLongIdx : activeShortIdx
                        const setActiveIdx = slotSide === "long" ? setActiveLongIdx : setActiveShortIdx
                        const slotShared = slotSide === "long" ? longSharedTpSl : shortSharedTpSl
                        const tpSlOverride = multiPositionModeRef.current ? {} : slotShared
                        if (targetSlots.length === 1) {
                          if (isSideActive) {
                            setCfg({ ...DEFAULT_GRID_CONFIG, ...tpSlOverride, symbol: cfgRef.current.symbol, side: slotSide, entryPrice: cfgRef.current.entryPrice, leverage: cfgRef.current.leverage })
                            orderIdRefs.current = []
                          }
                          return
                        }
                        const newSlots = targetSlots.filter((_, i) => i !== idx)
                        const newActive = Math.min(targetActiveIdx, newSlots.length - 1)
                        setSlots(newSlots)
                        setActiveIdx(newActive)
                        if (isSideActive) {
                          const targetSlot = newSlots[newActive]
                          const saved = targetSlot ? slotCfgMapRef.current[slotKey(targetSlot.slotId)] : undefined
                          setCfg(saved
                            ? { ...saved, ...tpSlOverride, symbol: cfgRef.current.symbol, entryPrice: cfgRef.current.entryPrice, leverage: cfgRef.current.leverage }
                            : { ...DEFAULT_GRID_CONFIG, ...tpSlOverride, symbol: cfgRef.current.symbol, side: slotSide, entryPrice: cfgRef.current.entryPrice, leverage: cfgRef.current.leverage }
                          )
                          orderIdRefs.current = []
                        }
                      }}
                      onMouseDown={(e) => e.stopPropagation()}
                      style={{
                        background: "transparent", border: "none", cursor: "pointer", padding: 0,
                        display: "flex", alignItems: "center", justifyContent: "center",
                        color: `${sideColor}44`, lineHeight: 1,
                        width: 10, height: 10, flexShrink: 0,
                      }}
                      title={slotPlaced ? "Cancel this grid" : "Remove grid slot"}
                    >
                      <svg width="7" height="7" viewBox="0 0 7 7" fill="none">
                        <line x1="1" y1="1" x2="6" y2="6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                        <line x1="6" y1="1" x2="1" y2="6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                      </svg>
                    </button>
                  </div>
                )
              })
            })}
            </div>

            {/* Right fade+arrow overlay — does NOT affect layout */}
            {slotCanScrollRight && (
              <button
                onMouseDown={stopProp}
                onClick={() => {
                  slotScrollRef.current?.scrollBy({ left: 60, behavior: "smooth" })
                  slotScrollCooldownRef.current = true
                  setTimeout(() => { slotScrollCooldownRef.current = false }, 400)
                }}
                style={{
                  position: "absolute", right: 0, top: 0, bottom: 0, zIndex: 2,
                  width: 20, border: "none", cursor: "pointer", padding: 0,
                  background: "linear-gradient(to left, rgba(18,18,18,1) 30%, transparent 100%)",
                  display: "flex", alignItems: "center", justifyContent: "flex-end", paddingRight: 2,
                  color: "rgba(255,255,255,0.5)",
                }}
              >
                <svg width="5" height="8" viewBox="0 0 5 8" fill="none">
                  <path d="M1 1L4 4L1 7" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </button>
            )}
          </div>

          {/* Add new grid slot — always visible, outside scroll viewport */}
          <button
            onClick={() => {
              handleAddSlot()
              setTimeout(() => {
                const el = slotScrollRef.current
                if (el) {
                  el.scrollTo({ left: el.scrollWidth, behavior: "smooth" })
                  updateSlotScroll()
                }
              }, 80)
            }}
            onMouseDown={stopProp}
            style={{
              display: "flex", alignItems: "center", justifyContent: "center",
              width: 18, height: 18, flexShrink: 0,
              background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.1)",
              borderRadius: 4, cursor: "pointer", color: "rgba(255,255,255,0.35)",
              transition: "all 0.15s",
            }}
            title={`Add new ${cfg.side} grid`}
          >
            <svg width="8" height="8" viewBox="0 0 8 8" fill="none">
              <line x1="4" y1="1" x2="4" y2="7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              <line x1="1" y1="4" x2="7" y2="4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
          </button>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
          <span style={{ fontSize: 9, fontFamily: "monospace", opacity: 0.35, textTransform: "uppercase", letterSpacing: "0.06em" }}>Pro</span>
          <MiniToggle checked={proMode} onChange={(v) => { setProMode(v); if (!v) { upd("perLevelTpEnabled", false); setMultiPositionMode(false) } }} />
          {proMode && (
            <>
              <div style={{ width: 1, height: 12, background: "rgba(255,255,255,0.1)", flexShrink: 0 }} />
              <span style={{ fontSize: 8, fontFamily: "monospace", opacity: multiPositionMode ? 0.85 : 0.3, textTransform: "uppercase", letterSpacing: "0.05em", color: multiPositionMode ? "rgba(255,170,0,0.9)" : undefined, whiteSpace: "nowrap" }}>M-pos</span>
              <MiniToggle
                checked={multiPositionMode}
                onChange={(v) => setMultiPositionMode(v)}
              />
            </>
          )}
        </div>
      </div>

      {/* ── Side toggle ───────────────────────────────── */}
      <div style={{ display: "flex", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 4, marginBottom: 6 }}>
        {(["long", "short"] as const).map((s, i) => (
          <button
            key={s}
            onClick={() => { upd("side", s); onSideChange?.(s) }}
            style={{
              flex: 1,
              padding: "6px 0",
              fontFamily: "monospace",
              fontSize: 10,
              fontWeight: 700,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              cursor: "pointer",
              border: "none",
              borderLeft: i === 1 ? "1px solid rgba(255,255,255,0.1)" : "none",
              borderRadius: i === 0 ? "3px 0 0 3px" : "0 3px 3px 0",
              transition: "background 0.15s, color 0.15s",
              background: cfg.side === s
                ? (s === "long" ? "rgba(0,229,160,0.18)" : "rgba(255,71,87,0.18)")
                : "transparent",
              color: cfg.side === s
                ? (s === "long" ? "#00e5a0" : "#ff4757")
                : "rgba(255,255,255,0.3)",
            }}
            title={s === "long" ? "Long: profit when price goes up" : "Short: profit when price goes down"}
            onMouseDown={stopProp}
          >
            {marketType === "spot" ? (s === "long" ? "BUY" : "SELL") : (s === "long" ? "LONG" : "SHORT")}
          </button>
        ))}
      </div>
      <Divider />

      {/* ── ENTRY ────────────────────────────────────── */}
      <div style={{ marginBottom: 6 }}>
        <div style={{ ...gap4, marginTop: 0 }}>
          {/* Current Price row with order type switcher */}
          <div style={{ ...readonlyBase, display: "flex", alignItems: "center", justifyContent: "space-between", gap: 6, padding: "3px 6px" }}>
            <span style={{ fontSize: 9, opacity: 0.4, whiteSpace: "nowrap", fontFamily: "monospace" }}>{cfg.symbol ?? "Current Price"}</span>
            <span style={{ fontWeight: 700, color: "#00e5a0", fontSize: 11, flex: 1, textAlign: "right", marginRight: 6 }}>
              {cfg.entryPrice.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </span>
            <Seg
              options={[
                { v: "limit", label: "Limit", title: "Enter at a specific limit price" },
                { v: "market", label: "Stop", title: "Enter with a stop order" },
              ]}
              value={cfg.entryType}
              onChange={(v) => upd("entryType", v)}
              style={{ minWidth: 90 }}
            />
          </div>
        </div>
      </div>
      <Divider />

      {/* ── GRID SETUP ───────────────────────────────── */}
      <div style={{ marginBottom: 6 }}>
        <div style={{ display: "flex", gap: 6, marginBottom: 4, alignItems: "center" }}>
          <div style={{ width: 80, flexShrink: 0 }}>
            <NI value={cfg.ordersCount} onChange={(v) => upd("ordersCount", Math.max(1, Math.min(100, Math.round(v))))} label="Orders" placeholder="8" title="Number of grid levels (1–100)" min={1} />
          </div>
          <BudgetInput
            value={cfg.totalQuote}
            onChange={(v) => upd("totalQuote", v)}
            mode={cfg.budgetMode ?? "quote"}
            onModeChange={(m) => upd("budgetMode", m)}
            baseSymbol={baseSymbol}
          />
        </div>
        {/* Available balance row */}
        <div style={{ position: "relative", marginBottom: 4 }}>
          <div
            style={{
              display: "flex", alignItems: "center", justifyContent: "space-between",
              padding: "2px 4px", borderRadius: 3, cursor: "default",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 3 }}>
              <span style={{ fontSize: 9, fontFamily: "monospace", color: "rgba(255,255,255,0.35)" }}>
                Available
              </span>
              {marketType === "futures" && (
                <svg
                  width="9" height="9" viewBox="0 0 10 10" fill="none"
                  style={{ opacity: 0.45, flexShrink: 0, cursor: "help" }}
                  onMouseEnter={() => setAvailTooltip(true)}
                  onMouseLeave={() => setAvailTooltip(false)}
                >
                  <circle cx="5" cy="5" r="4.5" stroke="rgba(30,111,239,0.7)" />
                  <text x="5" y="7.5" textAnchor="middle" fontSize="6.5" fill="rgba(77,159,255,0.9)" fontFamily="monospace">i</text>
                </svg>
              )}
            </div>
            <span style={{
              fontSize: 9, fontFamily: "monospace", fontWeight: 600,
              color: marketType === "futures" ? "#4d9fff" : "rgba(200,214,229,0.75)",
            }}>
              {availableForGrid.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} USDT
            </span>
          </div>

          {availTooltip && marketType === "futures" && (
            <div style={{
              position: "absolute", bottom: "calc(100% + 4px)", left: 0,
              minWidth: 220, zIndex: 9999,
              background: "#0a1220",
              border: "1px solid rgba(30,111,239,0.25)",
              borderRadius: 5, padding: "8px 10px",
              boxShadow: "0 8px 24px rgba(0,0,0,0.6)",
              pointerEvents: "none",
            }}>
              <span style={{ fontSize: 10, fontFamily: "monospace", fontWeight: 600, color: "rgba(200,214,229,0.9)", letterSpacing: "0.05em" }}>
                AVAILABLE BALANCE
              </span>
              <div style={{ display: "flex", flexDirection: "column", gap: 4, marginTop: 6 }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 16 }}>
                  <span style={{ fontSize: 10, fontFamily: "monospace", color: "rgba(255,255,255,0.4)" }}>Wallet balance</span>
                  <span style={{ fontSize: 10, fontFamily: "monospace", color: "rgba(200,214,229,0.75)" }}>{availableBalance.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} USDT</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 16 }}>
                  <span style={{ fontSize: 10, fontFamily: "monospace", color: "rgba(255,255,255,0.4)" }}>In open orders</span>
                  <span style={{ fontSize: 10, fontFamily: "monospace", color: "rgba(255,71,87,0.85)" }}>−{inOrders.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} USDT</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 16, paddingTop: 4, borderTop: "1px solid rgba(255,255,255,0.07)" }}>
                  <span style={{ fontSize: 10, fontFamily: "monospace", color: "rgba(255,255,255,0.4)" }}>Free margin</span>
                  <span style={{ fontSize: 10, fontFamily: "monospace", color: "rgba(200,214,229,0.75)" }}>{freeMargin.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} USDT</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 16 }}>
                  <span style={{ fontSize: 10, fontFamily: "monospace", color: "rgba(255,255,255,0.4)" }}>Leverage</span>
                  <span style={{ fontSize: 10, fontFamily: "monospace", color: "#4d9fff" }}>×{cfg.leverage}</span>
                </div>
              </div>
              <div style={{ borderTop: "1px solid rgba(255,255,255,0.08)", margin: "6px 0" }} />
              <div style={{ display: "flex", justifyContent: "space-between", gap: 16 }}>
                <span style={{ fontSize: 10, fontFamily: "monospace", fontWeight: 600, color: "rgba(255,255,255,0.55)" }}>Available (with leverage)</span>
                <span style={{ fontSize: 10, fontFamily: "monospace", fontWeight: 700, color: "#4d9fff" }}>{availableForGrid.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} USDT</span>
              </div>
              <p style={{ fontSize: 9, fontFamily: "monospace", color: "rgba(255,255,255,0.25)", lineHeight: 1.5, marginTop: 4 }}>
                = (Wallet − In orders) × {cfg.leverage}×<br/>
                = {freeMargin.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} × {cfg.leverage} = {availableForGrid.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </p>
            </div>
          )}
        </div>
        <PctBtns onPct={handlePct} />
      </div>
      <Divider />

      {/* ── GRID PLACEMENT ───────────────────────────── */}
      <div style={{ marginBottom: 6 }}>
        <div style={{ ...gap4, marginTop: 0 }}>
          <Seg
            options={[
              { v: "step_percent", label: "Step %", title: "Place orders at equal percentage steps" },
              { v: "price_range", label: "Price Range", title: "Distribute orders across a price range" },
            ]}
            value={cfg.placementMode}
            onChange={(v) => upd("placementMode", v)}
          />

          {cfg.placementMode === "step_percent" && (
            <div className="grid grid-cols-3" style={{ gap: 4 }}>
              <NI value={cfg.firstOffsetPercent} onChange={(v) => upd("firstOffsetPercent", v)} label="1st order %" step={0.1} title="Distance from entry price to 1st order (negative = market order simulation)" />
              <NI value={cfg.lastOffsetPercent} onChange={(v) => upd("lastOffsetPercent", v)} label="Last order %" min={0} step={0.1} title="Distance from entry to last order" />
              <NI value={cfg.stepPercent} onChange={(v) => upd("stepPercent", Math.max(0.01, v))} label="Step %" min={0.01} step={0.1} title="Price step between each grid level" />
            </div>
          )}

          {cfg.placementMode === "price_range" && (
            <div className="grid grid-cols-2" style={{ gap: 4 }}>
              <NI value={cfg.topPrice} onChange={(v) => upd("topPrice", v)} label="Top Price" title="Upper boundary of the grid" />
              <NI value={cfg.bottomPrice} onChange={(v) => upd("bottomPrice", v)} label="Bottom Price" title="Lower boundary of the grid" />
            </div>
          )}
        </div>
      </div>
      <Divider />

      {/* ── MULTIPLIER + DENSITY ─────────────────────── */}
      <div style={{ marginBottom: 6 }}>
        <div style={{ ...gap4 }}>
          <div className="grid grid-cols-2" style={{ gap: 4 }}>
            <NITooltip
              value={cfg.multiplier}
              onChange={(v) => upd("multiplier", Math.max(1.01, v))}
              label="Multiplier"
              min={1.01}
              step={0.05}
              title="Multiplier"
              tooltip="Каждый следующий ордер = предыдущий × Multiplier. Например, 1.25 — каждый ордер на 25% больше предыдущего."
            />
            <NITooltip
              value={cfg.density ?? 1}
              onChange={(v) => upd("density", Math.max(0.01, v))}
              label="Density"
              min={0.01}
              step={0.05}
              title="Density"
              tooltip={`Если выбрана "Плотность" равная 1, то ордера будут распределены в сетке равномерно, если больше 1, то ордера будут сконцентрированы ближе к концу сетки, если меньше 1, то ближе к началу.`}
            />
          </div>
        </div>
      </div>
      <Divider />

      {/* ── 5. TRAIL + AUTO RESTART ───────────────────── */}
      <div style={{ marginBottom: 6 }}>
        {/* Always-visible row: Trail [?] [toggle] [chevron if active] — — — Auto [?] TP [toggle] SL [toggle] */}
        <div style={{ display: "flex", alignItems: "center" }}>
          <LabelTooltip
            label="Trail"
            tooltip="Трейлинг сетки — сетка автоматически перемещается за ценой, когда цена уходит за край сетки на заданный процент."
          />
          <div style={{ marginLeft: 5 }}>
            <MiniToggle
              checked={cfg.trailEnabled}
              onChange={(v) => {
                upd("trailEnabled", v)
                if (v) setOpen((p) => ({ ...p, trail: true }))
              }}
            />
          </div>

          {/* Chevron to collapse/expand Trail settings row */}
          {cfg.trailEnabled && (
            <button
              onClick={() => tog("trail")}
              title={open.trail ? "Свернуть настройки трейлинга" : "Развернуть настройки трейлинга"}
              style={{
                marginLeft: 4, background: "none", border: "none", cursor: "pointer",
                padding: 0, display: "flex", alignItems: "center", opacity: 0.45,
                transition: "opacity 0.15s",
              }}
              onMouseEnter={(e) => (e.currentTarget.style.opacity = "0.85")}
              onMouseLeave={(e) => (e.currentTarget.style.opacity = "0.45")}
              onMouseDown={(e) => e.stopPropagation()}
            >
              <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                <path
                  d={open.trail ? "M2 3.5 L5 6.5 L8 3.5" : "M2 6.5 L5 3.5 L8 6.5"}
                  stroke="rgba(200,214,229,0.8)" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"
                />
              </svg>
            </button>
          )}

          {/* Spacer always pushes Auto to the right */}
          <div style={{ flex: 1 }} />

          {/* Auto — master toggle + conditional sub-toggles */}
          <div style={{ display: "flex", alignItems: "center", gap: 4, flexShrink: 0 }}>
            <LabelTooltip
              label="Auto"
              color={cfg.autoEnabled ? "rgba(52,211,153,0.8)" : undefined}
              tooltip="Авто-цикл сетки: после срабатывания TP новая сетка автоматически размещается по текущей рыночной цене. По умолчанию то же происходит после SL — отключите тумблер SL чтобы остановить цикл после стопа."
            />
            <MiniToggle
              checked={cfg.autoEnabled}
              onChange={(v) => {
                upd("autoEnabled", v)
                if (!v) {
                  upd("stopOnSl", false)
                  upd("stopNew", false)
                }
              }}
            />
            {cfg.autoEnabled && (
              <>
                <LabelTooltip
                  label="SL"
                  color={cfg.stopOnSl ? "rgba(248,113,113,0.45)" : "rgba(248,113,113,0.75)"}
                  tooltip={cfg.stopOnSl
                    ? "После срабатывания SL новый цикл сетки НЕ запускается — цикл останавливается."
                    : "После срабатывания SL новая сетка создаётся автоматически (по умолчанию). Включите тумблер чтобы остановить цикл после SL."}
                />
                <MiniToggle checked={cfg.stopOnSl} onChange={(v) => upd("stopOnSl", v)} />
                <LabelTooltip
                  label="Stop New"
                  color={cfg.stopNew ? "rgba(251,191,36,0.8)" : undefined}
                  tooltip="Остановить цикл после следующего срабатывания TP/SL. При этом TP пересчитывается на уровень безубытка. Удобно для мягкого выхода из авто-цикла."
                  align="right"
                />
                <MiniToggle checked={cfg.stopNew} onChange={(v) => upd("stopNew", v)} />
              </>
            )}
          </div>
        </div>

        {/* Row 2 — Trail settings, collapsible */}
        {cfg.trailEnabled && open.trail && (
          <div style={{ display: "flex", alignItems: "center", gap: 5, marginTop: 5 }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <NITooltip
                value={cfg.trailTriggerPercent}
                onChange={(v) => upd("trailTriggerPercent", v)}
                label="Trigger %"
                title="Trail trigger %"
                tooltip="Процент выхода цены за край сетки, при котором запускается перемещение сетки. Например, 1% — сетка сдвигается когда цена ушла на 1% за крайний ордер."
              />
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: 4, flexShrink: 0 }}>
              <LabelTooltip
                label="Lim"
                tooltip="Предельная цена трейлинга. Если цена достигает этого уровня — трейлинг останавливается. Возобновляется автоматически, когда цена снова выполняет условие триггера."
                color="rgba(200,214,229,0.4)"
              />
              <MiniToggle checked={cfg.trailLimitPriceEnabled} onChange={(v) => upd("trailLimitPriceEnabled", v)} />
            </div>

            {cfg.trailLimitPriceEnabled && (
              <div style={{ flex: 1, minWidth: 0 }}>
                <NITooltip
                  value={cfg.trailLimitPrice}
                  onChange={(v) => upd("trailLimitPrice", v)}
                  label="Lim price"
                  title="Trail limit price"
                  tooltip="Предельная цена трейлинга. Если цена достигает этого уровня — трейлинг останавливается. Возобновляется автоматически, когда цена снова выполняет условие триггера."
                />
              </div>
            )}
          </div>
        )}
      </div>
      <Divider />

      {/* ── TAKE PROFIT ───────────────────────────── */}
      {/* When !multiPositionMode: shared across all grids on this side */}
      <div style={{ marginBottom: 6 }}>
        {!multiPositionMode && (
          <div style={{ fontSize: 8, fontFamily: "monospace", color: "rgba(200,214,229,0.25)", letterSpacing: "0.05em", marginBottom: 3 }}>
            shared · {cfg.side}
          </div>
        )}
        <SectionHead
          title="TAKE PROFIT"
          expanded={open.tp}
          onToggle={() => tog("tp")}
          rightSlot={
            <div className="flex items-center" style={{ gap: 6 }} onMouseDown={stopProp}>
              {/* Reposition toggle */}
              <LabelTooltip
                label="Reposition"
                tooltip="После каждого усреднения TP автоматически смещается к средней цене позиции, сохраняя заданные расстояния и пропорции."
                color="rgba(200,214,229,0.35)"
              />
              <MiniToggle checked={tpSl.tpRepositionEnabled} onChange={(v) => upd("tpRepositionEnabled", v)} />

              {/* TP count stepper — hidden when per-level groups are active */}
              {!(proMode && tpSl.perLevelTpEnabled) && (
                <>
                  <div style={{ width: 1, height: 10, background: "rgba(255,255,255,0.1)" }} />
                  <div className="flex items-center" style={{ gap: 3 }}>
                    <span style={{ fontSize: 8.5, fontFamily: "monospace", opacity: 0.4, letterSpacing: "0.04em" }}>TP</span>
                    <div className="flex items-center" style={{ border: "1px solid rgba(255,255,255,0.1)", borderRadius: 3, overflow: "hidden" }}>
                      <button
                        onMouseDown={stopProp}
                        onClick={() => {
                          const n = Math.max(1, tpSl.multiTpCount - 1)
                          const lvls = tpSl.multiTpLevels.slice(0, n)
                          const pcts = distributeClose(n)
                          upd("multiTpCount", n)
                          upd("multiTpLevels", lvls.map((l, i) => ({ ...l, closePercent: pcts[i] })))
                          if (n === 1) upd("multiTpEnabled", false)
                        }}
                        style={{ padding: "0 4px", height: 16, background: "rgba(255,255,255,0.04)", border: "none", color: "rgba(200,214,229,0.55)", cursor: "pointer", fontSize: 10, lineHeight: 1 }}
                      >−</button>
                      <span style={{ padding: "0 5px", fontSize: 9.5, fontFamily: "monospace", color: "rgba(200,214,229,0.85)", background: "rgba(255,255,255,0.02)", minWidth: 16, textAlign: "center", lineHeight: "16px" }}>
                        {tpSl.multiTpCount}
                      </span>
                      <button
                        onMouseDown={stopProp}
                        onClick={() => {
                          const n = Math.min(10, tpSl.multiTpCount + 1)
                          const lvls = [...tpSl.multiTpLevels]
                          while (lvls.length < n) lvls.push({ tpPercent: parseFloat(((lvls[lvls.length - 1]?.tpPercent ?? 0) + 0.5).toFixed(2)), closePercent: 0 })
                          const pcts = distributeClose(n)
                          upd("multiTpCount", n)
                          upd("multiTpLevels", lvls.slice(0, n).map((l, i) => ({ ...l, closePercent: pcts[i] })))
                          if (n > 1) upd("multiTpEnabled", true)
                        }}
                        style={{ padding: "0 4px", height: 16, background: "rgba(255,255,255,0.04)", border: "none", color: "rgba(200,214,229,0.55)", cursor: "pointer", fontSize: 10, lineHeight: 1 }}
                      >+</button>
                    </div>
                  </div>
                </>
              )}

              {/* Divider */}
              <div style={{ width: 1, height: 10, background: "rgba(255,255,255,0.1)" }} />

              {/* Enable toggle */}
              <MiniToggle checked={tpSl.tpEnabled} onChange={(v) => upd("tpEnabled", v)} />
            </div>
          }
        />
        {open.tp && tpSl.tpEnabled && (
          <div style={{ ...gap4, marginTop: 4 }}>
            {/* Standard TP table — hidden when per-level groups are active */}
            {!(proMode && tpSl.perLevelTpEnabled) && (
              <>
                <div style={{ display: "grid", gridTemplateColumns: "18px 1fr 1fr", gap: 2, fontSize: 9, fontFamily: "monospace", opacity: 0.35, paddingLeft: 2 }}>
                  <span>#</span>
                  <span>TP %</span>
                  <span>Close %</span>
                </div>
                {tpSl.multiTpLevels.slice(0, tpSl.multiTpCount).map((lvl, i) => (
                  <div key={i} style={{ display: "grid", gridTemplateColumns: "18px 1fr 1fr", gap: 2, alignItems: "center" }}>
                    <span style={{ fontSize: 9, fontFamily: "monospace", opacity: 0.38 }}>{i + 1}</span>
                    <NI value={lvl.tpPercent} onChange={(v) => {
                      const next = [...tpSl.multiTpLevels]
                      next[i] = { ...next[i], tpPercent: v }
                      upd("multiTpLevels", next)
                    }} suffix="%" step={0.1} min={0} />
                    <NI value={lvl.closePercent} onChange={(v) => {
                      upd("multiTpLevels", rebalanceClose(tpSl.multiTpLevels.slice(0, tpSl.multiTpCount), i, v))
                    }} suffix="%" step={1} min={1} />
                  </div>
                ))}
              </>
            )}

            {/* Per-level TP groups — pro only */}
            {proMode && (
              <div style={{ borderTop: "1px solid rgba(255,255,255,0.05)", paddingTop: 4, ...gap4 }}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center" style={{ gap: 4 }}>
                    <LabelTooltip
                      label="Per-level groups"
                      tooltip="Разные настройки TP для каждой группы уровней сетки. После заполнения N-го ордера применяются свои TP-уровни."
                      color="rgba(200,214,229,0.4)"
                    />
                    {tpSl.perLevelTpEnabled && (
                      <button
                        onMouseDown={stopProp}
                        onClick={() => tog("perLevelGroups")}
                        style={{ background: "none", border: "none", cursor: "pointer", padding: 0, color: "rgba(200,214,229,0.35)", display: "flex", alignItems: "center" }}
                      >
                        <ChevronDown size={10} style={{ transform: open.perLevelGroups ? "rotate(0deg)" : "rotate(-90deg)", transition: "transform 0.15s" }} />
                      </button>
                    )}
                  </div>
                  <MiniToggle checked={tpSl.perLevelTpEnabled} onChange={(v) => upd("perLevelTpEnabled", v)} />
                </div>
                {tpSl.perLevelTpEnabled && open.perLevelGroups && (
                  <div style={{ ...gap4 }}>
                    {tpSl.perLevelTpGroups.map((grp, gi) => {
                      const grpTpCount = grp.tpCount ?? 1
                      const hasReset = grp.resetTpEnabled ?? false
                      return (
                        <div key={gi} style={{ borderLeft: `2px solid ${hasReset ? "rgba(255,171,0,0.35)" : "rgba(30,111,239,0.2)"}`, paddingLeft: 6, ...gap4 }}>
                          {/* Group header */}
                          <div className="flex items-center" style={{ gap: 4 }}>
                            <span style={{ fontSize: 8, fontFamily: "monospace", color: "rgba(200,214,229,0.35)", whiteSpace: "nowrap", letterSpacing: "0.04em" }}>
                              LVL {gi + 1}
                            </span>
                            <div className="flex items-center" style={{ gap: 3, marginLeft: 2 }}>
                              <span style={{ fontSize: 8, fontFamily: "monospace", color: hasReset ? "rgba(255,171,0,0.8)" : "rgba(200,214,229,0.3)", whiteSpace: "nowrap", letterSpacing: "0.04em" }}>
                                Reset TP
                              </span>
                              <TinyTooltipIcon
                                text="При срабатывании Reset TP запускается ребилд хвоста сетки: освободившаяся маржа + неиспользованный хвост пересоздаются в новые ордера. Обычный TP закрывает без ребилда."
                                color={hasReset ? "rgba(255,171,0,0.7)" : undefined}
                              />
                              <MiniToggle
                                checked={hasReset}
                                onChange={(v) => {
                                  upd("perLevelTpGroups", tpSl.perLevelTpGroups.map((g, idx) => {
                                    if (idx !== gi) return g
                                    const minCount = v ? Math.max(2, g.tpCount ?? 1) : g.tpCount ?? 1
                                    const lvls = [...g.levels]
                                    while (lvls.length < minCount) lvls.push({ tpPercent: parseFloat(((lvls[lvls.length - 1]?.tpPercent ?? 0) + 0.5).toFixed(2)), closePercent: 0 })
                                    const pcts = distributeClose(minCount)
                                    return { ...g, resetTpEnabled: v, tpCount: minCount, levels: lvls.slice(0, minCount).map((l, i) => ({ ...l, closePercent: pcts[i] })) }
                                  }))
                                }}
                              />
                            </div>
                            <div style={{ flex: 1 }} />
                            <div className="flex items-center" style={{ gap: 3 }}>
                              <span style={{ fontSize: 8, fontFamily: "monospace", opacity: 0.35, letterSpacing: "0.04em" }}>TP</span>
                              <div className="flex items-center" style={{ border: "1px solid rgba(255,255,255,0.1)", borderRadius: 3, overflow: "hidden" }}>
                                <button
                                  onMouseDown={stopProp}
                                  onClick={() => {
                                    const minAllowed = hasReset ? 2 : 1
                                    const n = Math.max(minAllowed, grpTpCount - 1)
                                    const lvls = grp.levels.slice(0, n)
                                    const pcts = distributeClose(n)
                                    const next = [...tpSl.perLevelTpGroups]
                                    next[gi] = { ...next[gi], tpCount: n, levels: lvls.map((l, i) => ({ ...l, closePercent: pcts[i] })) }
                                    upd("perLevelTpGroups", next)
                                  }}
                                  style={{ padding: "0 4px", height: 15, background: "rgba(255,255,255,0.04)", border: "none", color: "rgba(200,214,229,0.55)", cursor: "pointer", fontSize: 10, lineHeight: 1 }}
                                >−</button>
                                <span style={{ padding: "0 4px", fontSize: 9, fontFamily: "monospace", color: "rgba(200,214,229,0.85)", background: "rgba(255,255,255,0.02)", minWidth: 14, textAlign: "center", lineHeight: "15px" }}>
                                  {grpTpCount}
                                </span>
                                <button
                                  onMouseDown={stopProp}
                                  onClick={() => {
                                    const n = Math.min(10, grpTpCount + 1)
                                    const lvls = [...grp.levels]
                                    while (lvls.length < n) lvls.push({ tpPercent: parseFloat(((lvls[lvls.length - 1]?.tpPercent ?? 0) + 0.5).toFixed(2)), closePercent: 0 })
                                    const pcts = distributeClose(n)
                                    const next = [...tpSl.perLevelTpGroups]
                                    next[gi] = { ...next[gi], tpCount: n, levels: lvls.slice(0, n).map((l, i) => ({ ...l, closePercent: pcts[i] })) }
                                    upd("perLevelTpGroups", next)
                                  }}
                                  style={{ padding: "0 4px", height: 15, background: "rgba(255,255,255,0.04)", border: "none", color: "rgba(200,214,229,0.55)", cursor: "pointer", fontSize: 10, lineHeight: 1 }}
                                >+</button>
                              </div>
                            </div>
                          </div>
                          {grp.levels.slice(0, grpTpCount).map((lvl, li) => {
                            const isResetRow = hasReset && li === 0
                            const tpLabel = hasReset ? (li === 0 ? "Reset TP %" : "Main TP %") : "TP %"
                            const tpColor = isResetRow ? "rgba(255,171,0,0.55)" : undefined
                            return (
                              <div key={li} style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 2, alignItems: "center" }}>
                                <NI
                                  value={lvl.tpPercent}
                                  onChange={(v) => {
                                    upd("perLevelTpGroups", tpSl.perLevelTpGroups.map((g, idx) => idx !== gi ? g : { ...g, levels: g.levels.map((l, lx) => lx !== li ? l : { ...l, tpPercent: v }) }))
                                  }}
                                  label={tpLabel}
                                  labelColor={tpColor}
                                  step={0.1}
                                  min={0}
                                  tooltip={isResetRow ? "Reset TP: при срабатывании запускается ребилд хвоста сетки — освободившаяся маржа + неиспользованный хвост пересоздаются в новые ордера" : undefined}
                                />
                                <NI
                                  value={lvl.closePercent}
                                  onChange={(v) => {
                                    upd("perLevelTpGroups", tpSl.perLevelTpGroups.map((g, idx) => {
                                      if (idx !== gi) return g
                                      const tpCnt = g.tpCount ?? 1
                                      const rebalanced = rebalanceClose(g.levels.slice(0, tpCnt), li, v)
                                      return { ...g, levels: g.levels.map((l, lx) => lx < tpCnt ? rebalanced[lx] : l) }
                                    }))
                                  }}
                                  label="Close %"
                                  step={1}
                                  min={1}
                                  tooltip={isResetRow ? "Процент позиции закрытый при Reset TP. Освободившаяся маржа идёт на ребилд хвоста сетки" : undefined}
                                />
                              </div>
                            )
                          })}
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
        {open.tp && !tpSl.tpEnabled && (
          <div style={{ fontSize: 9, fontFamily: "monospace", color: "rgba(200,214,229,0.3)", padding: "4px 0" }}>
            Take profit disabled
          </div>
        )}
      </div>
      <Divider />

      {/* ── STOP LOSS ─────────────────────────────── */}
      {/* When !multiPositionMode: shared across all grids on this side */}
      <div style={{ marginBottom: 6 }}>
        <SectionHead
          title="STOP LOSS"
          expanded={open.sl}
          onToggle={() => tog("sl")}
          rightSlot={<MiniToggle checked={tpSl.slEnabled} onChange={(v) => upd("slEnabled", v)} />}
        />
        {open.sl && tpSl.slEnabled && (
          <div style={{ ...gap4, marginTop: 4 }}>
            <div style={{ display: "flex", alignItems: "center", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 4, overflow: "hidden" }}>
              {([
                {
                  v: "extreme_order" as const,
                  label: "Extreme Order",
                  tooltip: "SL размещается на заданном расстоянии (%) от крайнего (последнего) ордера сетки.\n\nПример: сетка из 8 ордеров, нижний ордер на 65 000 USDT, SL 2.5% → стоп на 63 375 USDT.\n\nСтоп отображается как превью сразу при настройке сетки. После входа в позицию становится реальным ордером.",
                },
                {
                  v: "avg_entry" as const,
                  label: "Avg Entry",
                  tooltip: "SL рассчитывается от средней цены входа в позицию (средневзвешенная по всем исполненным ордерам).\n\nСтоп автоматически перемещается после каждого усреднения, сохраняя заданный % от новой средней цены.\n\nПодходит для управления риском всей позиции при постепенном накоплении.",
                },
              ] as const).map((o, i, arr) => (
                <div key={o.v} style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center",
                  background: tpSl.slMode === o.v ? "rgba(30,111,239,0.18)" : "transparent",
                  borderRight: i < arr.length - 1 ? "1px solid rgba(255,255,255,0.1)" : undefined,
                }}>
                  <button
                    onClick={() => upd("slMode", o.v)}
                    onMouseDown={(e) => e.stopPropagation()}
                    style={{
                      flex: 1, fontSize: 9, fontFamily: "monospace", padding: "2px 6px",
                      background: "transparent", border: "none", cursor: "pointer",
                      color: tpSl.slMode === o.v ? "#1e6fef" : "rgba(255,255,255,0.35)",
                      fontWeight: tpSl.slMode === o.v ? 700 : 400, letterSpacing: "0.04em",
                    }}
                  >{o.label}</button>
                  <TinyTooltipIcon text={o.tooltip} color={tpSl.slMode === o.v ? "rgba(30,111,239,0.7)" : undefined} />
                  <div style={{ width: 4 }} />
                </div>
              ))}
            </div>
            <div className="grid grid-cols-2" style={{ gap: 4 }}>
              <NI value={tpSl.slPercent} onChange={(v) => upd("slPercent", v)} label="SL %" min={0} step={0.1} title="Stop loss percentage" />
              <NI value={tpSl.slClosePercent} onChange={(v) => upd("slClosePercent", Math.min(100, Math.max(1, v)))} label="Close %" min={1} title="Percentage of position to close at stop loss" />
            </div>
          </div>
        )}
        {open.sl && !tpSl.slEnabled && (
          <div style={{ fontSize: 9, fontFamily: "monospace", color: "rgba(200,214,229,0.3)", padding: "4px 0" }}>
            Stop loss disabled
          </div>
        )}
      </div>

      {/* ── ACTIONS ──────────────────────────────────── */}
      <div className="flex gap-2 sticky bottom-0" style={{ paddingTop: 6, paddingBottom: 2, background: "rgba(13,17,25,0.95)" }}>
        <button
          onClick={() => { setCfg({ ...DEFAULT_GRID_CONFIG, symbol: cfg.symbol, side: cfg.side, entryPrice: cfg.entryPrice, leverage: cfg.leverage }); if (isPlacedRef.current) markGridPendingUpdate(consoleIdRef.current) }}
          className="flex items-center justify-center gap-1"
          style={{
            fontSize: 10, fontFamily: "monospace", fontWeight: 600, padding: "6px 10px",
            background: "rgba(255,255,255,0.04)", color: "rgba(200,214,229,0.6)",
            border: "1px solid rgba(255,255,255,0.1)", borderRadius: 4, cursor: "pointer", flexShrink: 0,
          }}
          onMouseDown={stopProp}
          title="Reset all settings to defaults"
        >
          <RotateCcw size={10} /> Reset
        </button>
        {/* When the position has fills, "Apply Changes" is hidden — structural re-config is impossible. */}
        {hasPendingUpdate && positionHasFills ? (
          <div
            className="flex items-center justify-center gap-1.5 flex-1"
            style={{
              fontSize: 10, fontFamily: "monospace", fontWeight: 600, padding: "7px 0",
              background: "rgba(255,255,255,0.03)",
              color: "rgba(255,255,255,0.25)",
              border: "1px solid rgba(255,255,255,0.08)",
              borderRadius: 4,
            }}
          >
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none" style={{ flexShrink: 0 }}>
              <rect x="2" y="4.5" width="6" height="4.5" rx="1" stroke="currentColor" strokeWidth="1.2"/>
              <path d="M3.5 4.5V3a1.5 1.5 0 013 0v1.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
            </svg>
            Grid locked · has fills
          </div>
        ) : (
          <button
            className="flex items-center justify-center gap-1.5 flex-1"
            onClick={handlePlaceGrid}
            style={{
              fontSize: 11, fontFamily: "monospace", fontWeight: 700, padding: "7px 0",
              background: hasPendingUpdate
                ? "rgba(251,191,36,0.18)"
                : cfg.side === "long" ? "rgba(0,229,160,0.18)" : "rgba(248,113,113,0.15)",
              color: hasPendingUpdate
                ? "rgba(251,191,36,0.9)"
                : cfg.side === "long" ? "#00e5a0" : "#f87171",
              border: `1px solid ${hasPendingUpdate
                ? "rgba(251,191,36,0.45)"
                : cfg.side === "long" ? "rgba(0,229,160,0.45)" : "rgba(248,113,113,0.4)"}`,
              borderRadius: 4, cursor: activeChartId ? "pointer" : "not-allowed", opacity: activeChartId ? 1 : 0.5,
            }}
            onMouseDown={stopProp}
            disabled={!activeChartId}
            title={hasPendingUpdate ? "Применить изменения к размещённым ордерам" : cfg.side === "long" ? "Place Long grid orders on chart" : "Place Short grid orders on chart"}
          >
            {cfg.autoEnabled && <Play size={11} />}
            {hasPendingUpdate
              ? `Apply Changes #${activeSlotIndex + 1}`
              : isPlaced
                ? `${cfg.side === "long" ? "Long" : "Short"} / Grid #${activeSlotIndex + 1} ✓`
                : `${cfg.side === "long" ? "Long" : "Short"} / Grid${gridSlots.length > 1 ? ` #${activeSlotIndex + 1}` : ""}`
            }
          </button>
        )}
      </div>
      </div>
    </div>
  )
})
