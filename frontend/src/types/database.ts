export type EventType = {
  id: string
  title: string
  description: string
  duration_minutes: number
  color: string
  is_active: boolean
  created_at: string
}

export type Booking = {
  id: string
  event_type_id: string
  guest_name: string
  guest_email: string
  guest_notes: string
  start_time: string
  end_time: string
  status: "pending" | "confirmed" | "cancelled"
  created_at: string
}

export type BookingInsert = {
  event_type_id: string
  guest_name: string
  guest_email: string
  guest_notes?: string
  start_time: string
  end_time: string
  status: "pending" | "confirmed" | "cancelled"
}

