import type { SegmentId, TelemetryPoint } from "./types"

export interface DayValue {
  day: number
  value: number
}

export type TicketRow = { day: number } & Record<SegmentId, number>

export const errorSeries = (points: TelemetryPoint[]): DayValue[] =>
  points.map((p) => ({ day: p.day, value: p.error_rate }))

export const latencySeries = (points: TelemetryPoint[]): DayValue[] =>
  points.map((p) => ({ day: p.day, value: p.p99_ms }))

export const ticketSeries = (points: TelemetryPoint[]): TicketRow[] =>
  points.map((p) => ({ day: p.day, W: p.tickets.W, M: p.tickets.M, S: p.tickets.S }))
