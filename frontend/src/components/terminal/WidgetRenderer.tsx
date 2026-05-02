import React from "react"
import type { Widget } from "@/types/terminal"
import { ChartWidget, ChartHeaderExtra } from "@/components/widgets/ChartWidget"
import { OrderBookWidget } from "@/components/widgets/OrderBookWidget"
import { TradesWidget } from "@/components/widgets/TradesWidget"
import { PortfolioWidget } from "@/components/widgets/PortfolioWidget"
import { ScreenerWidget } from "@/components/widgets/ScreenerWidget"
import { PnlWidget } from "@/components/widgets/PnlWidget"
import { AlertsWidget } from "@/components/widgets/AlertsWidget"
import { OrderConsoleWidget } from "@/components/widgets/OrderConsoleWidget"
import { NewsWidget } from "@/components/widgets/NewsWidget"

export function WidgetRenderer({ widget }: { widget: Widget }) {
  switch (widget.type) {
    case "chart":
      return <ChartWidget widget={widget} />
    case "orderbook":
      return <OrderBookWidget widget={widget} />
    case "trades":
      return <TradesWidget widget={widget} />
    case "portfolio":
      return <PortfolioWidget widget={widget} />
    case "screener":
      return <ScreenerWidget widget={widget} />
    case "pnl":
      return <PnlWidget widget={widget} />
    case "alerts":
      return <AlertsWidget widget={widget} />
    case "order-console":
      return <OrderConsoleWidget widget={widget} />
    case "news":
      return <NewsWidget widget={widget} />
    default:
      return null
  }
}

export function WidgetHeaderExtra({ widget }: { widget: Widget }): React.ReactNode {
  if (widget.type === "chart") return <ChartHeaderExtra widget={widget} />
  return null
}
