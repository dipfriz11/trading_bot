import { useState, useRef, useCallback } from "react"
import { Plus, X } from "lucide-react"
import { useTerminal } from "@/contexts/TerminalContext"

export function TabBar() {
  const { state, addTab, removeTab, setActiveTab, renameTab, reorderTabs } = useTerminal()
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editValue, setEditValue] = useState("")
  const inputRef = useRef<HTMLInputElement>(null)

  // Drag-and-drop state
  const dragIndex = useRef<number | null>(null)
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null)
  const [, setDragging] = useState(false)

  const handleDoubleClick = (tabId: string, label: string) => {
    setEditingId(tabId)
    setEditValue(label)
    setTimeout(() => inputRef.current?.select(), 0)
  }

  const handleRenameCommit = () => {
    if (editingId && editValue.trim()) {
      renameTab(editingId, editValue.trim())
    }
    setEditingId(null)
  }

  const handleDragStart = useCallback((e: React.DragEvent, index: number) => {
    dragIndex.current = index
    setDragging(true)
    e.dataTransfer.effectAllowed = "move"
    // Ghost image: transparent
    const ghost = document.createElement("div")
    ghost.style.position = "fixed"
    ghost.style.top = "-9999px"
    document.body.appendChild(ghost)
    e.dataTransfer.setDragImage(ghost, 0, 0)
    setTimeout(() => document.body.removeChild(ghost), 0)
  }, [])

  const handleDragOver = useCallback((e: React.DragEvent, index: number) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = "move"
    setDragOverIndex(index)
  }, [])

  const handleDrop = useCallback((e: React.DragEvent, toIndex: number) => {
    e.preventDefault()
    const fromIndex = dragIndex.current
    if (fromIndex === null || fromIndex === toIndex) return

    reorderTabs(fromIndex, toIndex)
    dragIndex.current = null
    setDragOverIndex(null)
    setDragging(false)
  }, [state.tabs, reorderTabs])

  const handleDragEnd = useCallback(() => {
    dragIndex.current = null
    setDragOverIndex(null)
    setDragging(false)
  }, [])

  return (
    <div className="flex items-end flex-1 min-w-0 overflow-x-auto overflow-y-visible">
      {state.tabs.map((tab, index) => {
        const isActive = tab.id === state.activeTabId
        const isDragOver = dragOverIndex === index && dragIndex.current !== index

        return (
          <div
            key={tab.id}
            className="workspace-tab"
            data-active={isActive}
            data-dragover={isDragOver}
            draggable
            onClick={() => setActiveTab(tab.id)}
            onDoubleClick={() => handleDoubleClick(tab.id, tab.label)}
            onDragStart={(e) => handleDragStart(e, index)}
            onDragOver={(e) => handleDragOver(e, index)}
            onDrop={(e) => handleDrop(e, index)}
            onDragEnd={handleDragEnd}
          >
            {/* Left curve */}
            <span className="workspace-tab-curve workspace-tab-curve-left" />

            {editingId === tab.id ? (
              <input
                ref={inputRef}
                value={editValue}
                onChange={(e) => setEditValue(e.target.value)}
                onBlur={handleRenameCommit}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleRenameCommit()
                  if (e.key === "Escape") setEditingId(null)
                  e.stopPropagation()
                }}
                className="workspace-tab-input"
                onClick={(e) => e.stopPropagation()}
                onMouseDown={(e) => e.stopPropagation()}
              />
            ) : (
              <span className="workspace-tab-label">{tab.label}</span>
            )}

            {state.tabs.length > 1 && (
              <button
                className="workspace-tab-close"
                onClick={(e) => {
                  e.stopPropagation()
                  removeTab(tab.id)
                }}
                onMouseDown={(e) => e.stopPropagation()}
              >
                <X size={9} />
              </button>
            )}

            {/* Right curve */}
            <span className="workspace-tab-curve workspace-tab-curve-right" />
          </div>
        )
      })}

      <button
        onClick={addTab}
        className="workspace-tab-add"
        title="New workspace"
      >
        <Plus size={13} />
      </button>
    </div>
  )
}
