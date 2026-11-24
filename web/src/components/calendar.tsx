import { weekKind } from "@/lib/contract"
import type { Calendar } from "@/lib/types"
import { cn } from "@/lib/utils"

// The whole game on one strip: a row per quarter, a cell per week.
export function CalendarStrip({ calendar, week }: { calendar: Calendar; week: number }) {
  const quarters = Math.ceil(calendar.weeks / calendar.weeks_per_quarter)
  return (
    <section className="surface flex flex-col gap-4 p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="eyebrow">The year</p>
        <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
          <li className="flex items-center gap-1.5">
            <span className="size-2.5 rounded-sm bg-primary" /> This week
          </li>
          <li className="flex items-center gap-1.5">
            <span className="size-2.5 rounded-sm bg-chart-4" /> Load surge
          </li>
          <li className="flex items-center gap-1.5">
            <span className="size-2.5 rounded-sm border-2 border-chart-5" /> Whale contract applications
          </li>
          <li className="flex items-center gap-1.5">
            <span className="size-2.5 rounded-sm border-2 border-foreground/60 border-dashed" /> Checkpoint
          </li>
        </ul>
      </div>
      <div className="flex flex-col gap-2">
        {Array.from({ length: quarters }, (_, q) => (
          <div key={q} className="flex items-center gap-3">
            <span className="eyebrow w-6 shrink-0">Q{q + 1}</span>
            <div className="grid flex-1 gap-1" style={{ gridTemplateColumns: `repeat(${calendar.weeks_per_quarter}, minmax(0, 1fr))` }}>
              {Array.from({ length: calendar.weeks_per_quarter }, (_, i) => {
                const w = q * calendar.weeks_per_quarter + i + 1
                if (w > calendar.weeks) return <span key={w} />
                const kinds = weekKind(w, calendar)
                return (
                  <span
                    key={w}
                    title={`Week ${w}${kinds.includes("surge") ? ", load surge" : ""}${kinds.includes("checkpoint") ? ", checkpoint" : ""}${kinds.includes("contract") ? ", contract applications" : ""}`}
                    className={cn(
                      "h-6 rounded-sm bg-muted",
                      w < week && "bg-foreground/15",
                      kinds.includes("surge") && "bg-chart-4/70",
                      kinds.includes("contract") && "border-2 border-chart-5",
                      kinds.includes("checkpoint") && "border-2 border-dashed border-foreground/60",
                      w === week && "bg-primary",
                    )}
                  />
                )
              })}
            </div>
          </div>
        ))}
      </div>
      <p className="text-xs text-muted-foreground">
        Weeks {calendar.surge.start} to {calendar.surge.end} bring a load surge. Platform problems you carry into it can
        take your product down.
      </p>
    </section>
  )
}
