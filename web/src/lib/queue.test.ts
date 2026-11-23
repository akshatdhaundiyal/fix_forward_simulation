import { describe, expect, it } from "vitest"
import { backlogBu, latestUtility, reorderPosition, rollbackCandidates } from "./queue"
import type { Card, QueueItem, Report, TeamView } from "./types"

const item = (id: number, over: Partial<QueueItem> = {}): QueueItem => ({
  id,
  kind: "card",
  label: `Item ${id}`,
  cost: 20,
  progress: 0,
  seg: "M",
  picked: null,
  incident: null,
  ...over,
})

describe("reorderPosition", () => {
  const queue = [item(10), item(11), item(12), item(13)]

  it("moving an item down onto another sends that item's index", () => {
    expect(reorderPosition(queue, 10, 12)).toEqual({ item: 10, position: 2 })
  })

  it("moving an item to the front sends position 0", () => {
    expect(reorderPosition(queue, 13, 10)).toEqual({ item: 13, position: 0 })
  })

  it("dropping an item on itself, or on something unknown, sends nothing", () => {
    expect(reorderPosition(queue, 11, 11)).toBeNull()
    expect(reorderPosition(queue, 11, 99)).toBeNull()
    expect(reorderPosition(queue, 99, 11)).toBeNull()
  })
})

describe("backlogBu", () => {
  it("sums what is left to build", () => {
    expect(backlogBu([item(1, { cost: 20, progress: 5 }), item(2, { cost: 10, progress: 0 })])).toBe(25)
    expect(backlogBu([])).toBe(0)
  })
})

describe("latestUtility", () => {
  const reports: Report[] = [
    { seg: "M", day: 7, utility: { A1: 15, A3: 76 }, alerts: [] },
    { seg: "S", day: 14, utility: { A2: 80 }, alerts: [] },
    { seg: "M", day: 21, utility: { A1: 18 }, alerts: [] },
  ]
  const card = (id: string, seg: Card["seg"]): Card => ({ id, seg }) as Card

  it("uses the newest report for the card's own segment that covers the card", () => {
    expect(latestUtility(reports, card("A1", "M"))).toEqual({ value: 18, day: 21 })
    expect(latestUtility(reports, card("A3", "M"))).toEqual({ value: 76, day: 7 })
  })

  it("is null when no report covers the card or the card has no segment", () => {
    expect(latestUtility(reports, card("A5", "S"))).toBeNull()
    expect(latestUtility(reports, card("P1", null))).toBeNull()
  })
})

describe("rollbackCandidates", () => {
  it("lists shipped cards that are not bespoke contracts and have a funnel stage", () => {
    const view = {
      cards: [
        { id: "A1", status: "shipped", bespoke: false, stage: "paid" },
        { id: "B1", status: "shipped", bespoke: true, stage: "contract" },
        { id: "D4", status: "shipped", bespoke: false, stage: null },
        { id: "A2", status: "available", bespoke: false, stage: "activation" },
      ],
    } as unknown as TeamView
    expect(rollbackCandidates(view).map((c) => c.id)).toEqual(["A1"])
  })
})
