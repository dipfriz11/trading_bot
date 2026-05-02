import { CalendarDays, Clock, Users, Zap } from "lucide-react"
import { Button } from "@/components/ui/button"

type HeroSectionProps = {
  onBookNow: () => void
}

export function HeroSection({ onBookNow }: HeroSectionProps) {
  return (
    <section className="relative overflow-hidden border-b bg-gradient-to-b from-muted/50 to-background">
      <div className="absolute inset-0 -z-10 bg-[radial-gradient(45%_40%_at_50%_60%,var(--muted)_0%,transparent_100%)]" />
      <div className="mx-auto max-w-6xl px-4 py-24 sm:px-6 sm:py-32 lg:px-8">
        <div className="mx-auto max-w-3xl text-center">
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border bg-background px-4 py-1.5 text-sm text-muted-foreground">
            <Zap className="size-4 text-chart-1" />
            Simple scheduling for everyone
          </div>
          <h1 className="text-4xl font-extrabold tracking-tight text-balance sm:text-5xl lg:text-6xl">
            Schedule meetings
            <span className="block text-chart-2">without the hassle</span>
          </h1>
          <p className="mx-auto mt-6 max-w-xl text-lg leading-relaxed text-muted-foreground text-balance">
            Let your clients book appointments directly on your calendar. No back-and-forth emails, no scheduling conflicts, just simple and efficient booking.
          </p>
          <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
            <Button size="lg" onClick={onBookNow} className="w-full sm:w-auto">
              <CalendarDays className="size-5" />
              Book an Appointment
            </Button>
            <Button variant="outline" size="lg" className="w-full sm:w-auto">
              Learn More
            </Button>
          </div>
        </div>

        <div className="mt-16 grid grid-cols-1 gap-6 sm:grid-cols-3">
          <div className="flex items-center gap-4 rounded-lg border bg-card p-4">
            <div className="flex size-12 shrink-0 items-center justify-center rounded-lg bg-chart-1/10">
              <Clock className="size-6 text-chart-1" />
            </div>
            <div>
              <p className="font-semibold">Save Time</p>
              <p className="text-sm text-muted-foreground">Automate your scheduling</p>
            </div>
          </div>
          <div className="flex items-center gap-4 rounded-lg border bg-card p-4">
            <div className="flex size-12 shrink-0 items-center justify-center rounded-lg bg-chart-2/10">
              <Users className="size-6 text-chart-2" />
            </div>
            <div>
              <p className="font-semibold">No Conflicts</p>
              <p className="text-sm text-muted-foreground">Real-time availability</p>
            </div>
          </div>
          <div className="flex items-center gap-4 rounded-lg border bg-card p-4">
            <div className="flex size-12 shrink-0 items-center justify-center rounded-lg bg-chart-3/10">
              <Zap className="size-6 text-chart-3" />
            </div>
            <div>
              <p className="font-semibold">Instant Booking</p>
              <p className="text-sm text-muted-foreground">Confirm in seconds</p>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
