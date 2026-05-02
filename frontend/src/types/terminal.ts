export type Theme = "transparent" | "glass-graphite"

export type TransparentBgPreset = "slate" | "grey" | "lightgrey" | "steelblue"

export type WidgetType =
  | "chart"
  | "orderbook"
  | "trades"
  | "portfolio"
  | "screener"
  | "pnl"
  | "alerts"
  | "order-console"
  | "news"

export interface WidgetRect {
  x: number
  y: number
  width: number
  height: number
}

export interface Widget {
  id: string
  type: WidgetType
  title: string
  rect: WidgetRect
  prevRect?: WidgetRect
  zIndex: number
  symbol?: string
  chartType?: "candlestick" | "line"
  showOrderBook?: boolean
  showOrderForm?: boolean
  marketType?: "spot" | "futures"
  futuresSide?: "long" | "short"
  accountId?: string
  exchangeId?: string
}

export interface Tab {
  id: string
  label: string
  widgets: Widget[]
  nextZIndex: number
}

export type GlassGraphiteBg = "graphite" | "blue-mist" | "pure-black" | "dark-grey"

export interface TerminalState {
  tabs: Tab[]
  activeTabId: string
  theme: Theme
  transparentBg?: TransparentBgPreset
  ggBg?: GlassGraphiteBg
  customBgColor?: string
}

export type ResizeHandle =
  | "n" | "s" | "e" | "w"
  | "ne" | "nw" | "se" | "sw"

export interface DragState {
  widgetId: string
  startX: number
  startY: number
  startRect: WidgetRect
  type: "move" | "resize"
  handle?: ResizeHandle
}

export interface Candle {
  time: number
  open: number
  high: number
  low: number
  close: number
  volume: number
}

export interface OrderBookEntry {
  price: number
  size: number
  total: number
}

export interface Trade {
  id: string
  price: number
  size: number
  side: "buy" | "sell"
  time: string
}

export interface Position {
  symbol: string
  side: "long" | "short"
  size: number
  entryPrice: number
  markPrice: number
  pnl: number
  pnlPct: number
  leverage: number
}

// ---- Order types (canonical home — re-exported from TerminalContext for compat) ----

export type OrderSource = "manual" | "grid" | "dca" | "bot" | "webhook"

export interface ChartDraftOrder {
  side: "buy" | "sell"
  price: number
  qty: number
  orderType: "limit" | "market"
}

export interface ChartPlacedOrder {
  id: string
  side: "buy" | "sell"
  price: number
  qty: number
  orderType: "limit" | "market"
  isDraft?: boolean
  symbol?: string
  accountId?: string
  exchangeId?: string
  marketType?: "spot" | "futures"
  leverage?: number
  margin?: number
  time?: string
  filledAt?: string    // HH:MM:SS DD.MM when order was filled
  filledPct?: number   // 0–100 fill percentage
  status?: "pending" | "filled" | "cancelled"
  source?: OrderSource
  gridIndex?: number
  gridConsoleId?: string
  botName?: string
  webhookName?: string
}

export type PositionStatus = "active" | "pending" | "closed"

// Live position — created/updated by the position manager in TerminalContext
export interface LivePosition {
  // Identity (same key as PositionKey)
  accountId: string
  exchangeId: string
  marketType: "spot" | "futures"
  symbol: string

  side: "long" | "short"
  size: number          // base asset qty — virtual (pending orders) size
  realSize: number      // actual filled size on exchange (0 = virtual position)
  avgEntry: number      // volume-weighted average entry price
  leverage: number
  marginMode: "cross" | "isolated"
  markPrice: number     // latest mark/last price (updated externally)

  // TP/SL percent for display
  tpPct?: number
  slPct?: number
  tpPrice?: number
  slPrice?: number

  // Computed on the fly, stored for quick access
  unrealizedPnl: number
  unrealizedPnlPct: number
  notional: number      // size * avgEntry

  openedAt: string      // HH:MM:SS when position was first opened
  openedDate: string    // DD.MM date portion

  // Short human-readable ID (e.g. "5673700")
  shortId: string

