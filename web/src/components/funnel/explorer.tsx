import { useMemo, useState } from "react"
import { Skeleton } from "@/components/ui/skeleton"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { RATE_LABELS, metricToRate } from "@/lib/format"
import { METRIC_OPTIONS, SLICE_GROUPS, buildSeries, releaseMarkers, type Metric } from "@/lib/funnel"
import { SEGMENTS, SEGMENT_NAMES, type SegmentId, type TeamView } from "@/lib/types"
import { SeriesChart } from "./series-chart"
import { useHeavyView } from "./use-heavy-view"

const NO_SLICE = "all"

function Filter({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-2">
      <p className="eyebrow">{label}</p>
      {children}
    </div>
  )
}

const pill =
  "rounded-full px-4 data-[state=on]:bg-primary data-[state=on]:text-primary-foreground"

export function Explorer({
  code,
  pollSeconds,
  light,
}: {
  code: string
  pollSeconds: number
  // The ordinary view, used for release markers and the open incident's metric.
  light: TeamView
}) {
  const heavy = useHeavyView(code, pollSeconds)
  const incident = light.incidents[0]
  const [seg, setSeg] = useState<SegmentId>("W")
  const [metric, setMetric] = useState<Metric>(() => (incident ? metricToRate(incident.metric) : "activation"))
  const [slice, setSlice] = useState<string>(NO_SLICE)

  const data = heavy.status === "loading" ? undefined : heavy.view
  const points = data?.funnel[seg] ?? []
  const series = useMemo(
    () => buildSeries(points, metric, slice === NO_SLICE ? null : slice),
    [points, metric, slice],
  )
  const first = points[0]?.day ?? 0
  const last = points.at(-1)?.day ?? 0
  const releases = releaseMarkers(light.releases, first, last)

  const metricLabel = metric === "arr" ? "ARR" : RATE_LABELS[metric]
  const sliceLabel = SLICE_GROUPS.flatMap((g) => g.options).find((o) => o.value === slice)?.label

  return (
    <section className="surface flex flex-col gap-6 p-6">
      <div className="flex flex-col gap-1">
        <p className="eyebrow">Funnel explorer</p>
        <h3 className="display text-3xl">
          {SEGMENT_NAMES[seg]} · {metricLabel}
          {sliceLabel ? ` · ${sliceLabel}` : ""}
        </h3>
        <p className="text-sm text-muted-foreground">
          Orange lines mark your releases. Cut the data by slice to see where a change shows up.
        </p>
      </div>

      <div className="flex flex-wrap gap-x-8 gap-y-4">
        <Filter label="Segment">
          <ToggleGroup type="single" value={seg} variant="outline" onValueChange={(v) => v && setSeg(v as SegmentId)}>
            {SEGMENTS.map((s) => (
              <ToggleGroupItem key={s} value={s} className={pill}>
                {SEGMENT_NAMES[s]}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
        </Filter>
        <Filter label="Metric">
          <ToggleGroup type="single" value={metric} variant="outline" onValueChange={(v) => v && setMetric(v as Metric)} className="flex-wrap">
            {METRIC_OPTIONS.map((m) => (
              <ToggleGroupItem key={m.value} value={m.value} className={pill}>
                {m.label}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
        </Filter>
        <Filter label="Slice">
          <ToggleGroup type="single" value={slice} variant="outline" onValueChange={(v) => v && setSlice(v)} className="flex-wrap">
            <ToggleGroupItem value={NO_SLICE} className={pill}>
              All
            </ToggleGroupItem>
            {SLICE_GROUPS.flatMap((g) =>
              g.options.map((o) => (
                <ToggleGroupItem key={o.value} value={o.value} className={pill}>
                  {g.label}: {o.label}
                </ToggleGroupItem>
              )),
            )}
          </ToggleGroup>
        </Filter>
      </div>

      {heavy.status === "loading" ? (
        <Skeleton className="h-80 w-full rounded-2xl" />
      ) : series.empty ? (
        <div className="flex h-80 items-center justify-center rounded-2xl border border-dashed text-center text-sm text-muted-foreground">
          {metric === "arr" && slice !== NO_SLICE
            ? "ARR is not recorded by slice. Pick All, or choose a rate."
            : "Nothing to show for this view yet."}
        </div>
      ) : (
        <SeriesChart series={series} metric={metric} label={metricLabel} releases={releases} />
      )}
      {heavy.status === "error" && (
        <p className="text-xs text-destructive">Could not refresh the explorer. Showing the last data it had.</p>
      )}
    </section>
  )
}
