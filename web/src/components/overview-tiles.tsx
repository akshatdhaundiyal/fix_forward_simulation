import { AlertTriangle, ArrowRight, Gauge, ShieldCheck, TrendingUp } from "lucide-react"
import { Progress } from "@/components/ui/progress"
import { formatCr } from "@/lib/format"
import { backlogBu } from "@/lib/queue"
import { SEGMENTS, SEGMENT_NAMES, type TeamView } from "@/lib/types"
import { cn } from "@/lib/utils"

function Tile({
  icon: Icon,
  label,
  children,
  onClick,
  tone,
}: {
  icon: typeof TrendingUp
  label: string
  children: React.ReactNode
  onClick?: () => void
  tone?: "alert"
}) {
  const Wrapper = onClick ? "button" : "div"
  return (
    <Wrapper
      onClick={onClick}
      className={cn(
        "surface flex min-h-44 flex-col gap-4 p-5 text-left",
        onClick && "transition-colors hover:bg-accent focus-visible:ring-3 focus-visible:ring-ring/50 outline-none",
        tone === "alert" && "border-destructive/30 bg-destructive/5",
      )}
    >
      <div className="flex items-center justify-between">
        <p className="eyebrow">{label}</p>
        <Icon className="size-4 text-muted-foreground" />
      </div>
      {children}
    </Wrapper>
  )
}

function Sparkline({ values }: { values: number[] }) {
  if (values.length < 2) return <div className="h-10" />
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = max - min || 1
  const points = values
    .map((v, i) => `${(i / (values.length - 1)) * 100},${36 - ((v - min) / span) * 32}`)
    .join(" ")
  return (
    <svg viewBox="0 0 100 40" preserveAspectRatio="none" className="h-10 w-full" aria-hidden>
      <polyline points={points} fill="none" stroke="var(--chart-2)" strokeWidth="2" vectorEffect="non-scaling-stroke" />
    </svg>
  )
}

// Exactly four tiles. Everything else is one click down.
export function OverviewTiles({ view, onOpenIncidents }: { view: TeamView; onOpenIncidents: () => void }) {
  const totalSeries = (view.funnel.W ?? []).map((_, i) =>
    SEGMENTS.reduce((sum, s) => sum + (view.funnel[s]?.[i]?.arr ?? 0), 0),
  )
  const latestArr = (s: (typeof SEGMENTS)[number]) => view.funnel[s]?.at(-1)?.arr ?? 0
  const backlog = backlogBu(view.queue)
  const open = view.tiles.open_incidents

  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <Tile icon={TrendingUp} label="Annual recurring revenue">
        <p className="display tabular text-4xl leading-none">{formatCr(view.tiles.arr)}</p>
        <Sparkline values={totalSeries} />
        {totalSeries.length > 0 && (
          <p className="tabular text-xs text-muted-foreground">
            {SEGMENTS.map((s) => `${s} ${latestArr(s).toFixed(1)}`).join("  ·  ")} Cr
          </p>
        )}
      </Tile>

      <Tile icon={ShieldCheck} label="Customer trust">
        <div className="flex flex-col gap-3">
          {SEGMENTS.map((s) => (
            <div key={s} className="flex flex-col gap-1.5">
              <div className="flex items-baseline justify-between text-xs">
                <span className="text-muted-foreground">{SEGMENT_NAMES[s]}</span>
                <span className="tabular font-medium">{view.tiles.trust[s].toFixed(0)}</span>
              </div>
              <Progress value={view.tiles.trust[s]} className="h-1.5" />
            </div>
          ))}
        </div>
      </Tile>

      <Tile icon={Gauge} label="Build capacity">
        <p className="display tabular text-4xl leading-none">
          {view.tiles.capacity_bu_week.toFixed(1)}
          <span className="ml-2 font-sans text-sm text-muted-foreground">BU a week</span>
        </p>
        <p className="mt-auto text-xs text-muted-foreground">
          {view.queue.length === 0
            ? "Nothing queued. Your team is idle."
            : `${backlog.toFixed(0)} BU still to build across ${view.queue.length} ${view.queue.length === 1 ? "item" : "items"}.`}
        </p>
      </Tile>

      <Tile
        icon={AlertTriangle}
        label="Open incidents"
        onClick={onOpenIncidents}
        tone={open > 0 ? "alert" : undefined}
      >
        <p className="display tabular text-4xl leading-none">{open}</p>
        <p className="mt-auto flex items-center gap-1 text-xs text-muted-foreground">
          {open === 0 ? "All clear." : "Needs your attention."}
          <ArrowRight className="size-3" />
        </p>
      </Tile>
    </div>
  )
}
