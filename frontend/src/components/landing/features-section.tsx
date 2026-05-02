import { Calendar, Bell, Shield, Globe, Smartphone, Repeat } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

const features = [
  {
    icon: Calendar,
    title: "Flexible Scheduling",
    description: "Offer multiple meeting types with different durations. Let clients choose what works best for them.",
    color: "text-chart-1",
    bgColor: "bg-chart-1/10",
  },
  {
    icon: Bell,
    title: "Instant Notifications",
    description: "Receive confirmation emails immediately when someone books a meeting with you.",
    color: "text-chart-2",
    bgColor: "bg-chart-2/10",
  },
  {
    icon: Shield,
    title: "No Account Required",
    description: "Your clients can book appointments without creating an account or signing in.",
    color: "text-chart-3",
    bgColor: "bg-chart-3/10",
  },
  {
    icon: Globe,
    title: "Always Available",
    description: "Your booking page is available 24/7, letting clients schedule meetings anytime.",
    color: "text-chart-4",
    bgColor: "bg-chart-4/10",
  },
  {
    icon: Smartphone,
    title: "Mobile Friendly",
    description: "Fully responsive design works perfectly on any device, desktop or mobile.",
    color: "text-chart-5",
    bgColor: "bg-chart-5/10",
  },
  {
    icon: Repeat,
    title: "Conflict Prevention",
    description: "Automatically shows only available time slots, preventing double bookings.",
    color: "text-chart-1",
    bgColor: "bg-chart-1/10",
  },
]

export function FeaturesSection() {
  return (
    <section className="border-b bg-muted/30 py-24">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-3xl font-semibold tracking-tight sm:text-4xl">
            Everything you need for effortless scheduling
          </h2>
          <p className="mt-4 text-lg text-muted-foreground">
            Powerful features designed to make booking appointments simple for you and your clients.
          </p>
        </div>

        <div className="mt-16 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((feature) => (
            <Card key={feature.title} className="border-0 bg-card/50 shadow-none">
              <CardHeader>
                <div className={`mb-2 flex size-12 items-center justify-center rounded-lg ${feature.bgColor}`}>
                  <feature.icon className={`size-6 ${feature.color}`} />
                </div>
                <CardTitle className="text-lg">{feature.title}</CardTitle>
              </CardHeader>
              <CardContent>
                <CardDescription className="text-base">{feature.description}</CardDescription>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </section>
  )
}
