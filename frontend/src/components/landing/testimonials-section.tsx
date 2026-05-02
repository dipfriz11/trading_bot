import { Star } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"

const testimonials = [
  {
    name: "Sarah Johnson",
    role: "Freelance Consultant",
    initials: "SJ",
    content: "This booking system has completely transformed how I manage client meetings. No more endless email chains trying to find a time that works!",
    rating: 5,
  },
  {
    name: "Michael Chen",
    role: "Life Coach",
    initials: "MC",
    content: "My clients love how easy it is to book sessions. The interface is clean and intuitive. It's been a game-changer for my practice.",
    rating: 5,
  },
  {
    name: "Emily Rodriguez",
    role: "Therapist",
    initials: "ER",
    content: "Simple, professional, and exactly what I needed. The automatic conflict prevention saves me so much time and prevents booking mishaps.",
    rating: 5,
  },
]

export function TestimonialsSection() {
  return (
    <section className="border-b py-24">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-3xl font-semibold tracking-tight sm:text-4xl">
            Trusted by professionals everywhere
          </h2>
          <p className="mt-4 text-lg text-muted-foreground">
            See what others are saying about their scheduling experience.
          </p>
        </div>

        <div className="mt-16 grid gap-8 sm:grid-cols-2 lg:grid-cols-3">
          {testimonials.map((testimonial) => (
            <Card key={testimonial.name} className="bg-card">
              <CardContent className="pt-6">
                <div className="mb-4 flex gap-0.5">
                  {Array.from({ length: testimonial.rating }).map((_, i) => (
                    <Star key={i} className="size-4 fill-chart-1 text-chart-1" />
                  ))}
                </div>
                <p className="mb-6 text-muted-foreground">{testimonial.content}</p>
                <div className="flex items-center gap-3">
                  <Avatar>
                    <AvatarFallback className="bg-muted text-muted-foreground">
                      {testimonial.initials}
                    </AvatarFallback>
                  </Avatar>
                  <div>
                    <p className="font-medium">{testimonial.name}</p>
                    <p className="text-sm text-muted-foreground">{testimonial.role}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </section>
  )
}