  // Order storage — all placed orders belonging to this position
  orders: ChartPlacedOrder[]

  status: PositionStatus   // pending = orders placed but no fill yet; active = at least one fill
  realizedPnl: number
  sourceConsoleId?: string // grid/DCA console that opened this position
}

export interface Alert {
  id: string
  symbol: string
  condition: "above" | "below"
  price: number
  active: boolean
  triggered: boolean
  createdAt: string
}

export interface NewsItem {
  id: string
  headline: string
  source: string
  sentiment: "positive" | "negative" | "neutral"
  time: string
  symbols: string[]
}

export interface ScreenerRow {
  symbol: string
  price: number
  change: number
  changePct: number
  volume: number
  marketCap: number
  high24h: number
  low24h: number
}

// ---- DCA Order Types ----

export type DcaEntryType = "market" | "limit"
export type DcaPlacementMode = "step_percent" | "price_range"
export type DcaQtyMode = "fixed" | "multiplier"
export type DcaTpMode = "avg_entry"
export type DcaSlMode = "avg_entry" | "extreme_order"
export type DcaRebuildMode = "from_avg_entry"

export interface DcaMultiTpLevel {
  tpPercent: number
  closePercent: number
}

export interface DcaPerLevelResetSetting {
  level: number
  resetTpPercent: number
  closePercent: number
}

export interface DcaConfig {
  strategy: "dca"
  account_id: string
  exchange: string
  symbol: string
  position_side: "LONG" | "SHORT"
  leverage: number
  entry: {
    type: DcaEntryType
    price: number
  }
  dca: {
    orders_count: number
    total_budget: number
    placement_mode: DcaPlacementMode
    first_offset_percent: number
    step_percent: number
    price_range_from?: number
    price_range_to?: number
    qty_mode: DcaQtyMode
    qty_multiplier: number
  }
  take_profit: {
    enabled: boolean
    mode: DcaTpMode
    percent: number
    close_percent: number
    multi_tp_enabled: boolean
    levels: DcaMultiTpLevel[]
  }
  stop_loss: {
    enabled: boolean
    mode: DcaSlMode
    percent: number
    close_percent: number
  }
  reset_tp: {
    enabled: boolean
    trigger_levels: number[]
    reset_tp_percent: number
    reset_close_percent: number
    rebuild_tail: boolean
    rebuild_mode: DcaRebuildMode
    per_level_settings_enabled: boolean
    per_level_settings: DcaPerLevelResetSetting[]
  }
}

export const DEFAULT_DCA_CONFIG: DcaConfig = {
  strategy: "dca",
  account_id: "main",
  exchange: "binance",
  symbol: "BTC/USDT",
  position_side: "LONG",
  leverage: 5,
  entry: { type: "limit", price: 67500 },
  dca: {
    orders_count: 5,
    total_budget: 100,
    placement_mode: "step_percent",
    first_offset_percent: 0.5,
    step_percent: 1.0,
    qty_mode: "multiplier",
    qty_multiplier: 1.25,
  },
  take_profit: {
    enabled: true,
    mode: "avg_entry",
    percent: 1.2,
    close_percent: 100,
    multi_tp_enabled: false,
    levels: [],
  },
  stop_loss: {
    enabled: true,
    mode: "extreme_order",
    percent: 2.5,
    close_percent: 100,
  },
  reset_tp: {
    enabled: false,
    trigger_levels: [3, 4, 5],
    reset_tp_percent: 0.6,
    reset_close_percent: 35,
    rebuild_tail: true,
    rebuild_mode: "from_avg_entry",
    per_level_settings_enabled: false,
    per_level_settings: [],
  },
}

// ---- Grid Order Types ----

export type GridMode = "arithmetic" | "geometric" | "custom"
export type QtyMode = "fixed" | "multiplier" | "custom"
export type TpUpdateMode = "fixed" | "reprice"
export type GridPlacementMode = "step_percent" | "price_range" | "manual"
export type GridDirection = "below_price" | "above_price"
export type GridType = "simple" | "custom"
export type GridEntryType = "market" | "limit"
export type GridTpMode = "avg_entry" | "breakeven_offset"
export type GridSlMode = "avg_entry" | "extreme_order"

