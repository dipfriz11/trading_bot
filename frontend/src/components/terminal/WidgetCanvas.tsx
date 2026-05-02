import { useRef } from "react"
import { useTerminal } from "@/contexts/TerminalContext"
import { WidgetWrapper } from "./WidgetWrapper"
import { WidgetRenderer, WidgetHeaderExtra } from "./WidgetRenderer"

export function WidgetCanvas() {
  const { activeTab } = useTerminal()
  const canvasRef = useRef<HTMLDivElement>(null)

  return (
    <div
      ref={canvasRef}
      className="relative flex-1 overflow-hidden workspace-canvas"
      style={{ minHeight: 0 }}
    >
      {activeTab?.widgets.map((widget) => (
        <WidgetWrapper
          key={widget.id}
          widget={widget}
          canvasRef={canvasRef}
          headerExtra={<WidgetHeaderExtra widget={widget} />}
        >
          <WidgetRenderer widget={widget} />
        </WidgetWrapper>
      ))}

      {(!activeTab || activeTab.widgets.length === 0) && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3" style={{ pointerEvents: "none" }}>
          <div style={{ opacity: 0.08 }}>
            <svg width="64" height="64" viewBox="0 0 64 64" fill="none">
              <rect x="4" y="4" width="24" height="24" rx="3" stroke="currentColor" strokeWidth="1.5" />
              <rect x="36" y="4" width="24" height="24" rx="3" stroke="currentColor" strokeWidth="1.5" />
              <rect x="4" y="36" width="24" height="24" rx="3" stroke="currentColor" strokeWidth="1.5" />
              <rect x="36" y="36" width="24" height="24" rx="3" stroke="currentColor" strokeWidth="1.5" />
            </svg>
          </div>
          <div className="flex flex-col items-center gap-1" style={{ opacity: 0.2 }}>
            <span className="text-sm font-mono font-medium">Empty workspace</span>
            <span className="text-xs font-mono">Click "Add Widget" to get started</span>
          </div>
        </div>
      )}
    </div>
  )
}
