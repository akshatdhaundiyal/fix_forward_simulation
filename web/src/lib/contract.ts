import type { Calendar, TeamView } from "./types"

export type ContractState = "not-open" | "open" | "applied" | "pending" | "awarded" | "not-awarded"

// Where a team stands on the bespoke whale contract, from its view, the clock
// and the calendar's application window. The server awards the contract in the
// tick that ends the last application week, so for that one day an applicant's
// result is pending rather than "not awarded".
export function contractState(
  b1: TeamView["b1"],
  day: number,
  week: number,
  calendar: Calendar,
): ContractState {
  if (b1.awarded) return "awarded"
  const { first, last } = calendar.contract_window
  if (week < first) return "not-open"
  if (week <= last) return b1.applied ? "applied" : "open"
  if (b1.applied && day <= last * calendar.days_per_week) return "pending"
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
