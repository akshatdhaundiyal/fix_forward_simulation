import type { Clock } from "./types"

export type Band = "green" | "amber" | "red"
export type RoleId = "vp_sales" | "whale_lead" | "cto"

export interface WhaleFacts {
  data_isolation_shipped: boolean
  outage_hit: boolean
  applied: boolean
}

export interface BoardTeam {
  team: number
  name: string
  band: Band
  cto_line: string | null
  whale: { facts: WhaleFacts; lines: string[] }
  declined: boolean
}

export interface BoardRole {
  role: RoleId
  title: string
  unprompted: string | null
  asked: { question: string; answer: string }[]
  after: string | null
}

export interface BoardBooking {
  id: number
  team: number
  name: string
  role: RoleId
  quarter: number
  done: boolean
}

export interface Board {
  clock: Clock
  quarter: number
  roles: BoardRole[]
  teams: BoardTeam[]
  bookings: BoardBooking[]
}

export const ROLE_LABEL: Record<RoleId, string> = {
  vp_sales: "VP Sales",
  whale_lead: "Whale lead",
  cto: "CTO",
}

// Meetings still to run for a stakeholder, in the order teams booked them.
export function queueFor(board: Board, role: RoleId): BoardBooking[] {
  return board.bookings.filter((b) => b.role === role && !b.done).sort((a, b) => a.id - b.id)
}

export function metCount(board: Board, role: RoleId): number {
  return board.bookings.filter((b) => b.role === role && b.done).length
}

export function teamFor(board: Board, team: number): BoardTeam | undefined {
  return board.teams.find((t) => t.team === team)
}

// The Whale lead's three facts as plain yes or no, in the order they are read out.
export const FACT_LABELS: { key: keyof WhaleFacts; label: string }[] = [
  { key: "data_isolation_shipped", label: "Data isolation has shipped" },
  { key: "outage_hit", label: "The team has had a peak-season outage" },
  { key: "applied", label: "The team applied for the bespoke contract" },
]

export const BAND_LABEL: Record<Band, string> = { green: "Green", amber: "Amber", red: "Red" }
// Worst first, so the CTO sees who needs a word before anyone else.
const BAND_ORDER: Record<Band, number> = { red: 0, amber: 1, green: 2 }

export function sortByBand(teams: BoardTeam[]): BoardTeam[] {
  return [...teams].sort((a, b) => BAND_ORDER[a.band] - BAND_ORDER[b.band] || a.team - b.team)
}

// The decline checklist is entered as a count of items ticked; the server
// sees only that count.
export const DECLINE_ITEMS = 3

export function declineTicks(ticked: boolean[]): number {
  return ticked.filter(Boolean).length
}
