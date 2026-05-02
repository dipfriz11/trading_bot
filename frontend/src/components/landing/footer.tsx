import { CalendarDays } from "lucide-react"

export function Footer() {
  return (
    <footer className="border-t bg-muted/30">
      <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6 lg:px-8">
        <div className="flex flex-col items-center justify-between gap-6 sm:flex-row">
          <div className="flex items-center gap-2">
            <div className="flex size-8 items-center justify-center rounded-lg bg-primary">
              <CalendarDays className="size-4 text-primary-foreground" />
            </div>
            <span className="font-semibold">BookTime</span>
          </div>
          <p className="text-sm text-muted-foreground">
            Simple appointment scheduling for professionals.
          </p>
        </div>
      </div>
    </footer>
  )
}
