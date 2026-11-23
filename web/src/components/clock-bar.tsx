import { Pause, Play, Flag, Coffee } from "lucide-react"
import { countdownText, runState } from "@/lib/format"
import type { Clock } from "@/lib/types"
import { cn } from "@/lib/utils"

// Shows the server's clock exactly as last reported. The console keeps no
// timer of its own, so these values only change when the server says so.
export function ClockBar({ clock, quarter }: { clock: Clock; quarter: number }) {
  const state = runState(clock)
  const counting = clock.countdown_remaining !== null && !clock.finished
  const Icon = clock.finished ? Flag : clock.running ? Play : counting ? Coffee : Pause

  return (
    <div
      className={cn(
        "surface flex flex-wrap items-center gap-x-8 gap-y-3 px-5 py-4",
        clock.warning && "border-warning/50 bg-warning/10",
      )}
    >
      <div className="flex items-center gap-3">
        <span
          className={cn(
            "flex size-9 items-center justify-center rounded-full",
            state.tone === "go" && "bg-success/15 text-success",
            state.tone === "wait" && "bg-muted text-muted-foreground",
            state.tone === "stop" && "bg-primary text-primary-foreground",
          )}
        >
          <Icon className="size-4" />
        </span>
        <div>
          <p className="eyebrow">Game</p>
          <p className="text-sm font-medium">{state.label}</p>
        </div>
      </div>

      <div>
        <p className="eyebrow">Quarter {quarter}</p>
        <p className="display tabular text-2xl leading-none">
          Week {clock.week}
          <span className="ml-2 font-sans text-sm text-muted-foreground">day {clock.day}</span>
        </p>
      </div>

      {clock.next_checkpoint_week !== null && !clock.finished && (
        <div>
          <p className="eyebrow">Next checkpoint</p>
          <p className="text-sm font-medium">End of week {clock.next_checkpoint_week}</p>
        </div>
      )}

      {counting && (
        <div className="ml-auto text-right">
          <p className="eyebrow">{clock.hold ? "Break held by the host" : "Back in"}</p>
          <p
            className={cn("display tabular text-3xl leading-none", clock.warning && "text-foreground")}
            aria-live="off"
          >
            {countdownText(clock.countdown_remaining as number)}
          </p>
        </div>
      )}
    </div>
  )
}
