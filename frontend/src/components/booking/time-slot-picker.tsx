import { format, addMinutes, setHours, setMinutes, isBefore, isAfter } from "date-fns"
import type { Booking } from "@/types/database"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { cn } from "@/lib/utils"

type TimeSlotPickerProps = {
  selectedDate: Date
  durationMinutes: number
  existingBookings: Booking[]
  selectedTime: string | null
  onSelectTime: (time: string) => void
}

export function TimeSlotPicker({
  selectedDate,
  durationMinutes,
  existingBookings,
  selectedTime,
  onSelectTime,
}: TimeSlotPickerProps) {
  const generateTimeSlots = () => {
    const slots: string[] = []
    const startHour = 9
    const endHour = 17

    let current = setMinutes(setHours(selectedDate, startHour), 0)
    const end = setMinutes(setHours(selectedDate, endHour), 0)

    while (isBefore(current, end)) {
      const slotEnd = addMinutes(current, durationMinutes)
      if (isBefore(slotEnd, end) || slotEnd.getTime() === end.getTime()) {
        slots.push(format(current, "HH:mm"))
      }
      current = addMinutes(current, 30)
    }

    return slots
  }

  const isSlotAvailable = (timeString: string) => {
    const [hours, minutes] = timeString.split(":").map(Number)
    const slotStart = setMinutes(setHours(selectedDate, hours), minutes)
    const slotEnd = addMinutes(slotStart, durationMinutes)
    const now = new Date()

    if (isBefore(slotStart, now)) {
      return false
    }

    return !existingBookings.some((booking) => {
      const bookingStart = new Date(booking.start_time)
      const bookingEnd = new Date(booking.end_time)
      return (
        (isBefore(slotStart, bookingEnd) && isAfter(slotEnd, bookingStart)) ||
        slotStart.getTime() === bookingStart.getTime()
      )
    })
  }

  const timeSlots = generateTimeSlots()
  const availableSlots = timeSlots.filter(isSlotAvailable)

  if (availableSlots.length === 0) {
    return (
      <div className="flex h-full items-center justify-center text-muted-foreground">
        No available times on this date
      </div>
    )
  }

  return (
    <ScrollArea className="h-[320px]">
      <div className="grid gap-2 pr-4">
        {availableSlots.map((time) => (
          <Button
            key={time}
            variant={selectedTime === time ? "default" : "outline"}
            className={cn(
              "justify-center font-medium",
              selectedTime === time && "ring-2 ring-primary/20"
            )}
            onClick={() => onSelectTime(time)}
          >
            {time}
          </Button>
        ))}
      </div>
    </ScrollArea>
  )
}
