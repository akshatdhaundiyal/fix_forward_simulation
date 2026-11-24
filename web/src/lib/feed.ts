import type { ActionOutcome, Api } from "./api"
import type { Clock, TeamAction, TeamView } from "./types"

export type FeedStatus =
  | "connecting"
  | "live"
  | "reconnecting"
  | "server-degraded"
  | "invalid-code"

export interface FeedState {
  clock: Clock | null
  view: TeamView | null
  status: FeedStatus
}

// Used only before the first clock arrives; afterwards the server's
// poll_seconds decides.
const FIRST_POLL_MS = 3000

// Everything the console knows from the server. It keeps no clock of its own:
// the clock shown is whatever the server last reported.
export class Feed {
  state: FeedState = { clock: null, view: null, status: "connecting" }
  private etag: string | null = null
  private listeners = new Set<() => void>()

  constructor(
    private code: string,
    private api: Api,
  ) {}

  subscribe(listener: () => void): () => void {
    this.listeners.add(listener)
    return () => void this.listeners.delete(listener)
  }

  pollMs(): number {
    const seconds = this.state.clock?.poll_seconds
    return seconds ? seconds * 1000 : FIRST_POLL_MS
  }

  async refresh(): Promise<void> {
    // The clock has its own request because a 304 on the view carries no
    // clock block, and a countdown must never go stale.
    const [clock, view] = await Promise.allSettled([this.api.clock(), this.api.view(this.code, { etag: this.etag })])
    const next: FeedState = { ...this.state }

    if (clock.status === "fulfilled") next.clock = clock.value

    if (view.status === "rejected") {
      next.status = "reconnecting"
    } else if (view.value.kind === "invalid-code") {
      next.status = "invalid-code"
    } else if (view.value.kind === "degraded") {
      next.status = "server-degraded"
    } else {
      if (view.value.kind === "ok") {
        next.view = view.value.view
        this.etag = view.value.etag
        if (clock.status === "rejected") next.clock = view.value.clock
      }
      next.status = clock.status === "rejected" && view.value.kind === "same" ? "reconnecting" : "live"
    }

    this.state = next
    this.emit()
  }

  // Send an action, then refetch straight away. Nothing is guessed locally.
  async act(action: TeamAction): Promise<ActionOutcome> {
    const outcome = await this.api.action(this.code, action)
    this.etag = null
    await this.refresh()
    return outcome
  }

  private emit() {
    for (const listener of this.listeners) listener()
  }
}
