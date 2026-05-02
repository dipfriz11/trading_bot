import { useRef } from "react"
import { Header } from "./header"
import { HeroSection } from "./hero-section"
import { FeaturesSection } from "./features-section"
import { TestimonialsSection } from "./testimonials-section"
import { BookingSection } from "./booking-section"
import { Footer } from "./footer"

export function LandingPage() {
  const bookingRef = useRef<HTMLElement>(null)

  const scrollToBooking = () => {
    bookingRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  return (
    <div className="min-h-svh">
      <Header onBookNow={scrollToBooking} />
      <main>
        <HeroSection onBookNow={scrollToBooking} />
        <FeaturesSection />
        <TestimonialsSection />
        <BookingSection ref={bookingRef} />
      </main>
      <Footer />
    </div>
  )
}
