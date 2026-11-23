import { FilePlus2 } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { useActions } from "@/components/actions"
import { SEGMENTS, SEGMENT_NAMES, type SegmentId, type TeamView } from "@/lib/types"

function SegmentReports({ seg, view }: { seg: SegmentId; view: TeamView }) {
  const { run, busy } = useActions()
  const reports = view.reports.filter((r) => r.seg === seg).sort((a, b) => b.day - a.day)
  const queued = view.queue.some((q) => q.kind === "report" && q.seg === seg)
  const names = Object.fromEntries(view.cards.map((c) => [c.id, c.name]))

  return (
    <section className="surface flex flex-col gap-4 p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="eyebrow">Segment report</p>
          <h3 className="display text-2xl">{SEGMENT_NAMES[seg]}</h3>
        </div>
        <div className="flex items-center gap-2">
          {queued && <Badge variant="outline">In your queue</Badge>}
          <Button
            size="sm"
            className="rounded-full"
            disabled={busy}
            onClick={() => void run({ type: "queue_add", report: seg })}
          >
            <FilePlus2 />
            Order report
          </Button>
        </div>
      </div>

      {reports.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No report yet. Ordering one costs build time, and shows how useful each available card would be for this
          segment.
        </p>
      ) : (
        reports.map((r) => {
          const rows = Object.entries(r.utility).sort((a, b) => b[1] - a[1])
          return (
            <div key={r.day} className="flex flex-col gap-3 rounded-2xl border bg-background p-4">
              <p className="eyebrow">Received day {r.day}</p>
              {r.alerts.map((a) => (
                <p key={a} className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  {a}
                </p>
              ))}
              <ul className="flex flex-col gap-2">
                {rows.map(([id, value]) => (
                  <li key={id} className="flex items-center gap-3 text-sm">
                    <span className="min-w-0 flex-1 truncate">{names[id] ?? id}</span>
                    <div className="h-1.5 w-28 overflow-hidden rounded-full bg-muted">
                      <div className="h-full rounded-full bg-primary" style={{ width: `${Math.min(100, value)}%` }} />
                    </div>
                    <Badge variant="secondary" className="tabular w-10 justify-center font-mono">
                      {value}
                    </Badge>
                  </li>
                ))}
              </ul>
              <p className="text-xs text-muted-foreground">
                Utility is scored 0 to 100. A report covers the cards that were available when it was ordered.
              </p>
            </div>
          )
        })
      )}
    </section>
  )
}

export function Reports({ view }: { view: TeamView }) {
  return (
    <div className="grid gap-4 xl:grid-cols-3">
      {SEGMENTS.map((s) => (
        <SegmentReports key={s} seg={s} view={view} />
      ))}
    </div>
  )
}
