import { useState } from "react"
import { CalendarCheck, CheckCircle2, Users } from "lucide-react"
import { toast } from "sonner"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { bookStakeholder } from "@/lib/api"
import { placesText, positionText, roleState, type RoleBooking } from "@/lib/bookings"
import { useBookings } from "@/lib/use-bookings"

const BLURB: Record<string, string> = {
  vp_sales: "Hears what customers and prospects are asking for.",
  whale_lead: "Speaks for Whale Alpha, your largest account.",
  cto: "Knows how healthy the platform is. Worth hearing out.",
}

function Row({ role, perQuarter, busy, onBook }: {
  role: RoleBooking
  perQuarter: number
  busy: boolean
  onBook: (role: string) => void
}) {
  const state = roleState(role)
  return (
    <li className="surface flex flex-wrap items-center gap-4 p-5">
      <span className="flex size-10 items-center justify-center rounded-full bg-muted text-muted-foreground">
        <Users className="size-5" />
      </span>
      <div className="min-w-0 flex-1">
        <p className="font-medium">{role.title}</p>
        <p className="text-sm text-muted-foreground">{BLURB[role.role] ?? ""}</p>
      </div>
      <div className="flex flex-col items-end gap-2">
        {state === "open" && (
          <>
            <p className="tabular text-sm text-muted-foreground">{placesText(role, perQuarter)}</p>
            <Button className="rounded-full" disabled={busy} onClick={() => onBook(role.role)}>
              <CalendarCheck /> Book a meeting
            </Button>
          </>
        )}
        {state === "full" && <Badge variant="outline">Full this quarter</Badge>}
        {state === "booked" && role.mine && (
          <>
            <Badge>Booked</Badge>
            <p className="tabular text-sm text-muted-foreground">
              Queue place {role.mine.position}. {positionText(role.mine.position)}.
            </p>
          </>
        )}
        {state === "met" && (
          <Badge variant="outline" className="gap-1">
            <CheckCircle2 className="size-3" /> Met
          </Badge>
        )}
      </div>
    </li>
  )
}

// Each stakeholder takes a few meetings a quarter, first come first served.
// The server decides; a refusal comes back as its own message.
export function Bookings({ code, pollSeconds }: { code: string; pollSeconds: number }) {
  const { view, offline, refresh } = useBookings(code, pollSeconds)
  const [busy, setBusy] = useState(false)

  async function book(role: string) {
    if (busy) return
    setBusy(true)
    try {
      const outcome = await bookStakeholder(code, role)
      if (outcome.ok) toast.success("Meeting booked. Go to the stakeholder when your turn comes.")
      else toast.error(outcome.error)
      await refresh()
    } finally {
      setBusy(false)
    }
  }

  if (!view) return offline ? <p className="text-sm text-muted-foreground">Could not load bookings. Retrying.</p> : <Skeleton className="h-56 w-full rounded-2xl" />

  return (
    <section className="flex flex-col gap-4">
      <div>
        <p className="eyebrow">Quarter {view.quarter}</p>
        <h2 className="display text-3xl">Stakeholder meetings</h2>
        <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
          Each stakeholder takes {view.per_quarter} meetings a quarter, three minutes in person. You can book each one
          once a quarter. What they tell you is a free but biased view, so weigh it against your own reports.
        </p>
      </div>
      {offline && <p className="text-sm text-warning">Could not reach the server. Showing the last known places.</p>}
      <ul className="flex flex-col gap-3">
        {view.roles.map((r) => (
          <Row key={r.role} role={r} perQuarter={view.per_quarter} busy={busy} onBook={book} />
        ))}
      </ul>
    </section>
  )
}
