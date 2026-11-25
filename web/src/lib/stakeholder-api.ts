import { REQUEST_TIMEOUT_MS } from "./api"
import type { Board } from "./stakeholder"

export type StakeholderResult<T = unknown> =
  | { ok: true; data: T }
  | { ok: false; unauthorized: boolean; error: string }

export interface StakeholderApi {
  board(): Promise<StakeholderResult<Board>>
  done(booking: number): Promise<StakeholderResult>
  decline(team: number, ticks: number): Promise<StakeholderResult>
}

type Fetch = typeof fetch

// Every call carries the stakeholder password in a header and uses a relative URL.
export function createStakeholderApi(password: string, fetchFn: Fetch = (...args) => fetch(...args)): StakeholderApi {
  async function call<T>(method: "GET" | "POST", path: string, payload?: unknown): Promise<StakeholderResult<T>> {
    let resp: Response
    try {
      resp = await fetchFn(`api/stakeholder/${path}`, {
        method,
        headers: { "X-Stakeholder-Password": password, "Content-Type": "application/json" },
        body: method === "POST" ? JSON.stringify(payload ?? {}) : undefined,
        cache: "no-store",
        signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
      })
    } catch {
      return { ok: false, unauthorized: false, error: "Could not reach the server." }
    }
    if (resp.status === 401) return { ok: false, unauthorized: true, error: "Wrong stakeholder password." }
    let data: unknown = {}
    try {
      data = await resp.json()
    } catch {
      // An unreadable body is reported through the status below.
    }
    const body = data as { ok?: boolean; error?: string }
    if (!resp.ok || body.ok === false) {
      return { ok: false, unauthorized: false, error: body.error ?? `The server answered ${resp.status}.` }
    }
    return { ok: true, data: data as T }
  }

  return {
    board: () => call<Board>("GET", "board"),
    done: (booking) => call("POST", "done", { booking }),
    // Only the count of ticked items is sent, never which ones.
    decline: (team, ticks) => call("POST", "decline", { team, ticks }),
  }
}

const PASSWORD_KEY = "fixforward.stakeholderPassword"

// Kept for this browser session only; closing the tab forgets it.
export function recallStakeholderPassword(): string | null {
  try {
    return sessionStorage.getItem(PASSWORD_KEY)
  } catch {
    return null
  }
}

export function rememberStakeholderPassword(password: string): void {
  try {
    sessionStorage.setItem(PASSWORD_KEY, password)
  } catch {
    // The screen works without it; the stakeholder signs in again after a reload.
  }
}

export function forgetStakeholderPassword(): void {
  try {
    sessionStorage.removeItem(PASSWORD_KEY)
  } catch {
    // Nothing to do.
  }
}
