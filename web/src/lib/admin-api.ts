import { REQUEST_TIMEOUT_MS } from "./api"
import type { Clock } from "./types"

export interface AdminTeam {
  team: number
  name: string
  code: string
}

export interface AdminStatus {
  clock: Clock
  log_seq: number
  degraded: string | null
  snapshot_warning: string | null
  last_snapshot_seq: number
  last_snapshot_age: number | null
  revealed: boolean
  boot: string
  speed_choices: number[]
  teams: AdminTeam[]
}

export interface SnapshotInfo {
  id: string
  seq: number
  day: number
  digest?: string | null
  revealed?: boolean | null
}

export type AdminResult<T = unknown> =
  | { ok: true; data: T }
  | { ok: false; unauthorized: boolean; error: string }

export type ClockOp = "pause" | "resume" | "extend" | "hold" | "countdown" | "speed"

export interface AdminApi {
  status(): Promise<AdminResult<AdminStatus>>
  snapshots(): Promise<AdminResult<{ snapshots: SnapshotInfo[] }>>
  clock(op: ClockOp, value?: number): Promise<AdminResult>
  incident(team: number | "all", incident: number, op: "trigger" | "cancel"): Promise<AdminResult>
  edit(team: number, path: string, value: number | string, reason: string): Promise<AdminResult>
  restore(snapshot: string): Promise<AdminResult>
  reveal(): Promise<AdminResult>
  reload(): Promise<AdminResult>
  snapshotNow(): Promise<AdminResult>
}

type Fetch = typeof fetch

// Every admin call carries the password in a header and uses a relative URL.
export function createAdminApi(password: string, fetchFn: Fetch = (...args) => fetch(...args)): AdminApi {
  async function call<T>(method: "GET" | "POST", path: string, payload?: unknown): Promise<AdminResult<T>> {
    let resp: Response
    try {
      resp = await fetchFn(`api/admin/${path}`, {
        method,
        headers: { "X-Admin-Password": password, "Content-Type": "application/json" },
        body: method === "POST" ? JSON.stringify(payload ?? {}) : undefined,
        cache: "no-store",
        signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
      })
    } catch {
      return { ok: false, unauthorized: false, error: "Could not reach the server." }
    }
    if (resp.status === 401) return { ok: false, unauthorized: true, error: "Wrong admin password." }
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
    status: () => call<AdminStatus>("GET", "status"),
    snapshots: () => call<{ snapshots: SnapshotInfo[] }>("GET", "snapshots"),
    clock: (op, value) => call("POST", "clock", value === undefined ? { op } : { op, value }),
    incident: (team, incident, op) => call("POST", "incident", { team, incident, op }),
    async edit(team, path, value, reason) {
      if (!reason.trim()) return { ok: false, unauthorized: false, error: "Give a reason for the edit." }
      return call("POST", "edit", { team, path, value, reason })
    },
    restore: (snapshot) => call("POST", "restore", { snapshot }),
    reveal: () => call("POST", "reveal"),
    reload: () => call("POST", "reload"),
    snapshotNow: () => call("POST", "snapshot"),
  }
}

const PASSWORD_KEY = "fixforward.adminPassword"

// Kept for this browser session only; closing the tab forgets it.
export function recallAdminPassword(): string | null {
  try {
    return sessionStorage.getItem(PASSWORD_KEY)
  } catch {
    return null
  }
}

export function rememberAdminPassword(password: string): void {
  try {
    sessionStorage.setItem(PASSWORD_KEY, password)
  } catch {
    // The screen works without it; the operator signs in again after a reload.
  }
}

export function forgetAdminPassword(): void {
  try {
    sessionStorage.removeItem(PASSWORD_KEY)
  } catch {
    // Nothing to do.
  }
}
