import { useState, useEffect } from "react"
import { TrendingUp, TrendingDown, Minus, ExternalLink } from "lucide-react"
import type { Widget } from "@/types/terminal"
import { generateNews } from "@/lib/mock-data"
import type { NewsItem } from "@/types/terminal"

function SentimentIcon({ sentiment }: { sentiment: NewsItem["sentiment"] }) {
  if (sentiment === "positive") return <TrendingUp size={10} style={{ color: "#00e5a0" }} />
  if (sentiment === "negative") return <TrendingDown size={10} style={{ color: "#ff4757" }} />
  return <Minus size={10} style={{ color: "rgba(255,255,255,0.3)" }} />
}

export function NewsWidget(_props: { widget: Widget }) {
  const [news, setNews] = useState<NewsItem[]>(() => generateNews())
  const [filter, setFilter] = useState<"all" | "positive" | "negative">("all")
  const [expanded, setExpanded] = useState<string | null>(null)

  useEffect(() => {
    const t = setInterval(() => {
      const freshNews = generateNews()
      setNews((prev) => {
        const existingIds = new Set(prev.map((n) => n.id))
        const newItems = freshNews.filter((n) => !existingIds.has(n.id))
        if (newItems.length === 0) return prev
        return [...newItems.slice(0, 1), ...prev].slice(0, 30)
      })
    }, 8000)
    return () => clearInterval(t)
  }, [])

  const filtered = news.filter((n) => {
    if (filter === "all") return true
    return n.sentiment === filter
  })

  const sentimentColor = (s: NewsItem["sentiment"]) => {
    if (s === "positive") return "#00e5a0"
    if (s === "negative") return "#ff4757"
    return "rgba(255,255,255,0.3)"
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div
        className="flex-shrink-0 flex items-center gap-1 px-2 py-1"
        style={{ borderBottom: "1px solid rgba(255,255,255,0.05)" }}
      >
        {(["all", "positive", "negative"] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className="text-xs font-mono px-2 py-0.5 rounded capitalize transition-colors"
            style={{
              background: filter === f ? "rgba(255,255,255,0.08)" : "transparent",
              color: filter === f
                ? f === "positive" ? "#00e5a0" : f === "negative" ? "#ff4757" : "rgba(255,255,255,0.8)"
                : "rgba(255,255,255,0.35)",
              border: "1px solid",
              borderColor: filter === f ? "rgba(255,255,255,0.1)" : "transparent",
              fontSize: 10,
            }}
            onMouseDown={(e) => e.stopPropagation()}
          >
            {f}
          </button>
        ))}
        <div
          className="ml-auto flex items-center gap-1"
          style={{ fontSize: 9, opacity: 0.4 }}
        >
          <span className="inline-block size-1.5 rounded-full animate-pulse" style={{ background: "#00e5a0" }} />
          <span className="font-mono">LIVE</span>
        </div>
      </div>

      <div className="flex-1 overflow-auto min-h-0">
        {filtered.map((item) => {
          const isExpanded = expanded === item.id
          return (
            <div
              key={item.id}
              className="px-2 py-2 cursor-pointer transition-colors hover:bg-white/[0.02]"
              style={{ borderBottom: "1px solid rgba(255,255,255,0.035)" }}
              onClick={() => setExpanded(isExpanded ? null : item.id)}
              onMouseDown={(e) => e.stopPropagation()}
            >
              <div className="flex items-start gap-2">
                <SentimentIcon sentiment={item.sentiment} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1 mb-0.5">
                    {item.symbols.map((sym) => (
                      <span
                        key={sym}
                        className="text-xs font-mono px-1 rounded"
                        style={{
                          background: "rgba(30,111,239,0.12)",
                          color: "#1e6fef",
                          fontSize: 9,
                          border: "1px solid rgba(30,111,239,0.2)",
                        }}
                      >
                        {sym.replace("/USDT", "")}
                      </span>
                    ))}
                    <span className="text-xs font-mono ml-auto flex-shrink-0" style={{ opacity: 0.3, fontSize: 9 }}>
                      {item.time}
                    </span>
                  </div>
                  <p
                    className="text-xs font-sans leading-snug"
                    style={{
                      color: sentimentColor(item.sentiment),
                      opacity: item.sentiment === "neutral" ? 0.75 : 0.9,
                      display: "-webkit-box",
                      WebkitLineClamp: isExpanded ? undefined : 2,
                      WebkitBoxOrient: "vertical",
                      overflow: isExpanded ? "visible" : "hidden",
                    }}
                  >
                    {item.headline}
                  </p>
                  {isExpanded && (
                    <div className="mt-1.5 flex items-center gap-2">
                      <span className="text-xs font-mono" style={{ opacity: 0.4, fontSize: 9 }}>{item.source}</span>
                      <button
                        className="flex items-center gap-0.5 text-xs font-mono ml-auto"
                        style={{ color: "#1e6fef", opacity: 0.7, fontSize: 9 }}
                        onClick={(e) => e.stopPropagation()}
                        onMouseDown={(e) => e.stopPropagation()}
                      >
                        <ExternalLink size={9} /> Read more
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
