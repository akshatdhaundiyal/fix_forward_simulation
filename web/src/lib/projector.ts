import type { Clock } from "./types"

export interface ProjectorRow {
  team: number
  name: string
  arr: number
  trust_avg: number
  rank: number
  // Present only after the final reveal.
  uod?: number
  nev?: number
  penalty?: number
  bespoke_arr?: number
}

export interface ProjectorFeed {
  clock: Clock
  revealed: boolean
  rows: ProjectorRow[]
}

// The server already sorts and ranks; this keeps the screen correct if a feed
// ever arrives unsorted, and gives ties a stable team order.
export function sortRows(rows: ProjectorRow[], revealed: boolean): ProjectorRow[] {
  const key = (r: ProjectorRow) => (revealed && r.nev !== undefined ? r.nev : r.arr)
  return [...rows]
    .sort((a, b) => key(b) - key(a) || a.team - b.team)
    .map((r, i) => ({ ...r, rank: i + 1 }))
}

// Places gained (positive) or lost (negative) since the previous poll, by team.
export function rankMoves(previous: ProjectorRow[] | null, next: ProjectorRow[]): Record<number, number> {
  const moves: Record<number, number> = {}
  if (!previous) return moves
  const before = new Map(previous.map((r) => [r.team, r.rank]))
  for (const r of next) {
    const was = before.get(r.team)
    if (was !== undefined && was !== r.rank) moves[r.team] = was - r.rank
  }
  return moves
}
