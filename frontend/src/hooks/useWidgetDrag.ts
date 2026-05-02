import { useRef, useCallback, useEffect } from "react"
import type { WidgetRect, ResizeHandle, Widget } from "@/types/terminal"
import { WIDGET_MIN_SIZE } from "@/types/terminal"

interface UseWidgetDragOptions {
  widget: Widget
  canvasRef: React.RefObject<HTMLDivElement | null>
  onMove: (rect: WidgetRect) => void
  onBringToFront: () => void
  allWidgets: Widget[]
  onUpdateAll: (updates: { id: string; rect: WidgetRect }[]) => void
}

interface DragState {
  type: "move" | "resize"
  handle?: ResizeHandle
  startMouseX: number
  startMouseY: number
  startRect: WidgetRect
}

export function useWidgetDrag({
  widget,
  canvasRef,
  onMove,
  onBringToFront,
  allWidgets,
  onUpdateAll,
}: UseWidgetDragOptions) {
  const dragRef = useRef<DragState | null>(null)

  const clampRect = useCallback(
    (rect: WidgetRect): WidgetRect => {
      const canvas = canvasRef.current
      if (!canvas) return rect
      const minSize = WIDGET_MIN_SIZE[widget.type]
      const maxX = canvas.clientWidth - minSize.width
      const maxY = canvas.clientHeight - minSize.height
      return {
        x: Math.max(0, Math.min(rect.x, maxX)),
        y: Math.max(0, Math.min(rect.y, maxY)),
        width: Math.max(minSize.width, rect.width),
        height: Math.max(minSize.height, rect.height),
      }
    },
    [canvasRef, widget.type]
  )

  const startMove = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault()
      e.stopPropagation()
      onBringToFront()
      dragRef.current = {
        type: "move",
        startMouseX: e.clientX,
        startMouseY: e.clientY,
        startRect: { ...widget.rect },
      }
    },
    [widget.rect, onBringToFront]
  )

  const startResize = useCallback(
    (e: React.MouseEvent, handle: ResizeHandle) => {
      e.preventDefault()
      e.stopPropagation()
      onBringToFront()
      dragRef.current = {
        type: "resize",
        handle,
        startMouseX: e.clientX,
        startMouseY: e.clientY,
        startRect: { ...widget.rect },
      }
    },
    [widget.rect, onBringToFront]
  )

  useEffect(() => {
    function onMouseMove(e: MouseEvent) {
      const drag = dragRef.current
      if (!drag) return

      const dx = e.clientX - drag.startMouseX
      const dy = e.clientY - drag.startMouseY
      const { x, y, width, height } = drag.startRect
      const minSize = WIDGET_MIN_SIZE[widget.type]

      let newRect: WidgetRect

      if (drag.type === "move") {
        newRect = clampRect({ x: x + dx, y: y + dy, width, height })
      } else {
        const h = drag.handle!
        let nx = x, ny = y, nw = width, nh = height

        if (h.includes("e")) nw = Math.max(minSize.width, width + dx)
        if (h.includes("w")) {
          nw = Math.max(minSize.width, width - dx)
          nx = x + (width - nw)
        }
        if (h.includes("s")) nh = Math.max(minSize.height, height + dy)
        if (h.includes("n")) {
          nh = Math.max(minSize.height, height - dy)
          ny = y + (height - nh)
        }

        const canvas = canvasRef.current
        if (canvas) {
          nx = Math.max(0, nx)
          ny = Math.max(0, ny)
        }
        newRect = { x: nx, y: ny, width: nw, height: nh }
      }

      onMove(newRect)
    }

    function onMouseUp() {
      dragRef.current = null
    }

    window.addEventListener("mousemove", onMouseMove)
    window.addEventListener("mouseup", onMouseUp)
    return () => {
      window.removeEventListener("mousemove", onMouseMove)
      window.removeEventListener("mouseup", onMouseUp)
    }
  }, [widget.type, clampRect, onMove, canvasRef, allWidgets, onUpdateAll])

  return { startMove, startResize }
}
