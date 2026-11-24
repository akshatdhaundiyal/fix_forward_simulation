import { CheckCircle2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import type { StakeholderState } from "@/lib/use-stakeholder"
import { metCount, queueFor, ROLE_LABEL, type Board, type RoleId } from "@/lib/stakeholder"

// Teams in the order they booked. "Met" marks a meeting done and the queue
// refetches, so the next team moves up.
export function BookingQueue({ board, role, state }: { board: Board; role: RoleId; state: StakeholderState }) {
  const waiting = queueFor(board, role)
  const met = metCount(board, role)
  return (
    <section className="surface flex flex-col gap-4 p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <p className="eyebrow">Booking queue</p>
          <h2 className="display text-2xl">{ROLE_LABEL[role]}</h2>
        </div>
        <p className="tabular text-sm text-muted-foreground">
          {waiting.length} waiting, {met} met
        </p>
      </div>
      {waiting.length === 0 ? (
        <p className="text-sm text-muted-foreground">Nobody is waiting. New bookings appear here as teams make them.</p>
      ) : (
        <ol className="flex flex-col gap-2">
          {waiting.map((b, i) => (
            <li
              key={b.id}
              className="flex items-center gap-3 rounded-2xl border bg-background px-4 py-3 data-[next=true]:border-primary"
              data-next={i === 0}
            >
              <span className="display tabular w-6 text-xl text-muted-foreground">{i + 1}</span>
              <div className="min-w-0 flex-1">
                <p className="font-medium">{b.name}</p>
                <p className="text-xs text-muted-foreground">Booked in quarter {b.quarter}{i === 0 ? ". Meet them next." : ""}</p>
              </div>
              <Button
                variant={i === 0 ? "default" : "outline"}
                className="rounded-full"
                onClick={() => void state.run(() => state.api.done(b.id), `${b.name} marked as met`)}
              >
                <CheckCircle2 /> Met
              </Button>
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}
