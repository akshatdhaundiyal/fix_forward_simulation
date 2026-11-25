import { Badge } from "@/components/ui/badge"
import { BAND_LABEL, sortByBand, type Band, type BoardTeam } from "@/lib/stakeholder"
import { cn } from "@/lib/utils"

const DOT: Record<Band, string> = {
  green: "bg-success",
  amber: "bg-warning",
  red: "bg-destructive",
}

// Every team's band and the CTO's line for it. Only the band is ever sent, so
// there is no number here to read out.
export function CtoLights({ teams, hasLines }: { teams: BoardTeam[]; hasLines: boolean }) {
  const rows = sortByBand(teams)
  return (
    <section className="surface flex flex-col gap-4 p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <p className="eyebrow">Platform health</p>
          <h2 className="display text-2xl">Traffic lights</h2>
        </div>
        <p className="text-sm text-muted-foreground">Live. Worst first.</p>
      </div>
      <ul className="flex flex-col divide-y">
        {rows.map((t) => (
          <li key={t.team} className="flex flex-wrap items-center gap-x-4 gap-y-1 py-3">
            <span aria-hidden className={cn("size-4 shrink-0 rounded-full", DOT[t.band])} />
            <span className="w-28 font-medium">{t.name}</span>
            <Badge variant="outline" className="w-16 justify-center">
              {BAND_LABEL[t.band]}
            </Badge>
            <span className="min-w-0 flex-1 text-sm text-muted-foreground">
              {hasLines && t.cto_line ? t.cto_line : ""}
            </span>
          </li>
        ))}
      </ul>
      {!hasLines && (
        <p className="text-sm text-muted-foreground">
          This quarter's script has no traffic-light line. The colours are still live.
        </p>
      )}
    </section>
  )
}
