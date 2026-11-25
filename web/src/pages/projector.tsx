import { useEffect, useState } from "react"
import { WifiOff } from "lucide-react"
import { Debrief } from "@/components/projector/debrief"
import { Leaderboard } from "@/components/projector/leaderboard"
import { ProjectorHeader } from "@/components/projector/header"
import { Skeleton } from "@/components/ui/skeleton"
import { DEBRIEF_VIEWS, type DebriefView } from "@/lib/debrief"
import { useCalendar } from "@/lib/use-calendar"
import { useDebrief } from "@/lib/use-debrief"
import { useProjector } from "@/lib/use-projector"
import { cn } from "@/lib/utils"

export function ProjectorPage() {
  const { feed, rows, moves, offline } = useProjector()
  const calendar = useCalendar()
  const revealed = feed?.revealed ?? false
  const debrief = useDebrief(revealed)
  const [view, setView] = useState<DebriefView>("ranking")

  // The MC steps through the debrief with the number keys once the reveal has happened.
  useEffect(() => {
    if (!revealed) return
    const onKey = (event: KeyboardEvent) => {
      const match = DEBRIEF_VIEWS.find((v) => v.key === event.key)
      if (match) setView(match.value)
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [revealed])

  if (!feed) {
    return (
      <main className="mx-auto flex max-w-7xl flex-col gap-6 p-10">
        <Skeleton className="h-28 w-full rounded-3xl" />
        <Skeleton className="h-96 w-full rounded-3xl" />
      </main>
    )
  }

  const shown: DebriefView = revealed ? view : "ranking"
  return (
    <main className="mx-auto flex min-h-screen max-w-7xl flex-col gap-8 p-10">
      <ProjectorHeader clock={feed.clock} calendar={calendar} />
      {offline && (
        <div
          role="status"
          className="flex items-center gap-3 rounded-2xl border border-destructive/30 bg-destructive/10 px-5 py-3 text-lg text-destructive"
        >
          <WifiOff className="size-5" /> Lost the server. Showing the last update.
        </div>
      )}
      {revealed && (
        <nav className="flex flex-wrap gap-2" aria-label="Debrief">
          {DEBRIEF_VIEWS.map((v) => (
            <button
              key={v.value}
              onClick={() => setView(v.value)}
              className={cn(
                "rounded-full border px-5 py-2 text-lg",
                shown === v.value ? "border-primary bg-primary text-primary-foreground" : "bg-card text-muted-foreground",
              )}
            >
              <span className="mr-2 font-mono text-sm opacity-70">{v.key}</span>
              {v.label}
            </button>
          ))}
        </nav>
      )}
      {shown === "ranking" ? (
        <Leaderboard rows={rows} moves={moves} revealed={feed.revealed} />
      ) : (
        <Debrief view={shown} data={debrief} />
      )}
    </main>
  )
}
