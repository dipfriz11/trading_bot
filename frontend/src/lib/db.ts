import type { EventType, Booking } from "@/types/database"

const MOCK_EVENT_TYPES: EventType[] = [
  {
    id: "1",
    title: "Quick Chat",
    description: "A short 15-minute check-in to discuss quick questions or updates.",
    duration_minutes: 15,
    color: "#3b82f6",
    is_active: true,
    created_at: "2026-01-15T10:00:00Z",
  },
  {
    id: "2",
    title: "Consultation",
    description: "A 30-minute session to discuss your project requirements in detail.",
    duration_minutes: 30,
    color: "#8b5cf6",
    is_active: true,
    created_at: "2026-01-15T10:00:00Z",
  },
  {
    id: "3",
    title: "Strategy Session",
    description: "A comprehensive 60-minute meeting for planning and strategy discussions.",
    duration_minutes: 60,
    color: "#10b981",
    is_active: true,
    created_at: "2026-01-15T10:00:00Z",
  },
]

let mockBookings: Booking[] = [
  {
    id: "b1",
    event_type_id: "2",
    guest_name: "Alice Johnson",
    guest_email: "alice@example.com",
    guest_notes: "",
    start_time: new Date(Date.now() + 86400000).toISOString().replace(/T.*/, "T14:00:00Z"),
    end_time: new Date(Date.now() + 86400000).toISOString().replace(/T.*/, "T14:30:00Z"),
    status: "confirmed",
    created_at: "2026-03-20T09:00:00Z",
  },
]

type QueryResult<T> = { data: T | null; error: null } | { data: null; error: Error }

function createQueryBuilder<T>(table: string) {
  let data: T[] = table === "event_types" ? ([...MOCK_EVENT_TYPES] as T[]) : ([...mockBookings] as T[])

  const builder = {
    select(_columns?: string) {
      return builder
    },
    eq(column: string, value: unknown) {
      data = data.filter((row: any) => row[column] === value)
      return builder
    },
    in(column: string, values: unknown[]) {
      data = data.filter((row: any) => values.includes(row[column]))
      return builder
    },
    async insert(row: unknown): Promise<QueryResult<null>> {
      const entry = {
        id: crypto.randomUUID(),
        created_at: new Date().toISOString(),
        ...(row as object),
      } as Booking
      mockBookings.push(entry)
      return { data: null, error: null }
    },
    then(resolve: (result: QueryResult<T[]>) => void) {
      resolve({ data: data as T[], error: null })
    },
  }

  return builder
}

export const db = {
  from(table: string) {
    return createQueryBuilder(table)
  },
}
