import type { GridConfig, GridLevel } from "@/types/terminal"

// Calculate price levels based on placement mode
function calcPrices(cfg: GridConfig): number[] {
  const { ordersCount, entryPrice, placementMode, firstOffsetPercent, stepPercent, direction, topPrice, bottomPrice } = cfg
  const count = Math.max(1, Math.round(ordersCount))
  const prices: number[] = []

  if (placementMode === "price_range") {
    const lo = Math.min(topPrice, bottomPrice)
    const hi = Math.max(topPrice, bottomPrice)
    if (hi <= lo || count < 2) return [lo]
    const step = (hi - lo) / (count - 1)
    for (let i = 0; i < count; i++) prices.push(lo + step * i)
    return direction === "below_price" ? prices.reverse() : prices
  }

  if (placementMode === "manual") {
    // Manual mode: return evenly spaced as fallback
    const step = entryPrice * (stepPercent / 100)
    for (let i = 0; i < count; i++) {
      if (direction === "below_price") {
        prices.push(entryPrice - step * i)
      } else {
        prices.push(entryPrice + step * i)
      }
    }
    return prices
  }

  // step_percent mode (default)
  // First order is at offset from current price, then step between each subsequent
  for (let i = 0; i < count; i++) {
    let offsetPct: number
    if (i === 0) {
      offsetPct = firstOffsetPercent
    } else {
      offsetPct = firstOffsetPercent + i * stepPercent
    }
    if (direction === "below_price") {
      prices.push(entryPrice * (1 - offsetPct / 100))
    } else {
      prices.push(entryPrice * (1 + offsetPct / 100))
    }
  }
  return prices
}

// Calculate quantities based on multiplier or fixed split
function calcQtys(count: number, totalBudget: number, leverage: number, prices: number[], multiplierEnabled: boolean, multiplier: number): number[] {
  const totalExposure = totalBudget * leverage
  const qtys: number[] = []

  if (!multiplierEnabled || multiplier <= 1) {
    // Equal distribution by notional
    for (let i = 0; i < count; i++) {
      const notional = totalExposure / count
      qtys.push(prices[i] > 0 ? notional / prices[i] : 0)
    }
    return qtys
  }

  // Multiplier: notional_i = base * multiplier^i
  // sum = base * (1 + m + m^2 + ... + m^(n-1)) = base * (m^n - 1)/(m - 1)
  let geomSum = 0
  for (let i = 0; i < count; i++) geomSum += Math.pow(multiplier, i)
  const baseNotional = totalExposure / geomSum

  for (let i = 0; i < count; i++) {
    const notional = baseNotional * Math.pow(multiplier, i)
    qtys.push(prices[i] > 0 ? notional / prices[i] : 0)
  }
  return qtys
}

export function generateLevels(cfg: GridConfig): GridLevel[] {
  const { ordersCount, totalQuote, leverage, defaultResetTpPercent, defaultResetTpClosePercent, multiplierEnabled, multiplier } = cfg
  const count = Math.max(1, Math.round(ordersCount))
  const prices = calcPrices(cfg)

  if (prices.length === 0) return []

  const qtys = calcQtys(count, totalQuote, leverage, prices, multiplierEnabled, multiplier)

  let cumExposure = 0
  return prices.map((price, i) => {
    const qty = parseFloat((qtys[i] ?? 0).toFixed(6))
    const notional = parseFloat((qty * price).toFixed(2))
    cumExposure += notional
    return {
      index: i + 1,
      price: parseFloat(price.toFixed(2)),
      qty,
      notional,
      cumExposure: parseFloat(cumExposure.toFixed(2)),
      useResetTp: false,
      resetTpPercent: defaultResetTpPercent,
      resetTpClosePercent: defaultResetTpClosePercent,
    }
  })
}

export interface GridDerivedStats {
  totalLevels: number
  totalQty: number
  totalGridAmount: number
  resetEnabledCount: number
  baseOrderSize: number
  firstOrderSize: number
  lastOrderSize: number
  maxPositionSize: number
  avgEntryPrice: number
  tpPrice: number | null
  slPrice: number | null
  maxMarginRequired: number
  freeMarginAfter: number
}

export function calcDerivedStats(cfg: GridConfig, availableBalance = 0): GridDerivedStats {
  const { levels, totalQuote, leverage, entryPrice, tpEnabled, slEnabled, side } = cfg
  const totalLevels = levels.length
  const totalQty = levels.reduce((s, l) => s + l.qty, 0)
  const totalGridAmount = levels.reduce((s, l) => s + l.notional, 0)
  const resetEnabledCount = levels.filter((l) => l.useResetTp).length

  // Base order size (first level)
  const firstOrderSize = levels.length > 0 ? levels[0].notional : 0
  const lastOrderSize = levels.length > 0 ? levels[levels.length - 1].notional : 0
  const maxPositionSize = totalGridAmount

  // Avg entry = sum(price*qty) / sum(qty)
  const weightedSum = levels.reduce((s, l) => s + l.price * l.qty, 0)
  const avgEntryPrice = totalQty > 0 ? weightedSum / totalQty : entryPrice

  const baseOrderSize = totalLevels > 0
    ? (totalQuote * leverage) / totalLevels
    : 0

  // TP/SL prices
  const tpPrice = tpEnabled
    ? (side === "long" ? avgEntryPrice * (1 + cfg.tpPercent / 100) : avgEntryPrice * (1 - cfg.tpPercent / 100))
    : null

  const slPrice = slEnabled
    ? (side === "long" ? avgEntryPrice * (1 - cfg.slPercent / 100) : avgEntryPrice * (1 + cfg.slPercent / 100))
    : null

  const maxMarginRequired = totalQuote
  const freeMarginAfter = Math.max(0, availableBalance - maxMarginRequired)

  return {
    totalLevels,
    totalQty,
    totalGridAmount,
    resetEnabledCount,
    baseOrderSize,
    firstOrderSize,
    lastOrderSize,
    maxPositionSize,
    avgEntryPrice,
    tpPrice,
    slPrice,
    maxMarginRequired,
    freeMarginAfter,
  }
}

export function exportGridConfig(cfg: GridConfig): string {
  const out = {
    strategy: "grid",
    symbol: cfg.symbol.replace("/", ""),
    position_side: cfg.side.toUpperCase(),
    leverage: cfg.leverage,
    grid: {
      orders_count: cfg.ordersCount,
      total_budget: cfg.totalQuote,
      placement_mode: cfg.placementMode,
      first_offset_percent: cfg.firstOffsetPercent,
      step_percent: cfg.stepPercent,
      last_offset_percent: cfg.lastOffsetPercent,
      direction: cfg.direction,
      qty_mode: cfg.multiplierEnabled ? "multiplier" : "fixed",
      qty_multiplier: cfg.multiplier,
    },
  }
  return JSON.stringify(out, null, 2)
}
