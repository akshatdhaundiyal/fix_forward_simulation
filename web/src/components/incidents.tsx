import { AlertTriangle, CheckCircle2, Hammer, Undo2, Wrench } from "lucide-react"
import { useState } from "react"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { useActions } from "@/components/actions"
import { RATE_LABELS, causeLabel, metricToRate } from "@/lib/format"
import { rollbackCandidates } from "@/lib/queue"
import type { Card, Incident, TeamView } from "@/lib/types"
import { cn } from "@/lib/utils"

// Shown above every tab while something is open. It names the symptom only.
export function IncidentAlert({ incidents, onOpen }: { incidents: Incident[]; onOpen: () => void }) {
  if (incidents.length === 0) return null
  return (
    <div
      role="alert"
      className="flex flex-wrap items-center gap-3 rounded-2xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm"
    >
      <AlertTriangle className="size-4 shrink-0 text-destructive" />
      <p className="flex-1 font-medium text-destructive">{incidents.map((i) => i.symptom).join("  ")}</p>
      <Button size="sm" variant="outline" className="rounded-full bg-background" onClick={onOpen}>
        Investigate
      </Button>
    </div>
  )
}

function IncidentPanel({ incident, today, onOpenFunnel }: { incident: Incident; today: number; onOpenFunnel: () => void }) {
  const { run, busy } = useActions()
  const [cause, setCause] = useState<string | null>(null)

  return (
    <section className="surface flex flex-col gap-5 p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-2">
          <p className="eyebrow">Incident · open for {Math.max(0, today - incident.since_day)} days</p>
          <h3 className="display text-3xl leading-tight">{incident.symptom}</h3>
          <p className="text-sm text-muted-foreground">
            Affected metric: <span className="font-medium text-foreground">{RATE_LABELS[metricToRate(incident.metric)]}</span>.
            The cause is not in the alert. Look for it in the data.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {incident.patched && <Badge variant="secondary">Patched</Badge>}
          <Button variant="outline" size="sm" className="rounded-full bg-background" onClick={onOpenFunnel}>
            Open funnel explorer
          </Button>
        </div>
      </div>

      <div className="flex flex-col gap-3">
        <p className="text-sm font-medium">What do you think caused it?</p>
        <div role="radiogroup" aria-label="Candidate causes" className="grid gap-2 sm:grid-cols-2">
          {incident.options.map((option) => {
            const selected = cause === option
            return (
              <button
                key={option}
                role="radio"
                aria-checked={selected}
                onClick={() => setCause(option)}
                className={cn(
                  "rounded-2xl border bg-background px-4 py-3 text-left text-sm transition-colors hover:bg-accent focus-visible:ring-3 focus-visible:ring-ring/50 outline-none",
                  selected && "border-primary bg-accent ring-1 ring-primary",
                )}
              >
                {causeLabel(option)}
              </button>
            )
          })}
        </div>
        <p className="text-xs text-muted-foreground">
          A targeted fix goes to the front of your queue. It works only if you pick the real cause. A wrong pick spends
          the work and changes nothing, and you can try again.
        </p>
        <div className="flex flex-wrap gap-2">
          <Button
            className="rounded-full"
            disabled={busy || cause === null}
            onClick={() =>
              cause && void run({ type: "targeted_fix", incident: incident.id, cause }, "Fix added to the front of your queue")
            }
          >
            <Wrench /> Queue targeted fix
          </Button>
          <Button
            variant="outline"
            className="rounded-full bg-background"
            disabled={busy || incident.patched}
            onClick={() => void run({ type: "patch", incident: incident.id }, "Patch added to the front of your queue")}
          >
            <Hammer /> Queue a patch
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">
          A patch always works but only halves the damage for the rest of the game and stops the trust loss. It leaves
          a hidden cost in the codebase.
        </p>
      </div>
    </section>
  )
}

function RollbackSection({ cards }: { cards: Card[] }) {
  const { run, busy } = useActions()
  const [confirming, setConfirming] = useState<Card | null>(null)
  if (cards.length === 0) return null

  return (
    <section className="surface flex flex-col gap-4 p-6">
      <div>
        <p className="eyebrow">Roll back a release</p>
        <p className="text-sm text-muted-foreground">
          If a feature you shipped caused the incident, rolling it back resolves it. If it did not, you lose the feature
          for nothing. Re-shipping later costs half the original work.
        </p>
      </div>
      <ul className="flex flex-col gap-2">
        {cards.map((c) => (
          <li key={c.id} className="flex items-center justify-between gap-3 rounded-2xl border bg-background p-3 pl-4">
            <span className="text-sm font-medium">{c.name}</span>
            <Button
              variant="outline"
              size="sm"
              className="rounded-full"
              disabled={busy}
              onClick={() => setConfirming(c)}
            >
              <Undo2 /> Roll back
            </Button>
          </li>
        ))}
      </ul>

      <AlertDialog open={confirming !== null} onOpenChange={(open) => !open && setConfirming(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Roll back {confirming?.name}?</AlertDialogTitle>
            <AlertDialogDescription>
              The feature, its effects and the problems it carried are removed after a week, and its segment loses some
              trust. The work already spent is not returned. If it did not cause the incident, nothing else changes.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep the feature</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (confirming) void run({ type: "rollback", card: confirming.id }, "Rollback started")
                setConfirming(null)
              }}
            >
              Roll it back
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  )
}

export function Incidents({ view, onOpenFunnel }: { view: TeamView; onOpenFunnel: () => void }) {
  const candidates = rollbackCandidates(view)
  return (
    <div className="flex flex-col gap-4">
      {view.incidents.length === 0 ? (
        <section className="surface flex items-center gap-4 p-8">
          <CheckCircle2 className="size-6 text-success" />
          <div>
            <h3 className="display text-2xl">No open incidents</h3>
            <p className="text-sm text-muted-foreground">
              If a metric starts to fall, an alert appears here and across the top of every tab.
            </p>
          </div>
        </section>
      ) : (
        view.incidents.map((i) => (
          <IncidentPanel key={i.id} incident={i} today={view.day} onOpenFunnel={onOpenFunnel} />
        ))
      )}
      {view.incidents.length > 0 && <RollbackSection cards={candidates} />}
    </div>
  )
}
