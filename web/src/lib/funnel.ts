import type { FunnelPoint, RateKey, Release } from "./types"

export type Metric = RateKey | "arr"

export const METRIC_OPTIONS: { value: Metric; label: string }[] = [
  { value: "leads", label: "Leads" },
  { value: "signup", label: "Sign-up" },
  { value: "activation", label: "Activation" },
  { value: "paid", label: "Paid conversion" },
  { value: "churn", label: "Churn" },
  { value: "arr", label: "ARR" },
]

// Slices the server records, as "dimension:value". One slice at a time:
// the server keeps each as its own series.
export const SLICE_GROUPS: { label: string; options: { value: string; label: string }[] }[] = [
  {
    label: "Platform",
    options: [
      { value: "platform:web", label: "Web" },
      { value: "platform:mobile", label: "Mobile" },
    ],
  },
  {
    label: "Plan",
    options: [
      { value: "plan:monthly", label: "Monthly" },
      { value: "plan:annual", label: "Annual" },
    ],
  },
  {
    label: "Cohort",
    options: [
      { value: "cohort:new", label: "New" },
      { value: "cohort:existing", label: "Existing" },
    ],
  },
]

export interface Series {
  data: { day: number; value: number }[]
  // True when the chosen slice or metric has nothing to chart; the chart shows
  // an empty state instead of a flat line.
  empty: boolean
}

export function buildSeries(points: FunnelPoint[], metric: Metric, slice: string | null): Series {
  if (metric === "arr") {
    if (slice) return { data: [], empty: true }
    return { data: points.map((p) => ({ day: p.day, value: p.arr })), empty: points.length === 0 }
  }
  const data: Series["data"] = []
  for (const p of points) {
    const rates = slice ? p.slices?.[slice] : p.rates
    if (!rates || rates[metric] === undefined) continue
    data.push({ day: p.day, value: rates[metric] })
  }
  return { data, empty: data.length === 0 }
}

export function releaseMarkers(releases: Release[], firstDay: number, lastDay: number): Release[] {
  return releases.filter((r) => r.day >= firstDay && r.day <= lastDay)
}
