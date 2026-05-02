import { Clock } from "lucide-react"
import type { EventType } from "@/types/database"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { cn } from "@/lib/utils"

type EventTypeCardProps = {
  eventType: EventType
  selected?: boolean
  onClick: () => void
}

export function EventTypeCard({ eventType, selected, onClick }: EventTypeCardProps) {
  return (
    <Card
      className={cn(
        "cursor-pointer transition-all hover:border-primary/50",
        selected && "border-primary ring-2 ring-primary/20"
      )}
      onClick={onClick}
    >
      <CardHeader className="pb-2">
        <div className="flex items-center gap-3">
          <div
            className="size-3 rounded-full"
            style={{ backgroundColor: eventType.color }}
          />
          <CardTitle className="text-lg">{eventType.title}</CardTitle>
        </div>
        <CardDescription>{eventType.description}</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Clock className="size-4" />
          <span>{eventType.duration_minutes} minutes</span>
        </div>
      </CardContent>
    </Card>
  )
}
