import { describe, expect, it } from "vitest"
import { causeLabel, countdownText, formatCr, metricToRate, runState } from "./format"
import type { Clock } from "./types"

const clock = (over: Partial<Clock> = {}): Clock => ({
  day: 10,
  week: 2,
  running: true,
  paused: false,
  reason: null,
  speed: 1,
  seconds_per_day: 1,
  seconds_to_next_tick: 1,
  countdown_remaining: null,
  warning: false,
  hold: false,
  finished: false,
  next_checkpoint_week: 13,
  poll_seconds: 3,
  projector_poll_seconds: 2,
  ...over,
})

describe("format", () => {
  it("formats ARR in crore with one decimal", () => {
    expect(formatCr(25)).toBe("₹25.0 Cr")
    expect(formatCr(12.349)).toBe("₹12.3 Cr")
  })

  it("formats a countdown as minutes and seconds, rounding up", () => {
    expect(countdownText(420)).toBe("7:00")
    expect(countdownText(59.2)).toBe("1:00")
    expect(countdownText(0)).toBe("0:00")
  })

  it("names the run state from the clock block", () => {
    expect(runState(clock()).label).toBe("Running")
    expect(runState(clock({ running: false, paused: true, reason: "checkpoint" })).label).toBe("Checkpoint break")
    expect(runState(clock({ running: false, paused: true, reason: "start" })).label).toBe("Waiting to start")
    expect(runState(clock({ running: false, paused: true, reason: "operator" })).label).toBe("Paused by the host")
    expect(runState(clock({ running: false, paused: true, finished: true, reason: "finished" })).label).toBe(
      "Game finished",
    )
  })

  it("maps an incident's metric to the funnel rate that shows it", () => {
    expect(metricToRate("retention")).toBe("churn")
    expect(metricToRate("activation")).toBe("activation")
    expect(metricToRate("paid")).toBe("paid")
  })

  it("labels every candidate cause the server can send", () => {
    for (const c of ["external_load", "organic_growth", "own_release", "vendor", "pricing_change"]) {
      expect(causeLabel(c)).not.toBe(c)
    }
    expect(causeLabel("something_new")).toBe("Something new")
  })
})
