import { useState, useCallback, useEffect, useMemo } from "react"
import { ChevronDown, ChevronUp, TriangleAlert as AlertTriangle, Play, BookOpen, Save } from "lucide-react"
import type { DcaConfig, DcaMultiTpLevel, DcaPerLevelResetSetting } from "@/types/terminal"
import { DEFAULT_DCA_CONFIG } from "@/types/terminal"
import { TemplateBar } from "@/components/terminal/TemplateBar"
import { useTemplates } from "@/hooks/useTemplates"

// ── Primitive UI helpers (terminal-native, no external component) ──────────

const monoSm: React.CSSProperties = {
  fontSize: 10, fontFamily: "monospace",
}
const inputBase: React.CSSProperties = {
  background: "rgba(255,255,255,0.04)",
  border: "1px solid rgba(255,255,255,0.1)",
  borderRadius: 4,
  color: "rgba(200,214,229,0.9)",
  padding: "4px 8px",
  fontSize: 11,
  fontFamily: "monospace",
  width: "100%",
  outline: "none",
}
const labelStyle: React.CSSProperties = {
  fontSize: 9,
  fontFamily: "monospace",
  opacity: 0.4,
  textTransform: "uppercase",
  letterSpacing: "0.06em",
  marginBottom: 2,
  display: "block",
}

function NumInput({
  value, onChange, placeholder, min, step, disabled, title,
}: {
  value: number | string; onChange: (v: number) => void
  placeholder?: string; min?: number; step?: number; disabled?: boolean; title?: string
}) {
  return (
    <input
      type="number"
      value={value}
      onChange={(e) => onChange(parseFloat(e.target.value) || 0)}
      placeholder={placeholder}
      min={min}
      step={step}
      disabled={disabled}
      title={title ?? placeholder}
      style={{ ...inputBase, opacity: disabled ? 0.4 : 1 }}
      onMouseDown={(e) => e.stopPropagation()}
    />
  )
}

