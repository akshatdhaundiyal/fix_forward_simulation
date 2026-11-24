import type { Calendar, TeamView } from "./types"

export type ContractState = "not-open" | "open" | "applied" | "awarded" | "not-awarded"

// Where a team stands on the bespoke whale contract, from its view, the clock's
// week and the calendar's application window.
export function contractState(b1: TeamView["b1"], week: number, calendar: Calendar): ContractState {
  if (b1.awarded) return "awarded"
  const { first, last } = calendar.contract_window
  if (week < first) return "not-open"
  if (week <= last) return b1.applied ? "applied" : "open"
  return "not-awarded"
}

export type WeekKind = "surge" | "checkpoint" | "contract"

export function weekKind(week: number, calendar: Calendar): WeekKind[] {
  const kinds: WeekKind[] = []
  if (week >= calendar.surge.start && week <= calendar.surge.end) kinds.push("surge")
  if (calendar.checkpoint_weeks.includes(week)) kinds.push("checkpoint")
  if (week >= calendar.contract_window.first && week <= calendar.contract_window.last) kinds.push("contract")
  return kinds
}
