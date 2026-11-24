import { useState } from "react"
import { Button } from "@/components/ui/button"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import type { AdminState } from "@/lib/use-admin"

const INCIDENTS = [1, 2, 3]

// Trigger or cancel one incident for a single team or for every team.
export function IncidentControls({ admin }: { admin: AdminState }) {
  const { status, api, run } = admin
  const [team, setTeam] = useState<string>("all")
  const [incident, setIncident] = useState<string>("1")
  if (!status) return null
  const target = team === "all" ? ("all" as const) : Number(team)
  const who = team === "all" ? "every team" : (status.teams.find((t) => String(t.team) === team)?.name ?? `team ${team}`)

  return (
    <section className="surface flex flex-col gap-4 p-5">
      <p className="eyebrow">Incidents</p>
      <div className="flex flex-wrap gap-x-8 gap-y-4">
        <div className="flex flex-col gap-2">
          <p className="eyebrow">Incident</p>
          <ToggleGroup type="single" variant="outline" value={incident} onValueChange={(v) => v && setIncident(v)} className="rounded-full bg-background p-1">
            {INCIDENTS.map((n) => (
              <ToggleGroupItem key={n} value={String(n)} className="rounded-full px-4 data-[state=on]:bg-primary data-[state=on]:text-primary-foreground">
                {n}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
        </div>
        <div className="flex flex-col gap-2">
          <p className="eyebrow">For</p>
          <ToggleGroup type="single" variant="outline" value={team} onValueChange={(v) => v && setTeam(v)} className="flex-wrap">
            <ToggleGroupItem value="all" className="rounded-full px-4 data-[state=on]:bg-primary data-[state=on]:text-primary-foreground">
              All teams
            </ToggleGroupItem>
            {status.teams.map((t) => (
              <ToggleGroupItem key={t.team} value={String(t.team)} className="rounded-full px-4 data-[state=on]:bg-primary data-[state=on]:text-primary-foreground">
                {t.team}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
        </div>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button className="rounded-full" onClick={() => void run(() => api.incident(target, Number(incident), "trigger"), `Triggered incident ${incident} for ${who}`)}>
          Trigger incident {incident} for {who}
        </Button>
        <Button variant="outline" className="rounded-full bg-background" onClick={() => void run(() => api.incident(target, Number(incident), "cancel"), `Cancelled incident ${incident} for ${who}`)}>
          Cancel it
        </Button>
      </div>
    </section>
  )
}
