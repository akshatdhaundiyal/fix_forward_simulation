import { AlertTriangle, WifiOff } from "lucide-react"
import type { FeedStatus } from "@/lib/feed"

export function ConnectionBanner({ status }: { status: FeedStatus }) {
  if (status === "live" || status === "connecting" || status === "invalid-code") return null
  const degraded = status === "server-degraded"
  const Icon = degraded ? AlertTriangle : WifiOff
  return (
    <div
      role="status"
      className="flex items-center gap-3 rounded-2xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive"
    >
      <Icon className="size-4 shrink-0" />
      {degraded
        ? "The game is paused because the server cannot save its log. Tell your host."
        : "Connection lost. Showing the last update. Trying again."}
    </div>
  )
}
