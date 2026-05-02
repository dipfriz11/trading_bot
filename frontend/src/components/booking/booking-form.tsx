import { useState } from "react"
import { format, setHours, setMinutes, addMinutes } from "date-fns"
import { Calendar, Clock, ArrowLeft, Loader as Loader2 } from "lucide-react"
import type { EventType, BookingInsert } from "@/types/database"
import { db } from "@/lib/db"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Separator } from "@/components/ui/separator"

type BookingFormProps = {
  eventType: EventType
  selectedDate: Date
  selectedTime: string
  onBack: () => void
  onSuccess: () => void
}

export function BookingForm({
  eventType,
  selectedDate,
  selectedTime,
  onBack,
  onSuccess,
}: BookingFormProps) {
  const [name, setName] = useState("")
  const [email, setEmail] = useState("")
  const [notes, setNotes] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setIsSubmitting(true)

    try {
      const [hours, minutes] = selectedTime.split(":").map(Number)
      const startTime = setMinutes(setHours(selectedDate, hours), minutes)
      const endTime = addMinutes(startTime, eventType.duration_minutes)

      const bookingData: BookingInsert = {
        event_type_id: eventType.id,
        guest_name: name,
        guest_email: email,
        guest_notes: notes,
        start_time: startTime.toISOString(),
        end_time: endTime.toISOString(),
        status: "confirmed",
      }

      const { error: insertError } = await db.from("bookings").insert(bookingData)

      if (insertError) throw insertError

      onSuccess()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to book appointment")
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Card className="w-full max-w-lg">
      <CardHeader>
        <Button
          variant="ghost"
          size="sm"
          className="mb-2 w-fit"
          onClick={onBack}
        >
          <ArrowLeft className="size-4" data-icon="inline-start" />
          Back
        </Button>
        <CardTitle>Confirm your booking</CardTitle>
        <CardDescription>Fill in your details to complete the booking</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="mb-6 rounded-lg bg-muted p-4">
          <div
            className="mb-2 flex items-center gap-2 font-medium"
            style={{ color: eventType.color }}
          >
            <div
              className="size-2 rounded-full"
              style={{ backgroundColor: eventType.color }}
            />
            {eventType.title}
          </div>
          <div className="flex flex-col gap-2 text-sm text-muted-foreground">
            <div className="flex items-center gap-2">
              <Calendar className="size-4" />
              {format(selectedDate, "EEEE, MMMM d, yyyy")}
            </div>
            <div className="flex items-center gap-2">
              <Clock className="size-4" />
              {selectedTime} ({eventType.duration_minutes} min)
            </div>
          </div>
        </div>

        <Separator className="mb-6" />

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="name">Name</Label>
            <Input
              id="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Your name"
              required
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="notes">Notes (optional)</Label>
            <Textarea
              id="notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Any additional details or questions..."
              rows={3}
            />
          </div>

          {error && (
            <div className="rounded-lg bg-destructive/10 p-3 text-sm text-destructive">
              {error}
            </div>
          )}

          <Button type="submit" className="w-full" disabled={isSubmitting}>
            {isSubmitting && <Loader2 className="size-4 animate-spin" data-icon="inline-start" />}
            {isSubmitting ? "Booking..." : "Confirm Booking"}
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}
