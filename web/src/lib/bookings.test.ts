import { describe, expect, it } from "vitest"
import { bookStakeholder, fetchBookings } from "./api"
import { placesText, positionText, roleState, type RoleBooking } from "./bookings"

const role = (over: Partial<RoleBooking> = {}): RoleBooking => ({
  role: "cto",
  title: "CTO",
  places_left: 3,
  mine: null,
  ...over,
})

describe("roleState", () => {
  it("is full, with no way to book, when no places are left", () => {
    expect(roleState(role({ places_left: 0 }))).toBe("full")
  })

  it("shows the booking, not an open slot, for a stakeholder the team already booked", () => {
    expect(roleState(role({ mine: { id: 4, position: 2, done: false } }))).toBe("booked")
    expect(roleState(role({ places_left: 0, mine: { id: 4, position: 2, done: false } }))).toBe("booked")
  })

  it("is met once the meeting is marked done, and open otherwise", () => {
    expect(roleState(role({ mine: { id: 4, position: null, done: true } }))).toBe("met")
    expect(roleState(role())).toBe("open")
  })
})

describe("text helpers", () => {
  it("says how many places are left and where the team stands in the queue", () => {
    expect(placesText(role({ places_left: 0 }), 5)).toBe("All places taken")
    expect(placesText(role({ places_left: 3 }), 5)).toBe("3 of 5 places left")
    expect(positionText(1)).toBe("You are next")
    expect(positionText(3)).toBe("2 ahead of you")
    expect(positionText(null)).toBe("Met")
  })
})

function stub(status: number, body: unknown) {
  const calls: { url: string; init?: RequestInit }[] = []
  const fetchFn = (async (url: string, init?: RequestInit) => {
    calls.push({ url, init })
    return new Response(JSON.stringify(body), { status })
  }) as unknown as typeof fetch
  return { calls, fetchFn }
}

describe("bookings api", () => {
  it("reads the team's bookings and posts a booking with relative URLs", async () => {
    const view = { quarter: 1, per_quarter: 5, roles: [] }
    const read = stub(200, view)
    expect(await fetchBookings("AB12CD", read.fetchFn)).toEqual(view)
    expect(read.calls[0].url).toBe("api/team/AB12CD/bookings")
    const post = stub(200, { ok: true, booking: 7 })
    expect(await bookStakeholder("AB12CD", "cto", post.fetchFn)).toEqual({ ok: true })
    expect(post.calls[0].url).toBe("api/team/AB12CD/bookings")
    expect(JSON.parse(post.calls[0].init?.body as string)).toEqual({ role: "cto" })
  })

  it("passes the server's refusal through so the console can show it", async () => {
    const { fetchFn } = stub(400, { ok: false, error: "all places with this stakeholder are taken this quarter" })
    expect(await bookStakeholder("AB12CD", "cto", fetchFn)).toEqual({
      ok: false,
      error: "all places with this stakeholder are taken this quarter",
    })
  })

  it("reports an unreachable server as a failed booking, not an exception", async () => {
    const fetchFn = (async () => {
      throw new Error("offline")
    }) as unknown as typeof fetch
    const result = await bookStakeholder("AB12CD", "cto", fetchFn)
    expect(result.ok).toBe(false)
  })
})
