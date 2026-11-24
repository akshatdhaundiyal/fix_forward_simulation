import { describe, expect, it } from "vitest"
import { createStakeholderApi } from "./stakeholder-api"
import { declineTicks, queueFor, sortByBand, type Board, type BoardBooking, type BoardTeam } from "./stakeholder"

type Call = { url: string; init?: RequestInit }

function stub(respond: (call: Call) => Response) {
  const calls: Call[] = []
  const fetchFn = (async (url: string, init?: RequestInit) => {
    const call = { url, init }
    calls.push(call)
    return respond(call)
  }) as unknown as typeof fetch
  return { calls, api: createStakeholderApi("pw", fetchFn) }
}

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })
const header = (c: Call) => (c.init?.headers as Record<string, string>)["X-Stakeholder-Password"]
const body = (c: Call) => JSON.parse(c.init?.body as string)

describe("createStakeholderApi", () => {
  it("sends the password on every call and keeps URLs relative", async () => {
    const { api, calls } = stub(() => json({ ok: true }))
    await api.board()
    await api.done(3)
    await api.decline(2, 3)
    expect(calls.map((c) => c.url)).toEqual([
      "api/stakeholder/board",
      "api/stakeholder/done",
      "api/stakeholder/decline",
    ])
    for (const c of calls) expect(header(c)).toBe("pw")
  })

  it("marks a 401 as unauthorized, on any route, so the screen returns to the gate", async () => {
    const { api } = stub(() => json({ error: "unauthorized" }, 401))
    const expected = { ok: false, unauthorized: true, error: "Wrong stakeholder password." }
    expect(await api.board()).toEqual(expected)
    expect(await api.done(1)).toEqual(expected)
    expect(await api.decline(1, 3)).toEqual(expected)
  })

  it("marking a meeting done sends the booking id", async () => {
    const { api, calls } = stub(() => json({ ok: true }))
    await api.done(12)
    expect(body(calls[0])).toEqual({ booking: 12 })
  })

  it("the decline form sends the team and the tick count, not the individual ticks", async () => {
    const { api, calls } = stub(() => json({ ok: true }))
    await api.decline(4, declineTicks([true, false, true]))
    expect(body(calls[0])).toEqual({ team: 4, ticks: 2 })
  })

  it("shows the server's refusal for a second decline entry", async () => {
    const { api } = stub(() => json({ ok: false, error: "a result is already entered for this team" }, 400))
    expect(await api.decline(4, 3)).toEqual({
      ok: false,
      unauthorized: false,
      error: "a result is already entered for this team",
    })
  })

  it("reports an unreachable server as a failure, not an exception", async () => {
    const api = createStakeholderApi("pw", (async () => {
      throw new Error("offline")
    }) as unknown as typeof fetch)
    expect((await api.board()).ok).toBe(false)
  })
})

const team = (n: number, band: BoardTeam["band"]): BoardTeam => ({
  team: n,
  name: `Team ${n}`,
  band,
  cto_line: null,
  whale: { facts: { data_isolation_shipped: false, outage_hit: false, applied: false }, lines: [] },
  declined: false,
})

describe("board helpers", () => {
  it("lists a stakeholder's unmet bookings in booking order", () => {
    const b = (id: number, role: BoardBooking["role"], done = false): BoardBooking => ({
      id,
      team: id,
      name: `Team ${id}`,
      role,
      quarter: 1,
      done,
    })
    const board = { bookings: [b(9, "cto"), b(4, "cto"), b(5, "vp_sales"), b(6, "cto", true)] } as Board
    expect(queueFor(board, "cto").map((x) => x.id)).toEqual([4, 9])
  })

  it("puts red teams first, then amber, then green, by team number within a band", () => {
    const sorted = sortByBand([team(1, "green"), team(2, "red"), team(3, "amber"), team(4, "red")])
    expect(sorted.map((t) => t.team)).toEqual([2, 4, 3, 1])
  })
})
