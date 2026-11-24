import { Brand } from "@/components/brand"
import { countdownText, runState } from "@/lib/format"
import type { Calendar, Clock } from "@/lib/types"
import { cn } from "@/lib/utils"

// Big, far-readable header: the server's clock exactly as last reported.
export function ProjectorHeader({ clock, calendar }: { clock: Clock; calendar: Calendar | null }) {
  const state = runState(clock)
  const counting = clock.countdown_remaining !== null && !clock.finished
  const surge =
    calendar && clock.week >= calendar.surge.start && clock.week <= calendar.surge.end && !clock.finished
  const quarter = calendar ? Math.ceil(clock.week / calendar.weeks_per_quarter) : null

  return (
    <header className="flex flex-wrap items-end justify-between gap-6">
      <div className="flex flex-col gap-4">
        <Brand sub="Live" />
        <div className="flex items-baseline gap-5">
          <p className="display tabular text-7xl leading-none">Week {clock.week}</p>
          {quarter && <p className="eyebrow text-base">Quarter {Math.min(quarter, 4)}</p>}
        </div>
      </div>
      <div className="flex flex-col items-end gap-3">
        <span
          className={cn(
            "rounded-full px-5 py-2 text-lg font-medium",
            state.tone === "go" && "bg-success/15 text-success",
            state.tone === "wait" && "bg-muted text-foreground",
            state.tone === "stop" && "bg-primary text-primary-foreground",
          )}
        >
          {state.label}
        </span>
        {surge && (
          <span className="rounded-full bg-chart-4/20 px-5 py-2 text-lg font-medium text-foreground">
            Peak-season load surge
          </span>
        )}
        {counting && (
          <div className="text-right">
            <p className="eyebrow text-base">{clock.hold ? "Break held" : "Back in"}</p>
            <p className={cn("display tabular text-7xl leading-none", clock.warning && "text-destructive")}>
              {countdownText(clock.countdown_remaining as number)}
            </p>
          </div>
        )}
      </div>
    </header>
  )
}
