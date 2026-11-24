// What a team may see about stakeholder places: its own bookings and the
// places left, never anyone else's booking.
export interface RoleBooking {
  role: string
  title: string
  places_left: number
  mine: { id: number; position: number | null; done: boolean } | null
}

export interface BookingsView {
  quarter: number
  per_quarter: number
  roles: RoleBooking[]
}

export type RoleState = "met" | "booked" | "full" | "open"

// A booked stakeholder shows the booking, a full one shows no Book button, and
// only an open one can be booked.
export function roleState(role: RoleBooking): RoleState {
  if (role.mine) return role.mine.done ? "met" : "booked"
  return role.places_left <= 0 ? "full" : "open"
}

export function placesText(role: RoleBooking, perQuarter: number): string {
  if (role.places_left <= 0) return "All places taken"
  return `${role.places_left} of ${perQuarter} places left`
}

export function positionText(position: number | null): string {
  if (position === null) return "Met"
  return position === 1 ? "You are next" : `${position - 1} ahead of you`
}
