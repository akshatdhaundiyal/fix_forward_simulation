import { Skeleton } from "@/components/ui/skeleton"
import { percent } from "@/lib/format"
import { releaseMarkers } from "@/lib/funnel"
import { errorSeries, latencySeries, ticketSeries } from "@/lib/telemetry"
import { SEGMENT_NAMES, SEGMENTS, type TeamView } from "@/lib/types"
import { useWindowView } from "@/lib/use-window-view"
import { OpsChart } from "./ops-chart"

// Two quarters of days, enough for a trend to show through the noise.
const OPERATIONS_WINDOW = { days: 182 }

const SEGMENT_COLOR = { W: "var(--chart-5)", M: "var(--chart-3)", S: "var(--chart-2)" } as const

function Panel({ title, blurb, children }: { title: string; blurb: string; children: React.ReactNode }) {
  return (
    <section className="surface flex flex-col gap-4 p-6">
      <div>
        <p className="eyebrow">{title}</p>
        <p className="text-sm text-muted-foreground">{blurb}</p>
      </div>
      {children}
    </section>
  )
}

export function Operations({ code, pollSeconds, light }: { code: string; pollSeconds: number; light: TeamView }) {
  const state = useWindowView(code, pollSeconds, OPERATIONS_WINDOW)
  const view = state.status === "loading" ? undefined : state.view

  if (!view) return <Skeleton className="h-96 w-full rounded-2xl" />

  const points = view.telemetry
  const first = points[0]?.day ?? 0
  const last = points.at(-1)?.day ?? 0
  const releases = releaseMarkers(light.releases, first, last)

  if (points.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed p-10 text-center text-sm text-muted-foreground">
        Nothing to show yet. Operations data appears once the game has run for a day.
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="max-w-2xl text-sm text-muted-foreground">
        Live readings from your product. Day to day they move around a little, so give a change a few weeks before you
        trust it. Orange lines mark your releases.
      </p>
      <Panel title="Error rate" blurb="Share of requests that fail.">
        <OpsChart
          data={errorSeries(points)}
          lines={[{ key: "value", label: "Error rate", color: "var(--chart-1)" }]}
          releases={releases}
          format={(v) => percent(v, 2)}
        />
      </Panel>
      <Panel title="Response time" blurb="Slowest one percent of requests (p99), in milliseconds.">
        <OpsChart
          data={latencySeries(points)}
          lines={[{ key: "value", label: "p99 latency", color: "var(--chart-1)" }]}
          releases={releases}
          format={(v) => `${v.toFixed(0)} ms`}
        />
      </Panel>
      <Panel title="Support tickets" blurb="Tickets a day, for each customer segment.">
        <OpsChart
          data={ticketSeries(points)}
          lines={SEGMENTS.map((s) => ({ key: s, label: SEGMENT_NAMES[s], color: SEGMENT_COLOR[s] }))}
          releases={releases}
          format={(v) => v.toFixed(1)}
        />
        <ul className="flex flex-wrap gap-4 text-xs text-muted-foreground">
          {SEGMENTS.map((s) => (
            <li key={s} className="flex items-center gap-2">
              <span className="size-2 rounded-full" style={{ background: SEGMENT_COLOR[s] }} />
              {SEGMENT_NAMES[s]}
            </li>
          ))}
        </ul>
      </Panel>
    </div>
  )
}
