// Shapes of what the server sends a team. They mirror engine.team_view and
// clock.status. Nothing here names a hidden field: a team's browser only ever
// receives what team_view builds field by field.

export type SegmentId = "W" | "M" | "S"
export const SEGMENTS: SegmentId[] = ["W", "M", "S"]
export const SEGMENT_NAMES: Record<SegmentId, string> = {
  W: "Whales",
  M: "Mid-Market",
  S: "Self-Serve",
}

export type QualityMode = "low" | "medium" | "high"

export interface Clock {
  day: number
  week: number
  running: boolean
  paused: boolean
  reason: string | null
  speed: number
  seconds_per_day: number
  seconds_to_next_tick: number | null
  countdown_remaining: number | null
  warning: boolean
  hold: boolean
  finished: boolean
  next_checkpoint_week: number | null
  poll_seconds: number
  projector_poll_seconds: number
}

export type CardStatus =
  | "available"
  | "queued"
  | "shipped"
  | "done_this_quarter"
  | "apply"
  | "awarded"

export interface Card {
  id: string
  name: string
  cost: number
  seg: SegmentId | null
  stage: string | null
  pitch_arr: number
  trust_effect: Partial<Record<SegmentId, number>>
  status: CardStatus
  bespoke: boolean
}

export interface QueueItem {
  id: number
  kind: "card" | "report" | "fix" | "patch"
  label: string
  cost: number
  progress: number
  seg: SegmentId | null | undefined
  picked: string | null | undefined
  incident: number | null | undefined
}

export interface Incident {
  id: number
  symptom: string
  metric: string
  options: string[]
  since_day: number
  patched: boolean
}

export interface Report {
  seg: SegmentId
  day: number
  utility: Record<string, number>
  alerts: string[]
}

export interface Release {
  card: string
  day: number
  name: string
}

export type RateKey = "leads" | "signup" | "activation" | "paid" | "churn"

export interface FunnelPoint {
  day: number
  arr: number
  accounts: number
  new: number
  lost: number
  rates: Record<RateKey, number>
  // Present only when slices were requested. Keys look like "platform:web".
  slices?: Record<string, Record<RateKey, number>>
}

export interface TelemetryPoint {
  day: number
  error_rate: number
  p99_ms: number
  tickets: Record<SegmentId, number>
}

export interface Calendar {
  weeks: number
  weeks_per_quarter: number
  days_per_week: number
  checkpoint_weeks: number[]
  surge: { start: number; end: number }
  contract_window: { first: number; last: number }
}

export interface TeamView {
  team: number
  day: number
  week: number
  quarter: number
  tiles: {
    arr: number
    trust: Record<SegmentId, number>
    capacity_bu_week: number
    open_incidents: number
  }
  quality: QualityMode
  outage: boolean
  queue: QueueItem[]
  cards: Card[]
  incidents: Incident[]
  reports: Report[]
  b1: { window_open: boolean; applied: boolean; awarded: boolean }
  releases: Release[]
  funnel: Record<SegmentId, FunnelPoint[]>
  telemetry: TelemetryPoint[]
}

// Team actions the server accepts (config.ACTION_SPECS, caller "team").
export type TeamAction =
  | { type: "queue_add"; card: string }
  | { type: "queue_add"; report: SegmentId }
  | { type: "queue_remove"; item: number }
  | { type: "queue_reorder"; item: number; position: number }
  | { type: "set_quality"; mode: QualityMode }
  | { type: "rollback"; card: string }
  | { type: "targeted_fix"; incident: number; cause: string }
  | { type: "patch"; incident: number }
  | { type: "apply_b1" }
