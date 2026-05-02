import { useEffect, useState, forwardRef } from "react"
import { format, isSameDay, startOfDay, isBefore } from "date-fns"
import { Loader as Loader2 } from "lucide-react"
import type { EventType, Booking } from "@/types/database"
import { db } from "@/lib/db"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Calendar } from "@/components/ui/calendar"
import { Separator } from "@/components/ui/separator"
import { Button } from "@/components/ui/button"
import { EventTypeCard } from "@/components/booking/event-type-card"
import { TimeSlotPicker } from "@/components/booking/time-slot-picker"
import { BookingForm } from "@/components/booking/booking-form"
import { BookingConfirmation } from "@/components/booking/booking-confirmation"

type Step = "select-event" | "select-datetime" | "fill-form" | "confirmation"

export const BookingSection = forwardRef<HTMLElement>((_, ref) => {
  const [step, setStep] = useState<Step>("select-event")
  const [eventTypes, setEventTypes] = useState<EventType[]>([])
  const [bookings, setBookings] = useState<Booking[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedEventType, setSelectedEventType] = useState<EventType | null>(null)
  const [selectedDate, setSelectedDate] = useState<Date>(startOfDay(new Date()))
  const [selectedTime, setSelectedTime] = useState<string | null>(null)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    setLoading(true)
    try {
      const [eventTypesRes, bookingsRes] = await Promise.all([
        db.from("event_types").select("*").eq("is_active", true),
        db.from("bookings").select("*").in("status", ["pending", "confirmed"]),
      ])

      if (eventTypesRes.data) setEventTypes(eventTypesRes.data as EventType[])
      if (bookingsRes.data) setBookings(bookingsRes.data as Booking[])
    } finally {
      setLoading(false)
    }
  }

  const handleSelectEventType = (eventType: EventType) => {
    setSelectedEventType(eventType)
    setStep("select-datetime")
  }

  const handleSelectDate = (date: Date | undefined) => {
    if (date) {
      setSelectedDate(startOfDay(date))
      setSelectedTime(null)
    }
  }

  const handleSelectTime = (time: string) => {
    setSelectedTime(time)
  }

  const handleContinueToForm = () => {
    if (selectedTime) {
      setStep("fill-form")
    }
  }

  const handleBookingSuccess = () => {
    setStep("confirmation")
  }

  const handleBack = () => {
    if (step === "select-datetime") {
      setSelectedEventType(null)
      setSelectedTime(null)
      setStep("select-event")
    } else if (step === "fill-form") {
      setStep("select-datetime")
    }
  }

  const handleBookAnother = () => {
    setSelectedEventType(null)
    setSelectedDate(startOfDay(new Date()))
    setSelectedTime(null)
    setStep("select-event")
    loadData()
  }

  const bookingsForSelectedDate = bookings.filter((b) =>
    isSameDay(new Date(b.start_time), selectedDate)
  )

  return (
    <section ref={ref} id="booking" className="scroll-mt-8 py-24">
      <div className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8">
        <div className="mx-auto mb-12 max-w-2xl text-center">
          <h2 className="text-3xl font-semibold tracking-tight sm:text-4xl">
            Book Your Appointment
          </h2>
          <p className="mt-4 text-lg text-muted-foreground">
            Select a meeting type and choose a time that works for you.
          </p>
        </div>

        {loading ? (
          <div className="flex justify-center py-16">
            <Loader2 className="size-8 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <div className="flex justify-center">
            {step === "select-event" && (
              <div className="w-full max-w-2xl">
                <Card>
                  <CardHeader>
                    <CardTitle>Select an Event Type</CardTitle>
                    <CardDescription>Choose the type of meeting you'd like to book</CardDescription>
                  </CardHeader>
                  <CardContent className="grid gap-4">
                    {eventTypes.map((eventType) => (
                      <EventTypeCard
                        key={eventType.id}
                        eventType={eventType}
                        onClick={() => handleSelectEventType(eventType)}
                      />
                    ))}
                  </CardContent>
                </Card>
              </div>
            )}

            {step === "select-datetime" && selectedEventType && (
              <Card className="w-full">
                <CardHeader>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="mb-2 w-fit"
                    onClick={handleBack}
                  >
                    <span className="mr-2">&larr;</span>
                    Back
                  </Button>
                  <div className="flex items-center gap-2">
                    <div
                      className="size-3 rounded-full"
                      style={{ backgroundColor: selectedEventType.color }}
                    />
                    <CardTitle>{selectedEventType.title}</CardTitle>
                  </div>
                  <CardDescription>{selectedEventType.duration_minutes} minutes</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="flex flex-col gap-6 lg:flex-row">
                    <div className="flex-1">
                      <h3 className="mb-4 font-medium">Select a Date</h3>
                      <Calendar
                        mode="single"
                        selected={selectedDate}
                        onSelect={handleSelectDate}
                        disabled={(date) =>
                          isBefore(startOfDay(date), startOfDay(new Date())) ||
                          date.getDay() === 0 ||
                          date.getDay() === 6
                        }
                        className="rounded-lg border"
                      />
                    </div>
                    <Separator className="lg:hidden" />
                    <div className="hidden lg:block">
                      <Separator orientation="vertical" className="h-full" />
                    </div>
                    <div className="flex-1">
                      <h3 className="mb-4 font-medium">
                        {format(selectedDate, "EEEE, MMMM d")}
                      </h3>
                      <TimeSlotPicker
                        selectedDate={selectedDate}
                        durationMinutes={selectedEventType.duration_minutes}
                        existingBookings={bookingsForSelectedDate}
                        selectedTime={selectedTime}
                        onSelectTime={handleSelectTime}
                      />
                      {selectedTime && (
                        <Button
                          className="mt-4 w-full"
                          onClick={handleContinueToForm}
                        >
                          Continue
                        </Button>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

            {step === "fill-form" && selectedEventType && selectedTime && (
              <BookingForm
                eventType={selectedEventType}
                selectedDate={selectedDate}
                selectedTime={selectedTime}
                onBack={handleBack}
                onSuccess={handleBookingSuccess}
              />
            )}

            {step === "confirmation" && selectedEventType && selectedTime && (
              <BookingConfirmation
                eventType={selectedEventType}
                selectedDate={selectedDate}
                selectedTime={selectedTime}
                onBookAnother={handleBookAnother}
              />
            )}
          </div>
        )}
      </div>
    </section>
  )
})

BookingSection.displayName = "BookingSection"
