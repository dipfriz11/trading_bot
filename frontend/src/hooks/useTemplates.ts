import { useState, useCallback } from "react"

export interface Template<T> {
  id: string
  name: string
  config: T
  createdAt: number
}

function storageKey(scope: string) {
  return `crypterm:templates:${scope}`
}

function load<T>(scope: string): Template<T>[] {
  try {
    const raw = localStorage.getItem(storageKey(scope))
    return raw ? (JSON.parse(raw) as Template<T>[]) : []
  } catch {
    return []
  }
}

function save<T>(scope: string, templates: Template<T>[]) {
  localStorage.setItem(storageKey(scope), JSON.stringify(templates))
}

export function useTemplates<T>(scope: string) {
  const [templates, setTemplates] = useState<Template<T>[]>(() => load<T>(scope))

  const saveTemplate = useCallback((name: string, config: T) => {
    setTemplates((prev) => {
      const existing = prev.find((t) => t.name === name)
      let next: Template<T>[]
      if (existing) {
        next = prev.map((t) => t.name === name ? { ...t, config } : t)
      } else {
        next = [...prev, { id: `${Date.now()}`, name, config, createdAt: Date.now() }]
      }
      save(scope, next)
      return next
    })
  }, [scope])

  const deleteTemplate = useCallback((id: string) => {
    setTemplates((prev) => {
      const next = prev.filter((t) => t.id !== id)
      save(scope, next)
      return next
    })
  }, [scope])

  return { templates, saveTemplate, deleteTemplate }
}
