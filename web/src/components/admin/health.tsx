import { AlertTriangle, CheckCircle2, WifiOff } from "lucide-react"
import { useState } from "react"
import { Button } from "@/components/ui/button"
import type { AdminState } from "@/lib/use-admin"
import { Confirm } from "./confirm"

// Log health, snapshot age, team codes and the final reveal.
export function Health({ admin }: { admin: AdminState }) {
  const { status, offline, api, run } = admin
  const [revealing, setRevealing] = useState(false)
  if (!status) return null
  const age = status.last_snapshot_age

  return (
    <div className="flex flex-col gap-4">
      {offline && (
        <div role="status" className="flex items-center gap-3 rounded-2xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          <WifiOff className="size-4" /> Lost the server. Showing the last update.
        </div>
      )}
      {status.degraded && (
        <div role="alert" className="flex items-center gap-3 rounded-2xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          <AlertTriangle className="size-4 shrink-0" />
          <span>
            The game is paused because it cannot write its log: {status.degraded}. Fix the disk, then reload from the log below.
          </span>
        </div>
      )}
      {status.snapshot_warning && (
        <div role="status" className="flex items-center gap-3 rounded-2xl border border-warning/50 bg-warning/10 px-4 py-3 text-sm">
          <AlertTriangle className="size-4 shrink-0" /> Snapshot warning: {status.snapshot_warning}
        </div>
      )}

      <section className="surface grid gap-4 p-5 sm:grid-cols-3">
        <div>
          <p className="eyebrow">Log</p>
          <p className="flex items-center gap-2 text-sm font-medium">
            {status.degraded ? <AlertTriangle className="size-4 text-destructive" /> : <CheckCircle2 className="size-4 text-success" />}
            {status.degraded ? "Not writing" : "Healthy"} · line {status.log_seq}
          </p>
        </div>
        <div>
          <p className="eyebrow">Last snapshot</p>
          <p className="text-sm font-medium">{age === null ? "None yet" : `${Math.round(age)} seconds ago`}</p>
        </div>
        <div>
          <p className="eyebrow">Final reveal</p>
          {status.revealed ? (
            <p className="text-sm font-medium">Shown on the projector</p>
          ) : (
            <Button size="sm" className="rounded-full" onClick={() => setRevealing(true)}>
              Reveal debt and valuation
            </Button>
          )}
        </div>
      </section>

      <section className="surface flex flex-col gap-3 p-5">
        <p className="eyebrow">Teams and their codes</p>
        <ul className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
          {status.teams.map((t) => (
            <li key={t.team} className="flex items-center justify-between rounded-2xl border bg-background px-4 py-2.5">
              <span className="text-sm">
                <span className="tabular mr-2 text-muted-foreground">{t.team}</span>
                {t.name}
              </span>
              <span className="font-mono text-sm tracking-[0.2em]">{t.code}</span>
            </li>
          ))}
        </ul>
      </section>

      <Confirm
        open={revealing}
        title="Reveal debt and valuation?"
        action="Reveal on the projector"
        onCancel={() => setRevealing(false)}
        onConfirm={() => {
          setRevealing(false)
          void run(() => api.reveal(), "Revealed on the projector")
        }}
      >
        The projector switches to the final ranking by valuation and shows every team's hidden debt. This cannot be taken
        back, so do it only at the debrief.
      </Confirm>
    </div>
  )
}
