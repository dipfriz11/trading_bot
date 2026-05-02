import type { Candle, OrderBookEntry, Trade, Position, Alert, NewsItem, ScreenerRow } from "@/types/terminal"

export const SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT", "ADA/USDT", "AVAX/USDT", "DOGE/USDT"]

export interface AccountData {
  id: string
  label: string
  // balances per exchange per marketType
  balances: Record<string, { spot: { walletBalance: number; inOrders: number }; futures: { walletBalance: number; inOrders: number } }>
}

export const ACCOUNTS: AccountData[] = [
  {
    id: "main",
    label: "Main Account",
    balances: {
      binance: { spot: { walletBalance: 10000, inOrders: 0 }, futures: { walletBalance: 10000, inOrders: 0 } },
      okx:     { spot: { walletBalance: 4500,  inOrders: 0 }, futures: { walletBalance: 4500,  inOrders: 0 } },
      bybit:   { spot: { walletBalance: 2000,  inOrders: 0 }, futures: { walletBalance: 2000,  inOrders: 0 } },
      kraken:  { spot: { walletBalance: 3000,  inOrders: 0 }, futures: { walletBalance: 3000,  inOrders: 0 } },
      kucoin:  { spot: { walletBalance: 1500,  inOrders: 0 }, futures: { walletBalance: 1500,  inOrders: 0 } },
      gate:    { spot: { walletBalance: 800,   inOrders: 0 }, futures: { walletBalance: 800,   inOrders: 0 } },
      bitget:  { spot: { walletBalance: 600,   inOrders: 0 }, futures: { walletBalance: 600,   inOrders: 0 } },
    },
  },
  {
    id: "test",
    label: "Test Account",
    balances: {
      binance: { spot: { walletBalance: 2500, inOrders: 0 }, futures: { walletBalance: 2500, inOrders: 0 } },
      okx:     { spot: { walletBalance: 1000, inOrders: 0 }, futures: { walletBalance: 1000, inOrders: 0 } },
      bybit:   { spot: { walletBalance: 500,  inOrders: 0 }, futures: { walletBalance: 500,  inOrders: 0 } },
      kraken:  { spot: { walletBalance: 300,  inOrders: 0 }, futures: { walletBalance: 300,  inOrders: 0 } },
      kucoin:  { spot: { walletBalance: 200,  inOrders: 0 }, futures: { walletBalance: 200,  inOrders: 0 } },
      gate:    { spot: { walletBalance: 100,  inOrders: 0 }, futures: { walletBalance: 100,  inOrders: 0 } },
      bitget:  { spot: { walletBalance: 100,  inOrders: 0 }, futures: { walletBalance: 100,  inOrders: 0 } },
    },
  },
  {
    id: "scalp",
    label: "Scalp Account",
    balances: {
      binance: { spot: { walletBalance: 5000, inOrders: 0 }, futures: { walletBalance: 5000, inOrders: 0 } },
      okx:     { spot: { walletBalance: 2000, inOrders: 0 }, futures: { walletBalance: 2000, inOrders: 0 } },
      bybit:   { spot: { walletBalance: 1000, inOrders: 0 }, futures: { walletBalance: 1000, inOrders: 0 } },
      kraken:  { spot: { walletBalance: 500,  inOrders: 0 }, futures: { walletBalance: 500,  inOrders: 0 } },
      kucoin:  { spot: { walletBalance: 400,  inOrders: 0 }, futures: { walletBalance: 400,  inOrders: 0 } },
      gate:    { spot: { walletBalance: 300,  inOrders: 0 }, futures: { walletBalance: 300,  inOrders: 0 } },
      bitget:  { spot: { walletBalance: 200,  inOrders: 0 }, futures: { walletBalance: 200,  inOrders: 0 } },
    },
  },
]

export const EXCHANGES = [
  { id: "binance", label: "Binance" },
  { id: "okx",     label: "OKX"     },
  { id: "bybit",   label: "Bybit"   },
  { id: "kraken",  label: "Kraken"  },
  { id: "kucoin",  label: "KuCoin"  },
  { id: "gate",    label: "Gate.io" },
  { id: "bitget",  label: "Bitget"  },
]

export function getAccountBalance(
  accountId: string,
  exchangeId: string,
  marketType: "spot" | "futures",
): { walletBalance: number; inOrders: number } {
  const acc = ACCOUNTS.find((a) => a.id === accountId)
  if (!acc) return { walletBalance: 0, inOrders: 0 }
  return acc.balances[exchangeId]?.[marketType] ?? { walletBalance: 0, inOrders: 0 }
}

