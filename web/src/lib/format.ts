import type { Clock, RateKey } from "./types"

export function formatCr(value: number): string {
  return `₹${value.toFixed(1)} Cr`
}

export function countdownText(seconds: number): string {
  const whole = Math.max(0, Math.ceil(seconds))
  const m = Math.floor(whole / 60)
  const s = whole % 60
  return `${m}:${String(s).padStart(2, "0")}`
}

export interface RunState {
  label: string
  tone: "go" | "wait" | "stop"
}

export function runState(clock: Clock): RunState {
  if (clock.finished) return { label: "Game finished", tone: "stop" }
  if (clock.running) return { label: "Running", tone: "go" }
  switch (clock.reason) {
    case "start":
      return { label: "Waiting to start", tone: "wait" }
    case "checkpoint":
      return { label: "Checkpoint break", tone: "wait" }
    case "restart":
      return { label: "Waiting for the host to resume", tone: "wait" }
    default:
      return { label: "Paused by the host", tone: "wait" }
  }
}

const RATE_FOR_METRIC: Record<string, RateKey> = {
  leads: "leads",
  signup: "signup",
  activation: "activation",
  paid: "paid",
  retention: "churn",
}

// An incident names the funnel stage it hurts; the chart shows churn for retention.
export function metricToRate(metric: string): RateKey {
  return RATE_FOR_METRIC[metric] ?? "activation"
}

export const RATE_LABELS: Record<RateKey, string> = {
  leads: "Leads",
  signup: "Sign-up rate",
  activation: "Activation rate",
  paid: "Paid conversion",
  churn: "Weekly churn",
}

export const STAGE_LABELS: Record<string, string> = {
  leads: "Leads",
  signup: "Sign-up",
  activation: "Activation",
  paid: "Paid conversion",
  retention: "Retention",
  arr_per_account: "Revenue per account",
  contract: "Bespoke contract",
}

const CAUSES: Record<string, string> = {
  external_load: "External load",
  organic_growth: "Organic traffic growth",
  own_release: "Our own release",
  vendor: "Vendor degradation",
  pricing_change: "Pricing or marketing change",
}

export function causeLabel(cause: string): string {
  if (CAUSES[cause]) return CAUSES[cause]
  const words = cause.replace(/_/g, " ")
  return words.charAt(0).toUpperCase() + words.slice(1)
}

export function percent(rate: number, digits = 1): string {
  return `${(rate * 100).toFixed(digits)}%`
}
