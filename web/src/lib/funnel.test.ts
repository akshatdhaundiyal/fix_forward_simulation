import { describe, expect, it } from "vitest"
import { SLICE_GROUPS, buildSeries, releaseMarkers } from "./funnel"
import type { FunnelPoint, Release } from "./types"

const point = (day: number, over: Partial<FunnelPoint> = {}): FunnelPoint => ({
  day,
  arr: 10 + day,
  accounts: 20,
  new: 1,
  lost: 1,
  rates: { leads: 2, signup: 0.5, activation: 0.5, paid: 0.1, churn: 0.0025 },
  slices: {
    "platform:web": { leads: 2, signup: 0.5, activation: 0.6, paid: 0.1, churn: 0.0025 },
    "platform:mobile": { leads: 2, signup: 0.5, activation: 0.2, paid: 0.1, churn: 0.0025 },
  },
  ...over,
})

describe("buildSeries", () => {
  const points = [point(1), point(2), point(3)]

  it("charts a segment rate over time when no slice is chosen", () => {
    const s = buildSeries(points, "activation", null)
    expect(s.data).toEqual([
      { day: 1, value: 0.5 },
      { day: 2, value: 0.5 },
      { day: 3, value: 0.5 },
    ])
    expect(s.empty).toBe(false)
  })

  it("switches to the matching slice when one is chosen", () => {
    const s = buildSeries(points, "activation", "platform:mobile")
    expect(s.data.map((d) => d.value)).toEqual([0.2, 0.2, 0.2])
  })

  it("is empty, not flat, when the slice has no data", () => {
    expect(buildSeries(points, "activation", "cohort:new").empty).toBe(true)
    expect(buildSeries([point(1, { slices: undefined })], "activation", "platform:web").empty).toBe(true)
  })

  it("charts ARR for a segment and has no slice view of ARR", () => {
    expect(buildSeries(points, "arr", null).data.map((d) => d.value)).toEqual([11, 12, 13])
    expect(buildSeries(points, "arr", "platform:web").empty).toBe(true)
  })
})

describe("releaseMarkers", () => {
  const releases: Release[] = [
    { card: "A2", day: 19, name: "Self-serve onboarding revamp" },
    { card: "A4", day: 40, name: "Enterprise SSO & audit logs" },
  ]

  it("keeps only releases inside the charted days", () => {
    expect(releaseMarkers(releases, 30, 60).map((r) => r.card)).toEqual(["A4"])
    expect(releaseMarkers(releases, 1, 18)).toEqual([])
  })

  it("keeps a release on the first or last charted day", () => {
    expect(releaseMarkers(releases, 19, 40).map((r) => r.card)).toEqual(["A2", "A4"])
  })
})

describe("slice groups", () => {
  it("cover platform, plan and cohort", () => {
    expect(SLICE_GROUPS.map((g) => g.label)).toEqual(["Platform", "Plan", "Cohort"])
    expect(SLICE_GROUPS.flatMap((g) => g.options.map((o) => o.value))).toContain("cohort:new")
  })
})
