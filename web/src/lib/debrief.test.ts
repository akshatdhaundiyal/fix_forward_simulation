import { describe, expect, it } from "vitest"
import { bandAt, fetchDebriefWith, roleLabel, teamTitle, weeklyRows, type DebriefData, type DebriefTeam } from "./debrief"

const point = (week: number, debt: number) => ({
  week,
  debt,
  error_rate: 0.01 * week,
  band: debt <= 15 ? ("green" as const) : debt <= 30 ? ("amber" as const) : ("red" as const),
  arr: 20,
})

const team = (n: number, roles: string[], weeks: number[], debt = 10): DebriefTeam => ({
  team: n,
  name: `Team ${n}`,
  roles,
  series: weeks.map((w) => point(w, debt)),
  final: { arr: 20, nev: 50, debt },
})

const data = (teams: DebriefTeam[]): DebriefData => ({ weeks: 4, band_limits: [15, 30], teams, gains: [] })

describe("weeklyRows", () => {
  it("makes one row per week with a column per team", () => {
    const rows = weeklyRows(data([team(1, ["winner"], [1, 2, 3, 4]), team(3, ["biggest_collapse"], [1, 2, 3, 4], 40)]), (p) => p.debt)
    expect(rows).toHaveLength(4)
    expect(rows[0]).toEqual({ week: 1, t1: 10, t3: 40 })
  })

  it("leaves a gap, not a zero, for a week a team has no record for", () => {
    const rows = weeklyRows(data([team(2, ["winner"], [3, 4])]), (p) => p.debt)
    expect(rows[0].t2).toBeUndefined()
    expect(rows[2].t2).toBe(10)
  })
})

describe("labels", () => {
  it("names the roles in the MC's words and joins two roles on one team", () => {
    expect(roleLabel("week26_leader")).toBe("Week-26 leader")
    expect(teamTitle(team(1, ["week26_leader", "biggest_collapse"], []))).toBe(
      "Team 1: Week-26 leader and Biggest collapse",
    )
  })

  it("reads the band for a week, or nothing when there is no record", () => {
    const t = team(1, ["winner"], [1, 2], 20)
    expect(bandAt(t, 2)).toBe("amber")
    expect(bandAt(t, 3)).toBeNull()
  })
})

describe("fetchDebriefWith", () => {
  const stub = (status: number, body: unknown) =>
    (async () => new Response(JSON.stringify(body), { status })) as unknown as typeof fetch

  it("is null before the reveal and the data after it", async () => {
    expect(await fetchDebriefWith(stub(403, { error: "the debrief opens at the final reveal" }))).toBeNull()
    const d = data([team(1, ["winner"], [1])])
    expect(await fetchDebriefWith(stub(200, d))).toEqual(d)
  })

  it("throws on any other failure so the caller retries", async () => {
    await expect(fetchDebriefWith(stub(500, {}))).rejects.toThrow()
  })
})
