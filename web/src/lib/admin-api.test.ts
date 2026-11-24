import { describe, expect, it } from "vitest"
import { createAdminApi } from "./admin-api"

type Call = { url: string; init?: RequestInit }

function stub(respond: (call: Call) => Response) {
  const calls: Call[] = []
  const fetchFn = (async (url: string, init?: RequestInit) => {
    const call = { url, init }
    calls.push(call)
    return respond(call)
  }) as unknown as typeof fetch
  return { calls, api: createAdminApi("pw", fetchFn) }
}

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })
const header = (c: Call) => (c.init?.headers as Record<string, string>)["X-Admin-Password"]
const body = (c: Call) => JSON.parse(c.init?.body as string)

describe("createAdminApi", () => {
  it("sends the password on every call and keeps URLs relative", async () => {
    const { api, calls } = stub(() => json({ ok: true }))
    await api.status()
    await api.snapshots()
    await api.clock("pause")
    await api.reveal()
    expect(calls.map((c) => c.url)).toEqual([
      "api/admin/status",
      "api/admin/snapshots",
      "api/admin/clock",
      "api/admin/reveal",
    ])
    for (const c of calls) expect(header(c)).toBe("pw")
  })

  it("marks a 401 as unauthorized so the screen can return to the gate", async () => {
    const { api } = stub(() => json({ error: "unauthorized" }, 401))
    expect(await api.status()).toEqual({ ok: false, unauthorized: true, error: "Wrong admin password." })
  })

  it("posts each clock operation with its value", async () => {
    const { api, calls } = stub(() => json({ ok: true }))
    await api.clock("speed", 4)
    await api.clock("resume")
    expect(body(calls[0])).toEqual({ op: "speed", value: 4 })
    expect(body(calls[1])).toEqual({ op: "resume" })
  })

  it("returns the server's message when it refuses an operation", async () => {
    const { api } = stub(() => json({ ok: false, error: "not possible in the current clock state" }, 400))
    expect(await api.clock("pause")).toEqual({
      ok: false,
      unauthorized: false,
      error: "not possible in the current clock state",
    })
  })

  it("sends an incident to one team or to all", async () => {
    const { api, calls } = stub(() => json({ ok: true }))
    await api.incident("all", 1, "trigger")
    await api.incident(3, 2, "cancel")
    expect(body(calls[0])).toEqual({ team: "all", incident: 1, op: "trigger" })
    expect(body(calls[1])).toEqual({ team: 3, incident: 2, op: "cancel" })
  })

  it("will not send an edit without a reason", async () => {
    const { api, calls } = stub(() => json({ ok: true }))
    const result = await api.edit(1, "seg.W.trust", 50, "   ")
    expect(result).toMatchObject({ ok: false })
    expect(calls).toHaveLength(0)
  })

  it("sends an edit with its reason, and a restore with its snapshot id", async () => {
    const { api, calls } = stub(() => json({ ok: true }))
    await api.edit(2, "seg.W.trust", 50, "fix a typo")
    await api.restore("snap-5-d3")
    expect(body(calls[0])).toEqual({ team: 2, path: "seg.W.trust", value: 50, reason: "fix a typo" })
    expect(body(calls[1])).toEqual({ snapshot: "snap-5-d3" })
  })

  it("reports a network failure as an error, not a rejection", async () => {
    const api = createAdminApi("pw", (async () => {
      throw new Error("offline")
    }) as unknown as typeof fetch)
    expect(await api.status()).toMatchObject({ ok: false, unauthorized: false })
  })
})
