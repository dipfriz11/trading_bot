import { useState, useRef, useEffect } from "react"
import { createPortal } from "react-dom"
import { Save, ChevronDown, Trash2, BookMarked } from "lucide-react"
import type { Template } from "@/hooks/useTemplates"

interface TemplateBarProps<T> {
  templates: Template<T>[]
  activeId: string | null
  onSelect: (template: Template<T>) => void
  onSave: (name: string) => void
  onDelete: (id: string) => void
  isDirty: boolean
}

export function TemplateBar<T>({
  templates,
  activeId,
  onSelect,
  onSave,
  onDelete,
  isDirty,
}: TemplateBarProps<T>) {
  const [open, setOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [nameInput, setNameInput] = useState("")
  const dropRef = useRef<HTMLDivElement>(null)
  const btnRef = useRef<HTMLButtonElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const [pos, setPos] = useState<{ top: number; left: number; width: number } | null>(null)

  const active = templates.find((t) => t.id === activeId) ?? null

  const openDropdown = () => {
    const r = btnRef.current?.getBoundingClientRect()
    if (r) setPos({ top: r.bottom + 2, left: r.left, width: Math.max(r.width, 180) })
    setOpen(true)
  }

  useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      if (!dropRef.current?.contains(e.target as Node) && !btnRef.current?.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener("mousedown", handler)
    return () => document.removeEventListener("mousedown", handler)
  }, [open])

  useEffect(() => {
    if (saving) inputRef.current?.focus()
  }, [saving])

  const handleSave = () => {
    const name = nameInput.trim()
    if (!name) return
    onSave(name)
    setNameInput("")
    setSaving(false)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") handleSave()
    if (e.key === "Escape") { setSaving(false); setNameInput("") }
    e.stopPropagation()
  }

  const stopProp = (e: React.MouseEvent) => e.stopPropagation()

  const dropdownStyle: React.CSSProperties = {
    position: "fixed",
    top: pos?.top ?? 0,
    left: pos?.left ?? 0,
    width: pos?.width ?? 180,
    background: "rgba(18,22,28,0.98)",
    border: "1px solid rgba(255,255,255,0.1)",
    borderRadius: 5,
    boxShadow: "0 8px 24px rgba(0,0,0,0.5)",
    zIndex: 9999,
    overflow: "hidden",
  }

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 4,
        padding: "4px 10px",
        borderBottom: "1px solid rgba(255,255,255,0.06)",
      }}
      onMouseDown={stopProp}
    >
      {/* Template selector */}
      <button
        ref={btnRef}
        onClick={openDropdown}
        style={{
          flex: 1,
          display: "flex",
          alignItems: "center",
          gap: 5,
          padding: "3px 7px",
          background: "rgba(255,255,255,0.04)",
          border: "1px solid rgba(255,255,255,0.1)",
          borderRadius: 4,
          cursor: "pointer",
          color: active ? "rgba(200,214,229,0.85)" : "rgba(200,214,229,0.35)",
          fontSize: 10,
          fontFamily: "monospace",
          textAlign: "left",
          minWidth: 0,
        }}
      >
        <BookMarked size={10} style={{ opacity: 0.5, flexShrink: 0 }} />
        <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {active
            ? <>{active.name}{isDirty && <span style={{ color: "rgba(251,191,36,0.7)", marginLeft: 4 }}>*</span>}</>
            : "Шаблон…"
          }
        </span>
        <ChevronDown size={9} style={{ opacity: 0.4, flexShrink: 0 }} />
      </button>

      {/* Save button */}
      {!saving ? (
        <button
          onClick={() => {
            if (active) {
              onSave(active.name)
            } else {
              setSaving(true)
              setNameInput("")
            }
          }}
          title={active ? `Сохранить «${active.name}»` : "Сохранить как шаблон"}
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "3px 7px",
            gap: 4,
            background: isDirty && active
              ? "rgba(251,191,36,0.12)"
              : "rgba(255,255,255,0.05)",
            border: `1px solid ${isDirty && active ? "rgba(251,191,36,0.35)" : "rgba(255,255,255,0.1)"}`,
            borderRadius: 4,
            cursor: "pointer",
            color: isDirty && active ? "rgba(251,191,36,0.85)" : "rgba(200,214,229,0.45)",
            fontSize: 10,
            fontFamily: "monospace",
            whiteSpace: "nowrap",
            flexShrink: 0,
          }}
        >
          <Save size={10} />
          {!active && <span>Сохранить</span>}
        </button>
      ) : (
        <div style={{ display: "flex", alignItems: "center", gap: 4, flex: 1 }}>
          <input
            ref={inputRef}
            value={nameInput}
            onChange={(e) => setNameInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Название шаблона"
            style={{
              flex: 1,
              background: "rgba(255,255,255,0.06)",
              border: "1px solid rgba(30,111,239,0.4)",
              borderRadius: 4,
              color: "rgba(200,214,229,0.9)",
              padding: "3px 7px",
              fontSize: 10,
              fontFamily: "monospace",
              outline: "none",
              minWidth: 0,
            }}
          />
          <button
            onClick={handleSave}
            disabled={!nameInput.trim()}
            style={{
              padding: "3px 8px",
              background: nameInput.trim() ? "rgba(30,111,239,0.2)" : "rgba(255,255,255,0.04)",
              border: `1px solid ${nameInput.trim() ? "rgba(30,111,239,0.4)" : "rgba(255,255,255,0.1)"}`,
              borderRadius: 4,
              cursor: nameInput.trim() ? "pointer" : "default",
              color: nameInput.trim() ? "#1e6fef" : "rgba(255,255,255,0.2)",
              fontSize: 10,
              fontFamily: "monospace",
              flexShrink: 0,
            }}
          >
            ОК
          </button>
          <button
            onClick={() => { setSaving(false); setNameInput("") }}
            style={{
              padding: "3px 6px",
              background: "transparent",
              border: "1px solid rgba(255,255,255,0.08)",
              borderRadius: 4,
              cursor: "pointer",
              color: "rgba(255,255,255,0.3)",
              fontSize: 10,
              flexShrink: 0,
            }}
          >
            ✕
          </button>
        </div>
      )}

      {/* Dropdown portal */}
      {open && pos && createPortal(
        <div ref={dropRef} style={dropdownStyle} onMouseDown={stopProp}>
          {templates.length === 0 ? (
            <div style={{ padding: "8px 10px", fontSize: 10, fontFamily: "monospace", color: "rgba(255,255,255,0.3)", textAlign: "center" }}>
              Нет сохранённых шаблонов
            </div>
          ) : (
            templates.map((t) => (
              <div
                key={t.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  padding: "5px 8px",
                  background: t.id === activeId ? "rgba(30,111,239,0.12)" : "transparent",
                  borderLeft: t.id === activeId ? "2px solid rgba(30,111,239,0.5)" : "2px solid transparent",
                  cursor: "pointer",
                  gap: 6,
                }}
                onMouseEnter={(e) => { if (t.id !== activeId) (e.currentTarget as HTMLElement).style.background = "rgba(255,255,255,0.04)" }}
                onMouseLeave={(e) => { if (t.id !== activeId) (e.currentTarget as HTMLElement).style.background = "transparent" }}
              >
                <span
                  style={{ flex: 1, fontSize: 10, fontFamily: "monospace", color: t.id === activeId ? "#1e6fef" : "rgba(200,214,229,0.8)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
                  onClick={() => { onSelect(t); setOpen(false) }}
                >
                  {t.name}
                </span>
                <button
                  onClick={(e) => { e.stopPropagation(); onDelete(t.id); if (t.id === activeId) setOpen(false) }}
                  style={{ background: "none", border: "none", cursor: "pointer", padding: 2, color: "rgba(255,255,255,0.2)", flexShrink: 0, display: "flex" }}
                  title="Удалить шаблон"
                >
                  <Trash2 size={9} />
                </button>
              </div>
            ))
          )}
          <div
            style={{ borderTop: "1px solid rgba(255,255,255,0.06)", padding: "5px 8px", cursor: "pointer", fontSize: 10, fontFamily: "monospace", color: "rgba(255,255,255,0.4)", display: "flex", alignItems: "center", gap: 5 }}
            onClick={() => { setOpen(false); setSaving(true); setNameInput("") }}
            onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.color = "rgba(255,255,255,0.7)" }}
            onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.color = "rgba(255,255,255,0.4)" }}
          >
            <Save size={9} />
            Сохранить как новый…
          </div>
        </div>,
        document.body
      )}
    </div>
  )
}