function Seg<T extends string>({
  options, value, onChange,
}: {
  options: { v: T; label: string; title?: string }[]
  value: T; onChange: (v: T) => void
}) {
  return (
    <div
      className="flex rounded overflow-hidden"
      style={{ border: "1px solid rgba(255,255,255,0.1)" }}
    >
      {options.map((o) => (
        <button
          key={o.v}
          onClick={() => onChange(o.v)}
          title={o.title}
          style={{
            flex: 1,
            fontSize: 9,
            fontFamily: "monospace",
            padding: "2px 0",
            background: value === o.v ? "rgba(30,111,239,0.15)" : "transparent",
            color: value === o.v ? "#1e6fef" : "rgba(255,255,255,0.35)",
            border: "none",
            cursor: "pointer",
            transition: "all 0.1s",
            fontWeight: value === o.v ? 700 : 400,
            letterSpacing: "0.04em",
          }}
          onMouseDown={(e) => e.stopPropagation()}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

function SideToggle({
  value, onChange, marketType = "futures",
}: {
  value: "LONG" | "SHORT"
  onChange: (v: "LONG" | "SHORT") => void
  marketType?: "spot" | "futures"
}) {
  const labels: Record<"LONG" | "SHORT", string> = marketType === "spot"
    ? { LONG: "BUY", SHORT: "SELL" }
    : { LONG: "LONG", SHORT: "SHORT" }
  const tooltips: Record<"LONG" | "SHORT", string> = marketType === "spot"
    ? { LONG: "Buy — open long position", SHORT: "Sell — open short position" }
    : { LONG: "Long — profit when price goes up", SHORT: "Short — profit when price goes down" }
  return (
    <div
      className="flex rounded overflow-hidden"
      style={{ border: "1px solid rgba(255,255,255,0.1)" }}
      title={tooltips[value]}
    >
      {(["LONG", "SHORT"] as const).map((s) => {
        const active = value === s
        const isLong = s === "LONG"
        return (
          <button
            key={s}
            onClick={() => onChange(s)}
            title={tooltips[s]}
            style={{
              flex: 1, fontSize: 10, fontFamily: "monospace", fontWeight: 700,
              padding: "3px 0", border: "none", cursor: "pointer",
              background: active ? (isLong ? "rgba(0,229,160,0.15)" : "rgba(255,71,87,0.15)") : "transparent",
              color: active ? (isLong ? "#00e5a0" : "#ff4757") : "rgba(255,255,255,0.3)",
              borderBottom: active ? `2px solid ${isLong ? "#1a7a5a" : "#c02030"}` : "2px solid transparent",
              letterSpacing: "0.05em",
              transition: "all 0.15s",
            }}
            onMouseDown={(e) => e.stopPropagation()}
          >
            {labels[s]}
          </button>
        )
      })}
    </div>
  )
}

function Toggle({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <div
      className="flex items-center gap-2 cursor-pointer select-none"
      onClick={() => onChange(!checked)}
      onMouseDown={(e) => e.stopPropagation()}
    >
      <div
        style={{
          width: 28, height: 14, borderRadius: 7,
          background: checked ? "rgba(30,111,239,0.4)" : "rgba(255,255,255,0.1)",
          border: `1px solid ${checked ? "rgba(30,111,239,0.6)" : "rgba(255,255,255,0.15)"}`,
          position: "relative", flexShrink: 0, transition: "background 0.15s",
        }}
      >
        <div style={{
          position: "absolute", top: 1, left: checked ? 13 : 1,
          width: 10, height: 10, borderRadius: "50%",
          background: checked ? "#1e6fef" : "rgba(255,255,255,0.35)",
          transition: "left 0.15s",
        }} />
      </div>
      <span style={{ ...monoSm, fontSize: 11, opacity: checked ? 0.85 : 0.45 }}>{label}</span>
    </div>
  )
}

function SectionHeader({ title, expanded, onToggle, badge }: { title: string; expanded: boolean; onToggle: () => void; badge?: React.ReactNode }) {
  return (
    <button
      className="flex items-center justify-between w-full"
      style={{ background: "transparent", border: "none", padding: "4px 0", cursor: "pointer" }}
      onClick={onToggle}
      onMouseDown={(e) => e.stopPropagation()}
    >
      <span className="flex items-center gap-1.5" style={{ ...monoSm, color: "rgba(255,255,255,0.5)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
        {title}
        {badge}
      </span>
      {expanded ? <ChevronUp size={10} style={{ opacity: 0.4 }} /> : <ChevronDown size={10} style={{ opacity: 0.4 }} />}
    </button>
  )
}

function PctButtons({ onPct }: { onPct: (pct: number) => void }) {
  return (
    <div className="flex gap-1 mt-0.5">
      {[25, 50, 75, 100].map((p) => (
        <button
          key={p}
          onClick={() => onPct(p)}
          title={`Set budget to ${p}% of available balance`}
          style={{
            flex: 1, fontSize: 9, fontFamily: "monospace", padding: "1px 0",
            background: "rgba(255,255,255,0.04)",
            color: "rgba(255,255,255,0.4)",
            border: "1px solid rgba(255,255,255,0.07)",
            borderRadius: 3, cursor: "pointer",
          }}
          onMouseDown={(e) => e.stopPropagation()}
        >
          {p}%
        </button>
      ))}
    </div>
  )
}

function StatRow({ label, value, highlight }: { label: string; value: string | number; highlight?: "green" | "red" | "blue" }) {
  const color = highlight === "green" ? "#00e5a0" : highlight === "red" ? "#ff4757" : highlight === "blue" ? "#1e6fef" : "rgba(200,214,229,0.85)"
  return (
    <div className="flex justify-between items-center" style={{ padding: "2px 0", borderBottom: "1px solid rgba(255,255,255,0.03)" }}>
      <span style={{ ...monoSm, opacity: 0.45 }}>{label}</span>
      <span style={{ ...monoSm, fontSize: 11, color, fontWeight: 600 }}>{value}</span>
    </div>
  )
}

// ── Derived preview calculations ──────────────────────────────────────────

function calcPreview(cfg: DcaConfig) {
  const { entry, dca, take_profit, stop_loss } = cfg
  const entryPrice = entry.type === "market" ? cfg.entry.price : cfg.entry.price
  const orders = dca.orders_count
  const budget = dca.total_budget

  // Estimate qty distribution
  let totalQty = 0
  let totalCost = 0
  const qtys: number[] = []
  if (dca.qty_mode === "fixed") {
    const baseQty = budget / (entryPrice * orders)
    for (let i = 0; i < orders; i++) qtys.push(baseQty)
  } else {
    let base = 1
    let sum = 0
    for (let i = 0; i < orders; i++) { sum += base; base *= dca.qty_multiplier }
    const scale = budget / (sum * entryPrice)
    base = 1
    for (let i = 0; i < orders; i++) { qtys.push(base * scale); base *= dca.qty_multiplier }
  }
  let weightedPriceSum = 0
  for (let i = 0; i < orders; i++) {
    const priceDrop = i === 0 ? 0 : dca.first_offset_percent + (i - 1) * dca.step_percent
    const levelPrice = entryPrice * (1 - priceDrop / 100)
    totalQty += qtys[i]
    totalCost += qtys[i] * levelPrice
    weightedPriceSum += qtys[i] * levelPrice
  }
  const avgEntry = totalQty > 0 ? weightedPriceSum / totalQty : entryPrice
  const tpPrice = take_profit.enabled ? avgEntry * (1 + take_profit.percent / 100) : null
  const slPrice = stop_loss.enabled ? avgEntry * (1 - stop_loss.percent / 100) : null
  const maxMargin = (budget / cfg.leverage).toFixed(2)

  return {
    orders,
    maxPositionQty: totalQty.toFixed(4),
    maxPositionUsdt: budget.toFixed(2),
    maxMarginUsdt: maxMargin,
    avgEntry: avgEntry.toFixed(2),
    tpPrice: tpPrice ? tpPrice.toFixed(2) : null,
    slPrice: slPrice ? slPrice.toFixed(2) : null,
  }
}

// ── Validation ──────────────────────────────────────────────────────────

function validateDca(cfg: DcaConfig): string[] {
  const errors: string[] = []
  if (!cfg.symbol) errors.push("Symbol required")
  if (cfg.leverage < 1) errors.push("Leverage must be ≥ 1")
  if (cfg.entry.price <= 0) errors.push("Entry price must be > 0")
  if (cfg.dca.total_budget <= 0) errors.push("Total budget must be > 0")
  if (cfg.dca.orders_count < 1) errors.push("Orders count must be ≥ 1")
  if (cfg.dca.step_percent <= 0) errors.push("Step % must be > 0")
  if (cfg.take_profit.enabled && cfg.take_profit.percent <= 0) errors.push("TP % must be > 0")
  if (cfg.stop_loss.enabled && cfg.stop_loss.percent <= 0) errors.push("SL % must be > 0")
  return errors
}

// ── Props ────────────────────────────────────────────────────────────────

interface DcaTabProps {
  symbol?: string
  futuresSide?: "long" | "short"
  entryPrice?: number
  availableBalance?: number
  leverage?: number
  onSideChange?: (side: "long" | "short") => void
}

// ── Main component ───────────────────────────────────────────────────────

export function DcaTab({
  symbol: externalSymbol,
  futuresSide: externalFuturesSide,
  entryPrice: externalEntryPrice,
  availableBalance = 10000,
  leverage: externalLeverage,
  onSideChange,
}: DcaTabProps) {
  const [cfg, setCfg] = useState<DcaConfig>({
    ...DEFAULT_DCA_CONFIG,
    symbol: externalSymbol ?? DEFAULT_DCA_CONFIG.symbol,
    position_side: externalFuturesSide === "short" ? "SHORT" : "LONG",
    leverage: externalLeverage ?? DEFAULT_DCA_CONFIG.leverage,
    entry: {
      ...DEFAULT_DCA_CONFIG.entry,
      price: externalEntryPrice ?? DEFAULT_DCA_CONFIG.entry.price,
    },
  })

  // Sync from active chart
  useEffect(() => {
    if (externalSymbol) setCfg((p) => ({ ...p, symbol: externalSymbol }))
  }, [externalSymbol])

  useEffect(() => {
    if (externalEntryPrice && externalEntryPrice > 0) {
      setCfg((p) => ({ ...p, entry: { ...p.entry, price: externalEntryPrice } }))
    }
  }, [externalEntryPrice])

  useEffect(() => {
    if (externalLeverage && externalLeverage > 0) {
      setCfg((p) => ({ ...p, leverage: externalLeverage }))
    }
  }, [externalLeverage])

  useEffect(() => {
    if (externalFuturesSide) {
      setCfg((p) => ({ ...p, position_side: externalFuturesSide === "short" ? "SHORT" : "LONG" }))
    }
  }, [externalFuturesSide])

  const [sections, setSections] = useState({
    entry: true,
    dca: true,
    tp: true,
    sl: true,
    resetTp: false,
  })
  const [showConfirm, setShowConfirm] = useState(false)
  const [validationResult, setValidationResult] = useState<{ errors: string[]; config: DcaConfig } | null>(null)
  const [multiTpLevels, setMultiTpLevels] = useState<DcaMultiTpLevel[]>([
    { tpPercent: 0.8, closePercent: 50 },
    { tpPercent: 1.5, closePercent: 50 },
  ])
  const [perLevelSettings, setPerLevelSettings] = useState<DcaPerLevelResetSetting[]>([])

  const toggle = (k: keyof typeof sections) => setSections((p) => ({ ...p, [k]: !p[k] }))
  const stopProp = (e: React.MouseEvent) => e.stopPropagation()

  const setEntry = useCallback(<K extends keyof DcaConfig["entry"]>(k: K, v: DcaConfig["entry"][K]) => {
    setCfg((p) => ({ ...p, entry: { ...p.entry, [k]: v } }))
  }, [])
  const setDca = useCallback(<K extends keyof DcaConfig["dca"]>(k: K, v: DcaConfig["dca"][K]) => {
    setCfg((p) => ({ ...p, dca: { ...p.dca, [k]: v } }))
  }, [])
  const setTp = useCallback(<K extends keyof DcaConfig["take_profit"]>(k: K, v: DcaConfig["take_profit"][K]) => {
    setCfg((p) => ({ ...p, take_profit: { ...p.take_profit, [k]: v } }))
  }, [])
  const setSl = useCallback(<K extends keyof DcaConfig["stop_loss"]>(k: K, v: DcaConfig["stop_loss"][K]) => {
    setCfg((p) => ({ ...p, stop_loss: { ...p.stop_loss, [k]: v } }))
  }, [])
  const setRtp = useCallback(<K extends keyof DcaConfig["reset_tp"]>(k: K, v: DcaConfig["reset_tp"][K]) => {
    setCfg((p) => ({ ...p, reset_tp: { ...p.reset_tp, [k]: v } }))
  }, [])

  const handleBudgetPct = (pct: number) => {
    const total = availableBalance * cfg.leverage
    setDca("total_budget", parseFloat(((pct / 100) * total).toFixed(2)))
  }

  const toggleTriggerLevel = (level: number) => {
    setCfg((p) => {
      const tls = p.reset_tp.trigger_levels
      const next = tls.includes(level) ? tls.filter((l) => l !== level) : [...tls, level].sort((a, b) => a - b)
      return { ...p, reset_tp: { ...p.reset_tp, trigger_levels: next } }
    })
  }

  // Rebuild per-level settings when orders count changes
  useEffect(() => {
    const n = cfg.dca.orders_count
    setPerLevelSettings((prev) => {
      const next: DcaPerLevelResetSetting[] = []
      for (let i = 1; i <= n; i++) {
        const existing = prev.find((s) => s.level === i)
        next.push(existing ?? { level: i, resetTpPercent: cfg.reset_tp.reset_tp_percent, closePercent: cfg.reset_tp.reset_close_percent })
      }
      return next
    })
  }, [cfg.dca.orders_count, cfg.reset_tp.reset_tp_percent, cfg.reset_tp.reset_close_percent])

  const preview = useMemo(() => calcPreview(cfg), [cfg])

  const handleStartDca = () => {
    const errors = validateDca(cfg)
    const finalConfig: DcaConfig = {
      ...cfg,
      take_profit: { ...cfg.take_profit, levels: cfg.take_profit.multi_tp_enabled ? multiTpLevels : [] },
      reset_tp: {
        ...cfg.reset_tp,
        per_level_settings: cfg.reset_tp.per_level_settings_enabled ? perLevelSettings : [],
      },
    }
    setValidationResult({ errors, config: finalConfig })
    if (errors.length === 0) setShowConfirm(true)
  }

  const ticker = cfg.symbol.split("/")[0] ?? cfg.symbol

  const { templates: dcaTemplates, saveTemplate: saveDcaTemplate, deleteTemplate: deleteDcaTemplate } = useTemplates<DcaConfig>("dca")
  const [activeDcaTemplateId, setActiveDcaTemplateId] = useState<string | null>(null)
  const [savedDcaCfgJson, setSavedDcaCfgJson] = useState<string | null>(null)

  const cfgForDcaTemplate = { ...cfg, symbol: "", entry: { ...cfg.entry, price: 0 } }
  const isDcaDirty = activeDcaTemplateId !== null && savedDcaCfgJson !== JSON.stringify(cfgForDcaTemplate)

  const handleSelectDcaTemplate = (t: { id: string; config: DcaConfig }) => {
    setCfg((prev) => ({ ...t.config, symbol: prev.symbol, entry: { ...t.config.entry, price: prev.entry.price } }))
    setActiveDcaTemplateId(t.id)
    setSavedDcaCfgJson(JSON.stringify({ ...t.config, symbol: "", entry: { ...t.config.entry, price: 0 } }))
  }

  const handleSaveDcaTemplate = (name: string) => {
    saveDcaTemplate(name, cfgForDcaTemplate)
    setTimeout(() => {
      const all = JSON.parse(localStorage.getItem("crypterm:templates:dca") ?? "[]") as Array<{ id: string; name: string }>
      const found = all.find((t) => t.name === name)
      if (found) { setActiveDcaTemplateId(found.id); setSavedDcaCfgJson(JSON.stringify(cfgForDcaTemplate)) }
    }, 0)
  }

  return (
    <div
      className="flex flex-col h-full overflow-auto"
      onMouseDown={stopProp}
    >
      {/* ── Templates ──────────────────────────────────── */}
      <TemplateBar
        templates={dcaTemplates}
        activeId={activeDcaTemplateId}
        onSelect={handleSelectDcaTemplate}
        onSave={handleSaveDcaTemplate}
        onDelete={(id) => { deleteDcaTemplate(id); if (id === activeDcaTemplateId) { setActiveDcaTemplateId(null); setSavedDcaCfgJson(null) } }}
        isDirty={isDcaDirty}
      />
      <div style={{ padding: "8px 10px" }}>
      {/* ── 1. Header context ─────────────────────────── */}
      <div style={{ marginBottom: 6 }}>
        {/* Long / Short — first, user decides direction before anything else */}
        <div className="mb-1.5">
          <SideToggle
            value={cfg.position_side}
            onChange={(s) => {
              setCfg((p) => ({ ...p, position_side: s }))
              onSideChange?.(s.toLowerCase() as "long" | "short")
            }}
          />
        </div>

        {/* Symbol + Leverage */}
        <div className="flex gap-2">
          <div className="flex-1">
            <input
              type="text"
              value={cfg.symbol}
              onChange={(e) => setCfg((p) => ({ ...p, symbol: e.target.value }))}
              placeholder="Symbol"
              title="Trading pair (e.g. BTC/USDT)"
              style={{ ...inputBase, fontWeight: 700, color: "rgba(200,214,229,0.95)" }}
              onMouseDown={stopProp}
            />
          </div>
          <NumInput
            value={cfg.leverage}
            onChange={(v) => setCfg((p) => ({ ...p, leverage: Math.max(1, v) }))}
            placeholder="Lev×"
            title="Leverage multiplier (1× = no leverage)"
            min={1}
          />
        </div>
      </div>

      {/* ── 2. Entry ──────────────────────────────────── */}
      <div style={{ borderBottom: "1px solid rgba(255,255,255,0.05)", paddingBottom: 6, marginBottom: 6 }}>
        <SectionHeader title="Entry" expanded={sections.entry} onToggle={() => toggle("entry")} />
        {sections.entry && (
          <div className="flex flex-col gap-1.5 mt-1">
            <NumInput
              value={cfg.entry.price}
              onChange={(v) => setEntry("price", v)}
              placeholder="Entry Price"
              title="Limit price for the first (entry) order"
              min={0}
            />
          </div>
        )}
      </div>

      {/* ── 3. DCA Grid ───────────────────────────────── */}
      <div style={{ borderBottom: "1px solid rgba(255,255,255,0.05)", paddingBottom: 8, marginBottom: 8 }}>
        <SectionHeader title="DCA Grid" expanded={sections.dca} onToggle={() => toggle("dca")} />
        {sections.dca && (
          <div className="flex flex-col gap-1.5 mt-1">
            {/* Budget */}
            <NumInput
              value={cfg.dca.total_budget}
              onChange={(v) => setDca("total_budget", v)}
              placeholder="Total Budget (USDT)"
              title="Total capital to allocate across all DCA orders"
              min={0}
            />
            <PctButtons onPct={handleBudgetPct} />

            {/* Orders */}
            <NumInput
              value={cfg.dca.orders_count}
              onChange={(v) => setDca("orders_count", Math.max(1, Math.round(v)))}
              placeholder="Orders Count"
              title="Number of limit orders in the DCA grid"
              min={1}
            />

            {/* Placement mode */}
            <Seg
              options={[
                { v: "step_percent", label: "Step %", title: "Place orders at equal percentage steps below entry" },
                { v: "price_range", label: "Range", title: "Distribute orders evenly across a price range" },
              ] as const}
              value={cfg.dca.placement_mode}
              onChange={(v) => setDca("placement_mode", v)}
            />

            {cfg.dca.placement_mode === "step_percent" ? (
              <div className="grid grid-cols-2 gap-1.5">
                <NumInput
                  value={cfg.dca.first_offset_percent}
                  onChange={(v) => setDca("first_offset_percent", v)}
                  placeholder="First Offset %"
                  title="Price distance (%) from entry to 2nd order"
                  step={0.1}
                />
                <NumInput
                  value={cfg.dca.step_percent}
                  onChange={(v) => setDca("step_percent", v)}
                  placeholder="Step %"
                  title="Price step (%) between consecutive DCA orders"
                  step={0.1}
                />
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-1.5">
                <NumInput
                  value={cfg.dca.price_range_from ?? cfg.entry.price * 0.99}
                  onChange={(v) => setDca("price_range_from", v)}
                  placeholder="Range From"
                  title="Upper price bound for order distribution"
                />
                <NumInput
                  value={cfg.dca.price_range_to ?? cfg.entry.price * 0.95}
                  onChange={(v) => setDca("price_range_to", v)}
                  placeholder="Range To"
                  title="Lower price bound for order distribution"
                />
              </div>
            )}

            {/* Qty mode */}
            <Seg
              options={[
                { v: "fixed", label: "Fixed", title: "Equal quantity on every order" },
                { v: "multiplier", label: "Multiplier", title: "Each order is larger than the previous by a multiplier" },
              ] as const}
              value={cfg.dca.qty_mode}
              onChange={(v) => setDca("qty_mode", v)}
            />
            {cfg.dca.qty_mode === "multiplier" && (
              <NumInput
                value={cfg.dca.qty_multiplier}
                onChange={(v) => setDca("qty_multiplier", Math.max(1, v))}
                placeholder="Multiplier"
                title="Each subsequent order is this many times larger than the previous"
                step={0.05}
              />
            )}

            {/* Max position preview */}
            <div
              style={{
                ...inputBase,
                background: "rgba(30,111,239,0.04)",
                border: "1px solid rgba(30,111,239,0.12)",
                color: "rgba(100,160,255,0.7)",
                display: "flex", justifyContent: "space-between",
              }}
            >
              <span style={{ opacity: 0.5, fontSize: 10 }}>Max position</span>
              <span style={{ fontSize: 10 }}>
                {preview.maxPositionQty} {ticker} / ${preview.maxPositionUsdt}
              </span>
            </div>
          </div>
        )}
      </div>

      {/* ── 4. Take Profit ────────────────────────────── */}
      <div style={{ borderBottom: "1px solid rgba(255,255,255,0.05)", paddingBottom: 8, marginBottom: 8 }}>
        <SectionHeader
          title="Take Profit"
          expanded={sections.tp}
          onToggle={() => toggle("tp")}
          badge={
            <span style={{
              fontSize: 9, padding: "0 4px", borderRadius: 3,
              background: cfg.take_profit.enabled ? "rgba(0,229,160,0.15)" : "rgba(255,255,255,0.07)",
              color: cfg.take_profit.enabled ? "#00e5a0" : "rgba(255,255,255,0.3)",
            }}>
              {cfg.take_profit.enabled ? "ON" : "OFF"}
            </span>
          }
        />
        {sections.tp && (
          <div className="flex flex-col gap-1.5 mt-1">
            <Toggle checked={cfg.take_profit.enabled} onChange={(v) => setTp("enabled", v)} label="Enable TP" />

            {cfg.take_profit.enabled && (
              <>
                <div className="grid grid-cols-2 gap-1.5">
                  <NumInput
                    value={cfg.take_profit.percent}
                    onChange={(v) => setTp("percent", v)}
                    placeholder="TP %"
                    step={0.1}
                  />
                  <NumInput
                    value={cfg.take_profit.close_percent}
                    onChange={(v) => setTp("close_percent", v)}
                    placeholder="Close %"
                    min={1}
                  />
                </div>

                <Toggle
                  checked={cfg.take_profit.multi_tp_enabled}
                  onChange={(v) => setTp("multi_tp_enabled", v)}
                  label="Multi TP"
                />

                {cfg.take_profit.multi_tp_enabled && (
                  <div
                    style={{
                      background: "rgba(255,255,255,0.02)",
                      border: "1px solid rgba(255,255,255,0.06)",
                      borderRadius: 4, padding: "4px 6px",
                    }}
                  >
                    {multiTpLevels.map((lvl, idx) => (
                      <div key={idx} className="flex gap-1 items-center mb-1">
                        <span style={{ ...monoSm, opacity: 0.4, width: 12 }}>{idx + 1}</span>
                        <input
                          type="number"
                          value={lvl.tpPercent}
                          onChange={(e) => setMultiTpLevels((prev) => prev.map((l, j) => j === idx ? { ...l, tpPercent: parseFloat(e.target.value) || 0 } : l))}
                          placeholder="TP%"
                          style={{ ...inputBase, flex: 1, fontSize: 10 }}
                          onMouseDown={stopProp}
                        />
                        <input
                          type="number"
                          value={lvl.closePercent}
                          onChange={(e) => setMultiTpLevels((prev) => prev.map((l, j) => j === idx ? { ...l, closePercent: parseFloat(e.target.value) || 0 } : l))}
                          placeholder="Close%"
                          style={{ ...inputBase, flex: 1, fontSize: 10 }}
                          onMouseDown={stopProp}
                        />
                      </div>
                    ))}
                    <button
                      onClick={() => setMultiTpLevels((p) => [...p, { tpPercent: 2, closePercent: 50 }])}
                      style={{
                        ...monoSm, color: "#1e6fef", background: "transparent",
                        border: "none", cursor: "pointer", padding: "2px 0",
                      }}
                      onMouseDown={stopProp}
                    >
                      + Add level
                    </button>
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </div>

      {/* ── 5. Stop Loss ──────────────────────────────── */}
      <div style={{ borderBottom: "1px solid rgba(255,255,255,0.05)", paddingBottom: 8, marginBottom: 8 }}>
        <SectionHeader
          title="Stop Loss"
          expanded={sections.sl}
          onToggle={() => toggle("sl")}
          badge={
            <span style={{
              fontSize: 9, padding: "0 4px", borderRadius: 3,
              background: cfg.stop_loss.enabled ? "rgba(255,71,87,0.15)" : "rgba(255,255,255,0.07)",
              color: cfg.stop_loss.enabled ? "#ff4757" : "rgba(255,255,255,0.3)",
            }}>
              {cfg.stop_loss.enabled ? "ON" : "OFF"}
            </span>
          }
        />
        {sections.sl && (
          <div className="flex flex-col gap-1.5 mt-1">
            <Toggle checked={cfg.stop_loss.enabled} onChange={(v) => setSl("enabled", v)} label="Enable SL" />

            {cfg.stop_loss.enabled && (
              <>
                <Seg
                  options={[
                    { v: "avg_entry", label: "Avg Entry" },
                    { v: "extreme_order", label: "Extreme" },
                  ] as const}
                  value={cfg.stop_loss.mode}
                  onChange={(v) => setSl("mode", v)}
                />

                {/* Contextual hint */}
                <div style={{
                  fontSize: 9, fontFamily: "monospace", opacity: 0.35,
                  padding: "3px 6px", borderRadius: 3,
                  background: "rgba(255,71,87,0.05)",
                  border: "1px solid rgba(255,71,87,0.1)",
                  lineHeight: 1.5,
                }}>
                  {cfg.stop_loss.mode === "extreme_order"
                    ? "SL calculated from the last filled DCA order."
                    : "SL recalculated from avg position entry price."}
                </div>

                <div className="grid grid-cols-2 gap-1.5">
                  <NumInput
                    value={cfg.stop_loss.percent}
                    onChange={(v) => setSl("percent", v)}
                    placeholder="SL %"
                    step={0.1}
                  />
                  <NumInput
                    value={cfg.stop_loss.close_percent}
                    onChange={(v) => setSl("close_percent", v)}
                    placeholder="Close %"
                    min={1}
                  />
                </div>
              </>
            )}
          </div>
        )}
      </div>

      {/* ── 6. Advanced: Reset TP ─────────────────────── */}
      <div style={{ borderBottom: "1px solid rgba(255,255,255,0.05)", paddingBottom: 8, marginBottom: 8 }}>
        <SectionHeader
          title="Advanced: Reset TP"
          expanded={sections.resetTp}
          onToggle={() => toggle("resetTp")}
          badge={
            cfg.reset_tp.enabled ? (
              <span style={{
                fontSize: 9, padding: "0 4px", borderRadius: 3,
                background: "rgba(255,170,0,0.15)", color: "#ffaa00",
              }}>
                ON
              </span>
            ) : undefined
          }
        />

        {!sections.resetTp && (
          <p style={{ ...monoSm, opacity: 0.3, lineHeight: 1.4, marginTop: 2 }}>
            Partial close after DCA fill, tail rebuild support.
          </p>
        )}

        {sections.resetTp && (
          <div className="flex flex-col gap-1.5 mt-1">
            <Toggle
              checked={cfg.reset_tp.enabled}
              onChange={(v) => setRtp("enabled", v)}
              label="Enable Reset TP"
            />

            {cfg.reset_tp.enabled && (
              <>
                {/* Warning */}
                <div style={{
                  fontSize: 9, fontFamily: "monospace", opacity: 0.5,
                  padding: "3px 6px", borderRadius: 3,
                  background: "rgba(255,170,0,0.06)",
                  border: "1px solid rgba(255,170,0,0.2)",
                  lineHeight: 1.5, display: "flex", gap: 4, alignItems: "flex-start",
                }}>
                  <AlertTriangle size={10} style={{ flexShrink: 0, marginTop: 1, color: "#ffaa00" }} />
                  Only one Reset TP active at a time. Tail rebuild may recreate pending DCA orders.
                </div>

                {/* Trigger levels checkboxes */}
                <div>
                  <span style={labelStyle}>Trigger after levels</span>
                  <div className="flex gap-1 flex-wrap">
                    {Array.from({ length: cfg.dca.orders_count }, (_, i) => i + 1).map((lvl) => {
                      const active = cfg.reset_tp.trigger_levels.includes(lvl)
                      return (
                        <button
                          key={lvl}
                          onClick={() => toggleTriggerLevel(lvl)}
                          style={{
                            width: 22, height: 22, fontSize: 10, fontFamily: "monospace",
                            borderRadius: 3, cursor: "pointer",
                            background: active ? "rgba(255,170,0,0.2)" : "rgba(255,255,255,0.04)",
                            color: active ? "#ffaa00" : "rgba(255,255,255,0.35)",
                            border: `1px solid ${active ? "rgba(255,170,0,0.4)" : "rgba(255,255,255,0.08)"}`,
                            fontWeight: active ? 700 : 400,
                          }}
                          onMouseDown={stopProp}
                        >
                          {lvl}
                        </button>
                      )
                    })}
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-1.5">
                  <NumInput
                    value={cfg.reset_tp.reset_tp_percent}
                    onChange={(v) => setRtp("reset_tp_percent", v)}
                    placeholder="Reset TP %"
                    step={0.1}
                  />
                  <NumInput
                    value={cfg.reset_tp.reset_close_percent}
                    onChange={(v) => setRtp("reset_close_percent", v)}
                    placeholder="Close on Reset %"
                    step={1}
                  />
                </div>

                <Toggle
                  checked={cfg.reset_tp.rebuild_tail}
                  onChange={(v) => setRtp("rebuild_tail", v)}
                  label="Rebuild tail after reset"
                />

                {/* Per-level settings */}
                <Toggle
                  checked={cfg.reset_tp.per_level_settings_enabled}
                  onChange={(v) => setRtp("per_level_settings_enabled", v)}
                  label="Per-level reset settings"
                />

                {cfg.reset_tp.per_level_settings_enabled && (
                  <div
                    style={{
                      background: "rgba(255,255,255,0.02)",
                      border: "1px solid rgba(255,255,255,0.06)",
                      borderRadius: 4, padding: "4px 6px",
                    }}
                  >
                    <div className="flex gap-1 mb-1">
                      <span style={{ ...monoSm, opacity: 0.3, width: 20 }}>#</span>
                      <span style={{ ...monoSm, opacity: 0.3, flex: 1 }}>Reset TP%</span>
                      <span style={{ ...monoSm, opacity: 0.3, flex: 1 }}>Close%</span>
                    </div>
                    {perLevelSettings
                      .filter((s) => cfg.reset_tp.trigger_levels.includes(s.level))
                      .map((s) => (
                        <div key={s.level} className="flex gap-1 items-center mb-1">
                          <span style={{ ...monoSm, opacity: 0.4, width: 20 }}>{s.level}</span>
                          <input
                            type="number"
                            value={s.resetTpPercent}
                            onChange={(e) => setPerLevelSettings((prev) => prev.map((l) => l.level === s.level ? { ...l, resetTpPercent: parseFloat(e.target.value) || 0 } : l))}
                            placeholder="TP%"
                            style={{ ...inputBase, flex: 1, fontSize: 10 }}
                            onMouseDown={stopProp}
                          />
                          <input
                            type="number"
                            value={s.closePercent}
                            onChange={(e) => setPerLevelSettings((prev) => prev.map((l) => l.level === s.level ? { ...l, closePercent: parseFloat(e.target.value) || 0 } : l))}
                            placeholder="Close%"
                            style={{ ...inputBase, flex: 1, fontSize: 10 }}
                            onMouseDown={stopProp}
                          />
                        </div>
                      ))}
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </div>

      {/* ── 7. Preview ────────────────────────────────── */}
      <div style={{ borderBottom: "1px solid rgba(255,255,255,0.05)", paddingBottom: 8, marginBottom: 8 }}>
        <div style={{ marginBottom: 5 }}>
          <span style={{ ...monoSm, opacity: 0.5, textTransform: "uppercase", letterSpacing: "0.06em" }}>Preview</span>
        </div>
        <div
          style={{
            background: "rgba(255,255,255,0.02)",
            border: "1px solid rgba(255,255,255,0.06)",
            borderRadius: 4, padding: "6px 8px",
          }}
        >
          <StatRow label="Orders" value={preview.orders} />
          <StatRow label="Max position" value={`${preview.maxPositionQty} ${ticker} / $${preview.maxPositionUsdt}`} />
          <StatRow label="Max margin" value={`$${preview.maxMarginUsdt}`} />
          <StatRow label="Est. avg entry" value={`$${preview.avgEntry}`} highlight="blue" />
          {cfg.take_profit.enabled && preview.tpPrice && (
            <StatRow label={`Main TP (+${cfg.take_profit.percent}%)`} value={`$${preview.tpPrice}`} highlight="green" />
          )}
          {cfg.stop_loss.enabled && preview.slPrice && (
            <StatRow label={`SL (-${cfg.stop_loss.percent}%)`} value={`$${preview.slPrice}`} highlight="red" />
          )}
          <StatRow
            label="Reset TP"
            value={cfg.reset_tp.enabled
              ? `ON after levels ${cfg.reset_tp.trigger_levels.join(",")}`
              : "OFF"}
          />
        </div>
      </div>

      {/* ── 8. Validation errors ──────────────────────── */}
      {validationResult && validationResult.errors.length > 0 && (
        <div
          style={{
            padding: "5px 8px", borderRadius: 4, marginBottom: 8,
            background: "rgba(255,71,87,0.08)",
            border: "1px solid rgba(255,71,87,0.3)",
          }}
        >
          {validationResult.errors.map((e) => (
            <div key={e} className="flex items-center gap-1" style={{ ...monoSm, color: "#ff4757", marginBottom: 2 }}>
              <AlertTriangle size={9} /> {e}
            </div>
          ))}
        </div>
      )}

      {/* ── 9. Confirm modal ──────────────────────────── */}
      {showConfirm && validationResult && (
        <div
          style={{
            padding: "8px 10px", borderRadius: 4, marginBottom: 8,
            background: "rgba(0,0,0,0.3)",
            border: "1px solid rgba(255,255,255,0.12)",
          }}
        >
          <div style={{ ...monoSm, color: "rgba(255,255,255,0.6)", marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.06em" }}>
            Confirm Start DCA
          </div>
          <StatRow label="Symbol" value={`${cfg.symbol} ${cfg.position_side}`} />
          <StatRow label="Max exposure" value={`$${cfg.dca.total_budget}`} />
          <StatRow label="TP" value={cfg.take_profit.enabled ? `${cfg.take_profit.percent}%` : "OFF"} />
          <StatRow label="SL" value={cfg.stop_loss.enabled ? `${cfg.stop_loss.percent}%` : "OFF"} />
          <StatRow label="Reset TP" value={cfg.reset_tp.enabled ? "ON" : "OFF"} />
          <div className="flex gap-1.5 mt-3">
            <button
              onClick={() => setShowConfirm(false)}
              style={{
                flex: 1, fontSize: 11, fontFamily: "monospace", padding: "6px 0",
                background: "transparent", color: "rgba(255,255,255,0.4)",
                border: "1px solid rgba(255,255,255,0.1)", borderRadius: 4, cursor: "pointer",
              }}
              onMouseDown={stopProp}
            >
              Cancel
            </button>
            <button
              onClick={() => {
                console.log("[DCA Config]", JSON.stringify(validationResult.config, null, 2))
                setShowConfirm(false)
                setValidationResult(null)
              }}
              style={{
                flex: 2, fontSize: 11, fontFamily: "monospace", fontWeight: 700, padding: "6px 0",
                background: cfg.position_side === "LONG" ? "rgba(0,229,160,0.15)" : "rgba(255,71,87,0.15)",
                color: cfg.position_side === "LONG" ? "#00e5a0" : "#ff4757",
                border: `1px solid ${cfg.position_side === "LONG" ? "rgba(0,229,160,0.4)" : "rgba(255,71,87,0.4)"}`,
                borderRadius: 4, cursor: "pointer",
                letterSpacing: "0.03em",
              }}
              onMouseDown={stopProp}
            >
              Confirm & Log Config
            </button>
          </div>
        </div>
      )}

      {/* ── 10. Action buttons ────────────────────────── */}
      <div className="flex gap-1.5 mt-auto">
        <button
          onClick={() => {
            const errors = validateDca(cfg)
            setValidationResult({ errors, config: cfg })
          }}
          style={{
            flex: 1, fontSize: 10, fontFamily: "monospace", padding: "6px 0",
            background: "rgba(255,255,255,0.04)",
            color: "rgba(255,255,255,0.5)",
            border: "1px solid rgba(255,255,255,0.1)", borderRadius: 4, cursor: "pointer",
            display: "flex", alignItems: "center", justifyContent: "center", gap: 4,
          }}
          onMouseDown={stopProp}
        >
          <BookOpen size={10} /> Preview
        </button>
        <button
          onClick={() => {
            console.log("[DCA Preset saved]", cfg)
          }}
          style={{
            flex: 1, fontSize: 10, fontFamily: "monospace", padding: "6px 0",
            background: "rgba(255,255,255,0.04)",
            color: "rgba(255,255,255,0.5)",
            border: "1px solid rgba(255,255,255,0.1)", borderRadius: 4, cursor: "pointer",
            display: "flex", alignItems: "center", justifyContent: "center", gap: 4,
          }}
          onMouseDown={stopProp}
        >
          <Save size={10} /> Save
        </button>
        <button
          onClick={handleStartDca}
          style={{
            flex: 2, fontSize: 11, fontFamily: "monospace", fontWeight: 700, padding: "6px 0",
            background: cfg.position_side === "LONG" ? "rgba(0,229,160,0.15)" : "rgba(255,71,87,0.15)",
            color: cfg.position_side === "LONG" ? "#00e5a0" : "#ff4757",
            border: `1px solid ${cfg.position_side === "LONG" ? "rgba(0,229,160,0.4)" : "rgba(255,71,87,0.4)"}`,
            borderRadius: 4, cursor: "pointer",
            letterSpacing: "0.03em",
            display: "flex", alignItems: "center", justifyContent: "center", gap: 4,
          }}
          onMouseDown={stopProp}
        >
          <Play size={11} /> Start DCA
        </button>
      </div>
      </div>
    </div>
  )
}
