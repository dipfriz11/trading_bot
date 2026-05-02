import { createClient } from "@supabase/supabase-js"

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL as string
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY as string

class MockQueryBuilder {
  private mode: "list" | "write" = "list"

  select() {
    return this
  }

  upsert() {
    this.mode = "write"
    return this
  }

  delete() {
    this.mode = "write"
    return this
  }

  insert() {
    this.mode = "write"
    return this
  }

  eq() {
    return this
  }

  in() {
    return this
  }

  maybeSingle() {
    return Promise.resolve({
      data: null,
      error: new Error("Supabase env is not configured"),
    })
  }

  then(onFulfilled?: (value: { data: unknown; error: unknown }) => unknown, onRejected?: (reason: unknown) => unknown) {
    const result = this.mode === "list" ? { data: [], error: null } : { data: null, error: null }
    return Promise.resolve(result).then(onFulfilled, onRejected)
  }
}

const createMockSupabaseClient = () => ({ from: () => new MockQueryBuilder() })

export const supabase = supabaseUrl && supabaseAnonKey ? createClient(supabaseUrl, supabaseAnonKey) : (createMockSupabaseClient() as any)