export interface GridMultiTpLevel {
  tpPercent: number
  closePercent: number
}

export interface GridPerLevelTp {
  afterLevel: number   // after how many grid orders filled
  tpCount: number
  levels: GridMultiTpLevel[]
  resetTpEnabled: boolean  // if true, first TP level is Reset TP, rest are Main TP
}

export interface GridResetTpLevel {
  level: number
  resetTpPercent: number
  resetClosePercent: number
}

// ---- Grid Shared TP/SL (used when multiPosition mode is OFF) ----
// When Pro mode is active and multiPositionMode is enabled, each slot has its own
// full GridConfig including TP/SL (current behavior). When multiPositionMode is
// disabled (default), TP/SL is shared across all grids on the same side.

export interface GridSharedTpSl {
  tpEnabled: boolean
  tpMode: GridTpMode
  tpPercent: number
  tpClosePercent: number
  multiTpEnabled: boolean
  multiTpCount: number
  multiTpLevels: GridMultiTpLevel[]
  tpRepositionEnabled: boolean
  perLevelTpEnabled: boolean
  perLevelTpGroups: GridPerLevelTp[]
  slEnabled: boolean
  slMode: GridSlMode
  slPercent: number
  slClosePercent: number
  resetTpEnabled: boolean
  resetTpTriggerLevels: number[]
  defaultResetTpPercent: number
  defaultResetTpClosePercent: number
  resetTpRebuildTail: boolean
  resetTpPerLevelEnabled: boolean
  resetTpPerLevelSettings: GridResetTpLevel[]
}

export interface GridLevel {
  index: number
  price: number
  qty: number
  notional: number
  cumExposure: number
  useResetTp: boolean
  resetTpPercent: number
  resetTpClosePercent: number
}

export interface GridConfig {
  // General
  enabled: boolean
  symbol: string
  side: "long" | "short"
  ordersCount: number
  entryPrice: number
  topPrice: number
  bottomPrice: number
  totalQuote: number
  budgetMode: "quote" | "base"
  leverage: number
  gridType: GridType

  // Entry
  entryType: GridEntryType

  // Placement
  placementMode: GridPlacementMode
  firstOffsetPercent: number
  stepPercent: number
  lastOffsetPercent: number
  direction: GridDirection

  // Qty / multiplier
  qtyMode: QtyMode
  multiplier: number
  multiplierEnabled: boolean

  // Density
  density: number

  // Level logic (for level table)
  gridMode: GridMode

  // TP
  tpEnabled: boolean
  tpMode: GridTpMode
  tpPercent: number
  tpClosePercent: number
  multiTpEnabled: boolean
  multiTpCount: number
  multiTpLevels: GridMultiTpLevel[]
  tpRepositionEnabled: boolean
  perLevelTpEnabled: boolean
  perLevelTpGroups: GridPerLevelTp[]

  // SL
  slEnabled: boolean
  slMode: GridSlMode
  slPercent: number
  slClosePercent: number

  // Trail (grid trailing)
  trailEnabled: boolean
  trailTriggerPercent: number
  trailLimitPriceEnabled: boolean
  trailLimitPrice: number

  // Auto restart
  autoEnabled: boolean      // master toggle — auto-cycle active
  stopOnSl: boolean         // when ON: stop cycle after SL; when OFF (default): restart after SL
  stopNew: boolean          // when ON: stop after next trigger, rebuild TP to breakeven

  // TP/SL legacy (kept for compatibility)
  tpUpdateMode: TpUpdateMode
  trailingEnabled: boolean
  trailingStepPercent: number

  // Reset TP (pro)
  resetTpEnabled: boolean
  resetTpTriggerLevels: number[]
  defaultResetTpPercent: number
  defaultResetTpClosePercent: number
  resetTpRebuildTail: boolean
  resetTpPerLevelEnabled: boolean
  resetTpPerLevelSettings: GridResetTpLevel[]

  // Generated levels
  levels: GridLevel[]
}

