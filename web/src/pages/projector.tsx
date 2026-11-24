import { WifiOff } from "lucide-react"
import { Leaderboard } from "@/components/projector/leaderboard"
import { ProjectorHeader } from "@/components/projector/header"
import { Skeleton } from "@/components/ui/skeleton"
import { useCalendar } from "@/lib/use-calendar"
import { useProjector } from "@/lib/use-projector"

export function ProjectorPage() {
  const { feed, rows, moves, offline } = useProjector()
  const calendar = useCalendar()

  if (!feed) {
    return (
      <main className="mx-auto flex max-w-7xl flex-col gap-6 p-10">
        <Skeleton className="h-28 w-full rounded-3xl" />
        <Skeleton className="h-96 w-full rounded-3xl" />
      </main>
    )
  }

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
      <Leaderboard rows={rows} moves={moves} revealed={feed.revealed} />
    </main>
  )
}
