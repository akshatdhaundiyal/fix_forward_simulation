import { REQUEST_TIMEOUT_MS } from "./api"

export type Band = "green" | "amber" | "red"

export interface DebriefPoint {
  week: number
  debt: number
  error_rate: number
  band: Band
  arr: number
}

export interface DebriefTeam {
  team: number
  name: string
  roles: string[]
  series: DebriefPoint[]
  final: { arr: number; nev: number; debt: number }
}

export interface DebriefGain {
  card: string
  name: string
  pitch: number
  target_gain: number
}

export interface DebriefData {
  weeks: number
  band_limits: [number, number]
  teams: DebriefTeam[]
  gains: DebriefGain[]
}

export type DebriefView = "ranking" | "curves" | "dashboard" | "gains"

export const DEBRIEF_VIEWS: { value: DebriefView; label: string; key: string }[] = [
  { value: "ranking", label: "Ranking", key: "1" },
  { value: "curves", label: "Hidden debt", key: "2" },
  { value: "dashboard", label: "On your dashboard", key: "3" },
  { value: "gains", label: "Hidden gains", key: "4" },
]

const ROLE_LABEL: Record<string, string> = {
  week26_leader: "Week-26 leader",
  winner: "Final winner",
  biggest_collapse: "Biggest collapse",
}

export function roleLabel(role: string): string {
  return ROLE_LABEL[role] ?? role
}

export function teamTitle(team: DebriefTeam): string {
  return `${team.name}: ${team.roles.map(roleLabel).join(" and ")}`
}

// One row per week with one column per team, for a chart. A week a team has no
// record for (history starts late after a snapshot start) is left undefined, so
// the line has a gap instead of a false zero.
export function weeklyRows(
  data: DebriefData,
  pick: (point: DebriefPoint) => number,
): Record<string, number | undefined>[] {
  const rows: Record<string, number | undefined>[] = []
  for (let week = 1; week <= data.weeks; week++) {
    const row: Record<string, number | undefined> = { week }
    for (const team of data.teams) {
      const point = team.series.find((p) => p.week === week)
      row[`t${team.team}`] = point ? pick(point) : undefined
    }
    rows.push(row)
  }
  return rows
}

export function bandAt(team: DebriefTeam, week: number): Band | null {
  return team.series.find((p) => p.week === week)?.band ?? null
}

// Null until the final reveal (the server answers 403); the data after it.
export async function fetchDebriefWith(
  fetchFn: typeof fetch = (...args) => fetch(...args),
): Promise<DebriefData | null> {
  const resp = await fetchFn("api/debrief", { cache: "no-store", signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS) })
  if (resp.status === 403) return null
  if (!resp.ok) throw new Error(`debrief ${resp.status}`)
  return (await resp.json()) as DebriefData
}
