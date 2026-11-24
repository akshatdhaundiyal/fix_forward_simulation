import { describe, expect, it } from "vitest"
import { contractState, weekKind } from "./contract"
import type { Calendar } from "./types"

const calendar: Calendar = {
  weeks: 52,
  weeks_per_quarter: 13,
  checkpoint_weeks: [13, 26, 39],
  surge: { start: 28, end: 30 },
  contract_window: { first: 14, last: 17 },
}

const b1 = (over: Partial<{ applied: boolean; awarded: boolean }> = {}) => ({
  window_open: false,
  applied: false,
  awarded: false,
  ...over,
})

describe("contractState", () => {
  it("is not yet open before the application window", () => {
    expect(contractState(b1(), 10, calendar)).toBe("not-open")
    expect(contractState(b1(), 13, calendar)).toBe("not-open")
  })

  it("is open inside the window until the team applies, then applied", () => {
    expect(contractState(b1(), 14, calendar)).toBe("open")
    expect(contractState(b1(), 17, calendar)).toBe("open")
    expect(contractState(b1({ applied: true }), 15, calendar)).toBe("applied")
  })

  it("is awarded for an awarded team at any week", () => {
    expect(contractState(b1({ applied: true, awarded: true }), 18, calendar)).toBe("awarded")
    expect(contractState(b1({ applied: true, awarded: true }), 40, calendar)).toBe("awarded")
  })

  it("is not awarded once the window has closed, for applicants and non-applicants alike", () => {
    expect(contractState(b1({ applied: true }), 18, calendar)).toBe("not-awarded")
    expect(contractState(b1(), 18, calendar)).toBe("not-awarded")
  })
})

describe("weekKind", () => {
  it("marks surge weeks, checkpoint weeks and the contract window", () => {
    expect(weekKind(28, calendar)).toContain("surge")
    expect(weekKind(30, calendar)).toContain("surge")
    expect(weekKind(31, calendar)).not.toContain("surge")
    expect(weekKind(26, calendar)).toContain("checkpoint")
    expect(weekKind(15, calendar)).toContain("contract")
    expect(weekKind(5, calendar)).toEqual([])
  })
})