export const DEFAULT_GRID_CONFIG: GridConfig = {
  enabled: false,
  symbol: "BTC/USDT",
  side: "long",
  ordersCount: 8,
  entryPrice: 67432,
  topPrice: 70000,
  bottomPrice: 65000,
  totalQuote: 1000,
  budgetMode: "quote",
  leverage: 5,
  gridType: "simple",

  entryType: "market",

  placementMode: "step_percent",
  firstOffsetPercent: 0.5,
  stepPercent: 1,
  lastOffsetPercent: 5,
  direction: "below_price",

  qtyMode: "multiplier",
  multiplier: 1.25,
  multiplierEnabled: true,
  density: 1,

  gridMode: "arithmetic",

  tpEnabled: true,
  tpMode: "avg_entry",
  tpPercent: 1.2,
  tpClosePercent: 100,
  multiTpEnabled: true,
  multiTpCount: 2,
  multiTpLevels: [
    { tpPercent: 0.8, closePercent: 50 },
    { tpPercent: 1.5, closePercent: 50 },
  ],
  tpRepositionEnabled: false,
  perLevelTpEnabled: false,
  perLevelTpGroups: [
    { afterLevel: 1, tpCount: 1, levels: [{ tpPercent: 1.2, closePercent: 100 }], resetTpEnabled: false },
  ],

  slEnabled: true,
  slMode: "extreme_order",
  slPercent: 2.5,
  slClosePercent: 100,

  trailEnabled: false,
  trailTriggerPercent: 1,
  trailLimitPriceEnabled: false,
  trailLimitPrice: 0,

  autoEnabled: false,
  stopOnSl: false,
  stopNew: false,

  tpUpdateMode: "fixed",
  trailingEnabled: false,
  trailingStepPercent: 0.5,

  resetTpEnabled: false,
  resetTpTriggerLevels: [3, 4, 5],
  defaultResetTpPercent: 0.6,
  defaultResetTpClosePercent: 35,
  resetTpRebuildTail: true,
  resetTpPerLevelEnabled: false,
  resetTpPerLevelSettings: [],

  levels: [],
}

export const DEFAULT_GRID_SHARED_TP_SL: GridSharedTpSl = {
  tpEnabled: true,
  tpMode: "avg_entry",
  tpPercent: 1.2,
  tpClosePercent: 100,
  multiTpEnabled: true,
  multiTpCount: 2,
  multiTpLevels: [
    { tpPercent: 0.8, closePercent: 50 },
    { tpPercent: 1.5, closePercent: 50 },
  ],
  tpRepositionEnabled: false,
  perLevelTpEnabled: false,
  perLevelTpGroups: [
    { afterLevel: 1, tpCount: 1, levels: [{ tpPercent: 1.2, closePercent: 100 }], resetTpEnabled: false },
  ],
  slEnabled: true,
  slMode: "extreme_order",
  slPercent: 2.5,
  slClosePercent: 100,
  resetTpEnabled: false,
  resetTpTriggerLevels: [3, 4, 5],
  defaultResetTpPercent: 0.6,
  defaultResetTpClosePercent: 35,
  resetTpRebuildTail: true,
  resetTpPerLevelEnabled: false,
  resetTpPerLevelSettings: [],
}

export const WIDGET_LABELS: Record<WidgetType, string> = {
  chart: "Price Chart",
  orderbook: "Order Book",
  trades: "Trades Feed",
  portfolio: "Positions",
  screener: "Asset Screener",
  pnl: "P&L Statistics",
  alerts: "Alerts",
  "order-console": "Order Console",
  news: "News",
}

export const WIDGET_MIN_SIZE: Record<WidgetType, { width: number; height: number }> = {
  chart: { width: 280, height: 200 },
  orderbook: { width: 200, height: 200 },
  trades: { width: 200, height: 150 },
  portfolio: { width: 300, height: 150 },
  screener: { width: 340, height: 200 },
  pnl: { width: 240, height: 150 },
  alerts: { width: 220, height: 150 },
  "order-console": { width: 240, height: 250 },
  news: { width: 260, height: 150 },
}
