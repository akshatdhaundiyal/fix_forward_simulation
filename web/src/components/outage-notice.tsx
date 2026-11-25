import { ServerCrash } from "lucide-react"

// Shown while a peak-season outage has seized the team's build capacity.
export function OutageNotice({ outage }: { outage: boolean }) {
  if (!outage) return null
  return (
    <div
      role="alert"
      className="flex items-start gap-3 rounded-2xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm"
    >
      <ServerCrash className="mt-0.5 size-4 shrink-0 text-destructive" />
      <div>
        <p className="font-medium text-destructive">Peak-season outage</p>
        <p className="text-muted-foreground">
          The surge took your platform down. Your team's build time is going into repairs first. Your queue resumes once
          they are done.
        </p>
      </div>
    </div>
  )
}
