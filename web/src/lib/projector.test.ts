import { describe, expect, it } from "vitest"
import { rankMoves, sortRows, type ProjectorRow } from "./projector"

const row = (team: number, arr: number, over: Partial<ProjectorRow> = {}): ProjectorRow => ({
  team,
  name: `Team ${team}`,
  arr,
  trust_avg: 60,
  rank: 0,
  ...over,
})

describe("sortRows", () => {
  it("ranks by ARR before the reveal and keeps team order on a tie", () => {
    const rows = sortRows([row(3, 20), row(1, 25), row(2, 25)], false)
    expect(rows.map((r) => r.team)).toEqual([1, 2, 3])
    expect(rows.map((r) => r.rank)).toEqual([1, 2, 3])
  })

  it("ranks by valuation after the reveal", () => {
    const rows = sortRows(
      [row(1, 40, { nev: 100, uod: 50, penalty: 0 }), row(2, 30, { nev: 140, uod: 0, penalty: 0 })],
      true,
    )
    expect(rows.map((r) => r.team)).toEqual([2, 1])
  })

  it("does not mutate its input", () => {
    const input = [row(2, 10), row(1, 20)]
    sortRows(input, false)
    expect(input.map((r) => r.team)).toEqual([2, 1])
  })
})

describe("rankMoves", () => {
  it("is empty on the first poll", () => {
    expect(rankMoves(null, sortRows([row(1, 25)], false))).toEqual({})
  })

  it("reports places gained and lost between polls", () => {
    const before = sortRows([row(1, 25), row(2, 24), row(3, 20)], false)
    const after = sortRows([row(1, 25), row(2, 21), row(3, 22)], false)
    expect(rankMoves(before, after)).toEqual({ 3: 1, 2: -1 })
  })

  it("ignores a team that was not in the previous poll", () => {
    const before = sortRows([row(1, 25)], false)
    const after = sortRows([row(1, 25), row(2, 24)], false)
    expect(rankMoves(before, after)).toEqual({})
  })
})