function randBetween(a: number, b: number) {
  return a + Math.random() * (b - a)
}

export function generateCandles(symbol: string, count = 100): Candle[] {
  const basePrices: Record<string, number> = {
    "BTC/USDT": 67500,
    "ETH/USDT": 3450,
    "SOL/USDT": 185,
    "BNB/USDT": 590,
    "XRP/USDT": 0.62,
    "ADA/USDT": 0.48,
    "AVAX/USDT": 38,
    "DOGE/USDT": 0.16,
  }
  const base = basePrices[symbol] ?? 100
  const candles: Candle[] = []
  let price = base
  const now = Date.now()

  for (let i = count; i >= 0; i--) {
    const open = price
    const change = (Math.random() - 0.48) * base * 0.015
    const close = Math.max(open + change, 0.001)
    const high = Math.max(open, close) * (1 + Math.random() * 0.008)
    const low = Math.min(open, close) * (1 - Math.random() * 0.008)
    const volume = randBetween(base * 50, base * 200)
    candles.push({
      time: now - i * 60000,
      open: parseFloat(open.toFixed(4)),
      high: parseFloat(high.toFixed(4)),
      low: parseFloat(low.toFixed(4)),
      close: parseFloat(close.toFixed(4)),
      volume: parseFloat(volume.toFixed(2)),
    })
    price = close
  }
  return candles
}

export function generateOrderBook(symbol: string): { asks: OrderBookEntry[]; bids: OrderBookEntry[] } {
  const basePrices: Record<string, number> = {
    "BTC/USDT": 67500, "ETH/USDT": 3450, "SOL/USDT": 185,
    "BNB/USDT": 590, "XRP/USDT": 0.62, "ADA/USDT": 0.48,
    "AVAX/USDT": 38, "DOGE/USDT": 0.16,
  }
  const mid = basePrices[symbol] ?? 100
  const spread = mid * 0.0002
  const asks: OrderBookEntry[] = []
  const bids: OrderBookEntry[] = []
  let askTotal = 0
  let bidTotal = 0

  for (let i = 0; i < 20; i++) {
    const askPrice = mid + spread + i * mid * 0.0001 * (1 + Math.random())
    const askSize = randBetween(0.01, 5)
    askTotal += askSize
    asks.push({ price: parseFloat(askPrice.toFixed(4)), size: parseFloat(askSize.toFixed(4)), total: parseFloat(askTotal.toFixed(4)) })

    const bidPrice = mid - spread - i * mid * 0.0001 * (1 + Math.random())
    const bidSize = randBetween(0.01, 5)
    bidTotal += bidSize
    bids.push({ price: parseFloat(bidPrice.toFixed(4)), size: parseFloat(bidSize.toFixed(4)), total: parseFloat(bidTotal.toFixed(4)) })
  }

  return { asks, bids: bids.sort((a, b) => b.price - a.price) }
}

export function generateTrades(symbol: string, count = 30): Trade[] {
  const basePrices: Record<string, number> = {
    "BTC/USDT": 67500, "ETH/USDT": 3450, "SOL/USDT": 185,
    "BNB/USDT": 590, "XRP/USDT": 0.62, "ADA/USDT": 0.48,
    "AVAX/USDT": 38, "DOGE/USDT": 0.16,
  }
  const base = basePrices[symbol] ?? 100
  const trades: Trade[] = []
  const now = Date.now()

  for (let i = 0; i < count; i++) {
    const price = base * (1 + (Math.random() - 0.5) * 0.002)
    const size = randBetween(0.001, 2)
    const side = Math.random() > 0.5 ? "buy" : "sell"
    const t = new Date(now - i * 2500)
    trades.push({
      id: `t${i}`,
      price: parseFloat(price.toFixed(4)),
      size: parseFloat(size.toFixed(4)),
      side,
      time: `${t.getHours().toString().padStart(2, "0")}:${t.getMinutes().toString().padStart(2, "0")}:${t.getSeconds().toString().padStart(2, "0")}`,
    })
  }
  return trades
}

export function generatePositions(): Position[] {
  return [
    { symbol: "BTC/USDT", side: "long", size: 0.5, entryPrice: 65200, markPrice: 67500, pnl: 1150, pnlPct: 3.53, leverage: 10 },
    { symbol: "ETH/USDT", side: "short", size: 2, entryPrice: 3600, markPrice: 3450, pnl: 300, pnlPct: 4.17, leverage: 5 },
    { symbol: "SOL/USDT", side: "long", size: 10, entryPrice: 190, markPrice: 185, pnl: -50, pnlPct: -2.63, leverage: 3 },
  ]
}

