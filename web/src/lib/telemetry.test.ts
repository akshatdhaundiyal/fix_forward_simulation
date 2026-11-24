import { describe, expect, it } from "vitest"
import { errorSeries, latencySeries, ticketSeries } from "./telemetry"
import type { TelemetryPoint } from "./types"

const points: TelemetryPoint[] = [
  { day: 1, error_rate: 0.005, p99_ms: 300, tickets: { W: 0.1, M: 1, S: 20 } },
  { day: 2, error_rate: 0.006, p99_ms: 330, tickets: { W: 0.2, M: 2, S: 22 } },
]

describe("telemetry series", () => {
  it("charts error rate and latency by day", () => {
    expect(errorSeries(points)).toEqual([
      { day: 1, value: 0.005 },
      { day: 2, value: 0.006 },
    ])
    expect(latencySeries(points).map((p) => p.value)).toEqual([300, 330])
  })

  it("charts tickets as one row per day with a value per segment", () => {
    expect(ticketSeries(points)).toEqual([
      { day: 1, W: 0.1, M: 1, S: 20 },
      { day: 2, W: 0.2, M: 2, S: 22 },
    ])
  })

  it("is empty before the first day has been recorded", () => {
    expect(errorSeries([])).toEqual([])
    expect(ticketSeries([])).toEqual([])
  })
})
