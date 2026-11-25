import type { Calendar, Clock, TeamAction, TeamView } from "./types"

// Relative URLs only: the console works under any host or path.

// A stalled request must fail rather than hang, or polling stops and the
// console freezes on its last state. The slice view is much larger, so it gets longer.
export const REQUEST_TIMEOUT_MS = 8000
export const HEAVY_REQUEST_TIMEOUT_MS = 20000

export type ViewResult =
  | { kind: "ok"; clock: Clock; view: TeamView; etag: string | null }
  | { kind: "same" }
  | { kind: "invalid-code" }
  | { kind: "degraded" }

export type ActionOutcome = { ok: true } | { ok: false; error: string }

export interface ViewOptions {
  etag?: string | null
  days?: number
  slices?: boolean
}

export interface Api {
  clock(): Promise<Clock>
  view(code: string, opts?: ViewOptions): Promise<ViewResult>
  action(code: string, action: TeamAction): Promise<ActionOutcome>
}

type Fetch = typeof fetch

export function createApi(fetchFn: Fetch = (...args) => fetch(...args)): Api {
  return {
    async clock() {
      const resp = await fetchFn("api/clock", { cache: "no-store", signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS) })
      if (!resp.ok) throw new Error(`clock ${resp.status}`)
      return (await resp.json()) as Clock
    },

    async view(code, opts = {}) {
      const params = new URLSearchParams()
      if (opts.days) params.set("days", String(opts.days))
      if (opts.slices) params.set("slices", "1")
      const query = params.toString()
      const headers: Record<string, string> = {}
      if (opts.etag) headers["If-None-Match"] = opts.etag
      const resp = await fetchFn(`api/team/${encodeURIComponent(code)}/view${query ? `?${query}` : ""}`, {
        headers,
        cache: "no-store",
        signal: AbortSignal.timeout(opts.slices ? HEAVY_REQUEST_TIMEOUT_MS : REQUEST_TIMEOUT_MS),
      })
      if (resp.status === 304) return { kind: "same" }
      if (resp.status === 404) return { kind: "invalid-code" }
      if (resp.status === 503) return { kind: "degraded" }
      if (!resp.ok) throw new Error(`view ${resp.status}`)
      const body = (await resp.json()) as { clock: Clock; view: TeamView }
      return { kind: "ok", clock: body.clock, view: body.view, etag: resp.headers.get("ETag") }
    },

    async action(code, action) {
      let resp: Response
      try {
        resp = await fetchFn(`api/team/${encodeURIComponent(code)}/action`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action }),
          signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
        })
      } catch {
        return { ok: false, error: "Could not reach the server. Check the connection and try again." }
      }
      if (resp.status === 503) {
        return { ok: false, error: "The game is paused because the server cannot save its log." }
      }
      let body: { ok?: boolean; error?: string } = {}
      try {
        body = await resp.json()
      } catch {
        // Fall through to the generic message below.
      }
      if (resp.ok && body.ok !== false) return { ok: true }
      return { ok: false, error: body.error ?? "The server did not accept that action." }
    },
  }
}

// The calendar never changes during a game, so it is fetched once and kept outside Api.
export async function fetchCalendar(fetchFn: Fetch = (...args) => fetch(...args)): Promise<Calendar> {
  const resp = await fetchFn("api/calendar", { cache: "no-store", signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS) })
  if (!resp.ok) throw new Error(`calendar ${resp.status}`)
  return (await resp.json()) as Calendar
}