export function generateAlerts(): Alert[] {
  return [
    { id: "a1", symbol: "BTC/USDT", condition: "above", price: 70000, active: true, triggered: false, createdAt: "2024-01-15 10:30" },
    { id: "a2", symbol: "ETH/USDT", condition: "below", price: 3000, active: true, triggered: false, createdAt: "2024-01-15 11:00" },
    { id: "a3", symbol: "SOL/USDT", condition: "above", price: 200, active: false, triggered: true, createdAt: "2024-01-14 09:15" },
  ]
}

export function generateNews(): NewsItem[] {
  return [
    { id: "n1", headline: "Bitcoin breaks key resistance at $67,500 as institutional demand surges", source: "CoinDesk", sentiment: "positive", time: "2m ago", symbols: ["BTC/USDT"] },
    { id: "n2", headline: "Ethereum network upgrade scheduled for next month amid developer debate", source: "The Block", sentiment: "neutral", time: "15m ago", symbols: ["ETH/USDT"] },
    { id: "n3", headline: "SEC delays decision on spot ETH ETF, market reacts with 2% drop", source: "Reuters", sentiment: "negative", time: "1h ago", symbols: ["ETH/USDT"] },
    { id: "n4", headline: "Solana DeFi TVL hits all-time high of $8.2 billion", source: "DeFiLlama", sentiment: "positive", time: "2h ago", symbols: ["SOL/USDT"] },
    { id: "n5", headline: "Binance reports record monthly trading volume for Q4", source: "Binance Blog", sentiment: "positive", time: "3h ago", symbols: ["BNB/USDT"] },
    { id: "n6", headline: "Crypto market volatility index reaches 6-month high as macro uncertainty grows", source: "Bloomberg", sentiment: "negative", time: "4h ago", symbols: ["BTC/USDT", "ETH/USDT"] },
    { id: "n7", headline: "XRP legal battle enters final phase, analysts optimistic on outcome", source: "Cointelegraph", sentiment: "positive", time: "5h ago", symbols: ["XRP/USDT"] },
  ]
}

export function generateScreener(): ScreenerRow[] {
  return [
    { symbol: "BTC/USDT", price: 67500, change: 1250, changePct: 1.89, volume: 28500000000, marketCap: 1320000000000, high24h: 68200, low24h: 66100 },
    { symbol: "ETH/USDT", price: 3450, change: -45, changePct: -1.29, volume: 14200000000, marketCap: 414000000000, high24h: 3520, low24h: 3380 },
    { symbol: "SOL/USDT", price: 185, change: 8.5, changePct: 4.82, volume: 3200000000, marketCap: 86000000000, high24h: 192, low24h: 175 },
    { symbol: "BNB/USDT", price: 590, change: 12, changePct: 2.07, volume: 1800000000, marketCap: 88000000000, high24h: 598, low24h: 578 },
    { symbol: "XRP/USDT", price: 0.62, change: 0.02, changePct: 3.33, volume: 2100000000, marketCap: 34000000000, high24h: 0.64, low24h: 0.59 },
    { symbol: "ADA/USDT", price: 0.48, change: -0.01, changePct: -2.04, volume: 450000000, marketCap: 17000000000, high24h: 0.50, low24h: 0.46 },
    { symbol: "AVAX/USDT", price: 38, change: 1.8, changePct: 4.98, volume: 680000000, marketCap: 15600000000, high24h: 39.5, low24h: 36.2 },
    { symbol: "DOGE/USDT", price: 0.16, change: 0.008, changePct: 5.26, volume: 1200000000, marketCap: 23000000000, high24h: 0.168, low24h: 0.151 },
  ]
}

export function formatPrice(price: number): string {
  if (price >= 10000) return price.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })
  if (price >= 1000) return price.toLocaleString("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 })
  if (price >= 10) return price.toFixed(2)
  if (price >= 1) return price.toFixed(3)
  return price.toFixed(4)
}

export function formatVolume(vol: number): string {
  if (vol >= 1e12) return `${(vol / 1e12).toFixed(2)}T`
  if (vol >= 1e9) return `${(vol / 1e9).toFixed(2)}B`
  if (vol >= 1e6) return `${(vol / 1e6).toFixed(1)}M`
  if (vol >= 1e3) return `${(vol / 1e3).toFixed(1)}K`
  return vol.toFixed(2)
}
