import { useState, useCallback } from "react"

export type MarginMode = "cross" | "isolated"

export interface PositionSettings {
  leverage: number
  marginMode: MarginMode
}

// Per-symbol position settings store (in-memory, can be persisted later)
const defaultSettings: PositionSettings = { leverage: 10, marginMode: "cross" }

// Shared state across hook instances (module-level singleton)
const store: Record<string, PositionSettings> = {}

function getSettings(symbol: string): PositionSettings {
  return store[symbol] ?? { ...defaultSettings }
}

export function usePositionSettings(symbol: string) {
  const [, forceUpdate] = useState(0)

  const settings = getSettings(symbol)

  const setLeverage = useCallback((leverage: number) => {
    store[symbol] = { ...getSettings(symbol), leverage }
    forceUpdate((n) => n + 1)
  }, [symbol])

  const setMarginMode = useCallback((marginMode: MarginMode) => {
    store[symbol] = { ...getSettings(symbol), marginMode }
    forceUpdate((n) => n + 1)
  }, [symbol])

  return { settings, setLeverage, setMarginMode }
}
