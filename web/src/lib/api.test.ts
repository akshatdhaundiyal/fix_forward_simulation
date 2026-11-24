import { describe, expect, it } from "vitest"
import { createApi } from "./api"

type Call = { url: string; init?: RequestInit }

function stub(respond: (call: Call) => Response | Promise<Response>) {
  const calls: Call[] = []
  const fetchFn = (async (url: string, init?: RequestInit) => {
    const call = { url, init }
    calls.push(call)
    return respond(call)
  }) as unknown as typeof fetch
  return { api: createApi(fetchFn), calls }
}

const json = (body: unknown, status = 200, headers: Record<string, string> = {}) =>
  new Response(JSON.stringify(body), { status, headers })

describe("createApi.view", () => {
  it("maps 304, 404 and 503 to typed results and other failures to a rejection", async () => {
    for (const [status, kind] of [
      [304, "same"],
      [404, "invalid-code"],
      [503, "degraded"],
    ] as const) {
      const { api } = stub(() => new Response(null, { status }))
      expect(await api.view("ABC123")).toEqual({ kind })
    }
    const { api } = stub(() => new Response(null, { status: 500 }))
    await expect(api.view("ABC123")).rejects.toThrow()
  })

  it("returns the view, the clock and the ETag on 200", async () => {
    const { api } = stub(() => json({ clock: { day: 3 }, view: { team: 1 } }, 200, { ETag: '"v1"' }))
    expect(await api.view("ABC123")).toEqual({
      kind: "ok",
      clock: { day: 3 },
      view: { team: 1 },
      etag: '"v1"',
    })
  })

  it("sends If-None-Match and builds the days and slices query", async () => {
    const { api, calls } = stub(() => new Response(null, { status: 304 }))
    await api.view("ABC123", { etag: '"v1"', days: 91, slices: true })
    expect(calls[0].url).toBe("api/team/ABC123/view?days=91&slices=1")
    expect((calls[0].init?.headers as Record<string, string>)["If-None-Match"]).toBe('"v1"')
    await api.view("ABC123")
    expect(calls[1].url).toBe("api/team/ABC123/view")
  })

  it("gives every request a timeout so a stalled connection fails instead of hanging", async () => {
    const { api, calls } = stub(() => json({ clock: {}, view: {} }))
    await api.view("ABC123")
    await api.view("ABC123", { slices: true })
    await api.clock()
    await api.action("ABC123", { type: "apply_b1" })
    for (const c of calls) expect(c.init?.signal).toBeInstanceOf(AbortSignal)
  })

  it("keeps every URL relative", async () => {
    const { api, calls } = stub(() => json({ ok: true, clock: {}, view: {} }))
    await api.clock()
    await api.view("ABC123", { days: 5 })
    await api.action("ABC123", { type: "apply_b1" })
    for (const c of calls) expect(c.url).toMatch(/^api\//)
  })
})

describe("createApi.action", () => {
  it("posts the action and reports success", async () => {
    const { api, calls } = stub(() => json({ ok: true }))
    expect(await api.action("ABC123", { type: "set_quality", mode: "high" })).toEqual({ ok: true })
    expect(calls[0].init?.method).toBe("POST")
    expect(JSON.parse(calls[0].init?.body as string)).toEqual({ action: { type: "set_quality", mode: "high" } })
  })

  it("returns the server's own message when it rejects an action", async () => {
    const { api } = stub(() => json({ ok: false, error: "card is locked" }, 400))
    expect(await api.action("ABC123", { type: "queue_add", card: "B3" })).toEqual({
      ok: false,
      error: "card is locked",
    })
  })

  it("explains a 503, a network failure and an unreadable body", async () => {
    const down = stub(() => new Response(null, { status: 503 }))
    expect((await down.api.action("ABC123", { type: "apply_b1" })).ok).toBe(false)

    const offline = createApi((async () => {
      throw new Error("offline")
    }) as unknown as typeof fetch)
    const result = await offline.action("ABC123", { type: "apply_b1" })
    expect(result).toMatchObject({ ok: false })

    const junk = stub(() => new Response("not json", { status: 500 }))
    expect(await junk.api.action("ABC123", { type: "apply_b1" })).toMatchObject({ ok: false })
  })
})
