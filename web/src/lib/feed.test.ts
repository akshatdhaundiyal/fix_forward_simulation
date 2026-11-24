import { describe, expect, it } from "vitest"
import { Feed } from "./feed"
import type { Api, ActionOutcome, ViewResult } from "./api"
import type { Clock, TeamView } from "./types"

const clock = (over: Partial<Clock> = {}): Clock => ({
  day: 0,
  week: 1,
  running: false,
  paused: true,
  reason: "start",
  speed: 1,
  seconds_per_day: 1,
  seconds_to_next_tick: null,
  countdown_remaining: null,
  warning: false,
  hold: false,
  finished: false,
  next_checkpoint_week: 13,
  poll_seconds: 3,
  projector_poll_seconds: 2,
  ...over,
})

const view = (over: Partial<TeamView> = {}): TeamView =>
  ({ team: 1, day: 0, week: 1, quarter: 1, quality: "medium", ...over }) as TeamView

function fakeApi(over: Partial<Api> = {}): Api & { calls: string[] } {
  const calls: string[] = []
  const api: Api = {
    clock: async () => {
      calls.push("clock")
      return clock()
    },
    view: async () => {
      calls.push("view")
      return { kind: "ok", clock: clock(), view: view(), etag: '"e1"' } satisfies ViewResult
    },
    action: async () => ({ ok: true }) satisfies ActionOutcome,
    ...over,
  }
  return Object.assign(api, { calls })
}

describe("Feed", () => {
  it("loads clock and view and goes live", async () => {
    const feed = new Feed("ABC123", fakeApi())
    expect(feed.state.status).toBe("connecting")
    await feed.refresh()
    expect(feed.state.status).toBe("live")
    expect(feed.state.view?.team).toBe(1)
    expect(feed.state.clock?.poll_seconds).toBe(3)
  })

  it("keeps the previous view on a 304 and still updates the clock", async () => {
    let day = 0
    const api = fakeApi({
      clock: async () => clock({ day: ++day }),
      view: async (_c, opts) =>
        opts?.etag ? { kind: "same" } : { kind: "ok", clock: clock(), view: view({ team: 7 }), etag: '"e1"' },
    })
    const feed = new Feed("ABC123", api)
    await feed.refresh()
    await feed.refresh()
    expect(feed.state.view?.team).toBe(7)
    expect(feed.state.clock?.day).toBe(2)
    expect(feed.state.status).toBe("live")
  })

  it("marks reconnecting on a network failure and keeps the last view, then recovers", async () => {
    let fail = false
    const api = fakeApi({
      clock: async () => {
        if (fail) throw new Error("offline")
        return clock()
      },
      view: async () => {
        if (fail) throw new Error("offline")
        return { kind: "ok", clock: clock(), view: view({ team: 3 }), etag: '"e"' }
      },
    })
    const feed = new Feed("ABC123", api)
    await feed.refresh()
    fail = true
    await feed.refresh()
    expect(feed.state.status).toBe("reconnecting")
    expect(feed.state.view?.team).toBe(3)
    fail = false
    await feed.refresh()
    expect(feed.state.status).toBe("live")
  })

  it("reports a server-paused status on 503 and invalid-code on 404", async () => {
    const feed = new Feed("ABC123", fakeApi({ view: async () => ({ kind: "degraded" }) }))
    await feed.refresh()
    expect(feed.state.status).toBe("server-degraded")
    const bad = new Feed("NOPE", fakeApi({ view: async () => ({ kind: "invalid-code" }) }))
    await bad.refresh()
    expect(bad.state.status).toBe("invalid-code")
  })

  it("polls at the interval the clock block reports and changes with it", async () => {
    let poll = 3
    const feed = new Feed("ABC123", fakeApi({ clock: async () => clock({ poll_seconds: poll }) }))
    expect(feed.pollMs()).toBe(3000)
    await feed.refresh()
    expect(feed.pollMs()).toBe(3000)
    poll = 5
    await feed.refresh()
    expect(feed.pollMs()).toBe(5000)
  })

  it("returns the server's rejection text and refetches after any action", async () => {
    const api = fakeApi({ action: async () => ({ ok: false, error: "card is locked" }) })
    const feed = new Feed("ABC123", api)
    await feed.refresh()
    const before = api.calls.filter((c) => c === "view").length
    const outcome = await feed.act({ type: "queue_add", card: "B3" })
    expect(outcome).toEqual({ ok: false, error: "card is locked" })
    expect(api.calls.filter((c) => c === "view").length).toBe(before + 1)
  })

  it("does not change the stored view until the refetch completes", async () => {
    let release!: () => void
    const gate = new Promise<void>((r) => (release = r))
    let serverTeam = 1
    const api = fakeApi({
      view: async () => {
        if (serverTeam === 2) await gate
        return { kind: "ok", clock: clock(), view: view({ team: serverTeam }), etag: `"e${serverTeam}"` }
      },
      action: async () => {
        serverTeam = 2
        return { ok: true }
      },
    })
    const feed = new Feed("ABC123", api)
    await feed.refresh()
    const pending = feed.act({ type: "set_quality", mode: "high" })
    await Promise.resolve()
    await Promise.resolve()
    expect(feed.state.view?.team).toBe(1)
    release()
    await pending
    expect(feed.state.view?.team).toBe(2)
  })

  it("notifies subscribers and stops after unsubscribe", async () => {
    const feed = new Feed("ABC123", fakeApi())
    let n = 0
    const off = feed.subscribe(() => n++)
    await feed.refresh()
    expect(n).toBeGreaterThan(0)
    off()
    const seen = n
    await feed.refresh()
    expect(n).toBe(seen)
  })
})
