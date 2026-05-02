import { CircleCheck as CheckCircle, Calendar, Clock, ArrowLeft } from "lucide-react"
import { format } from "date-fns"
import type { EventType } from "@/types/database"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

type BookingConfirmationProps = {
  eventType: EventType
  selectedDate: Date
  selectedTime: string
  onBookAnother: () => void
}

export function BookingConfirmation({
  eventType,
  selectedDate,
  selectedTime,
  onBookAnother,
}: BookingConfirmationProps) {
  return (
    <Card className="w-full max-w-lg text-center">
      <CardHeader>
        <div className="mx-auto mb-4 flex size-16 items-center justify-center rounded-full bg-primary/10">
          <CheckCircle className="size-8 text-primary" />
        </div>
        <CardTitle className="text-2xl">Booking Confirmed!</CardTitle>
        <CardDescription>
          Your appointment has been scheduled successfully
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="mb-6 rounded-lg bg-muted p-4 text-left">
          <div
            className="mb-3 flex items-center gap-2 font-medium"
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

        <p className="mb-6 text-sm text-muted-foreground">
          A confirmation email will be sent to you shortly with all the details.
        </p>

        <Button variant="outline" onClick={onBookAnother} className="w-full">
          <ArrowLeft className="size-4" data-icon="inline-start" />
          Book Another Appointment
        </Button>
      </CardContent>
    </Card>
  )
}
