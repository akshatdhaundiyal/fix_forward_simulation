import { ArrowDown, ArrowUp } from "lucide-react"
import { formatCr } from "@/lib/format"
import type { ProjectorRow } from "@/lib/projector"
import { cn } from "@/lib/utils"

function Move({ delta }: { delta: number | undefined }) {
  if (!delta) return <span className="w-8" />
  const Icon = delta > 0 ? ArrowUp : ArrowDown
  return (
    <span
      className={cn("flex w-8 items-center text-sm font-medium", delta > 0 ? "text-success" : "text-destructive")}
      aria-label={delta > 0 ? `Up ${delta}` : `Down ${-delta}`}
    >
      <Icon className="size-5" />
      {Math.abs(delta)}
    </span>
  )
}

export function Leaderboard({
  rows,
  moves,
  revealed,
}: {
  rows: ProjectorRow[]
  moves: Record<number, number>
  revealed: boolean
}) {
  const max = Math.max(1, ...rows.map((r) => r.arr))
  return (
    <section className="flex flex-col gap-2" aria-label={revealed ? "Final ranking by valuation" : "Leaderboard"}>
      <div className="flex items-center gap-4 px-5 pb-1 text-muted-foreground">
        <span className="w-14" />
        <span className="w-8" />
        <span className="eyebrow flex-1 text-sm">{revealed ? "Final ranking by valuation" : "Team"}</span>
        <span className="eyebrow w-32 text-right text-sm">ARR</span>
        <span className="eyebrow w-24 text-right text-sm">Trust</span>
        {revealed && (
          <>
            <span className="eyebrow w-28 text-right text-sm">Hidden debt</span>
            <span className="eyebrow w-32 text-right text-sm">Valuation</span>
          </>
        )}
      </div>
      {rows.map((r) => (
        <div
          key={r.team}
          className={cn(
            "relative flex items-center gap-4 overflow-hidden rounded-3xl border bg-card px-5 py-4 shadow-soft",
            r.rank === 1 && "border-primary/40",
          )}
        >
          {!revealed && (
            <div
              className="absolute inset-y-0 left-0 bg-chart-2/15 transition-[width] duration-700"
              style={{ width: `${(r.arr / max) * 100}%` }}
            />
          )}
          <span className="display tabular relative w-14 text-5xl leading-none">{r.rank}</span>
          <span className="relative">
            <Move delta={moves[r.team]} />
          </span>
          <span className="relative flex-1 truncate text-3xl font-medium">{r.name}</span>
          <span className="display tabular relative w-32 text-right text-4xl">{formatCr(r.arr)}</span>
          <span className="tabular relative w-24 text-right text-3xl text-muted-foreground">
            {r.trust_avg.toFixed(0)}
          </span>
          {revealed && (
            <>
              <span className="tabular relative w-28 text-right text-3xl text-muted-foreground">
                {r.uod !== undefined ? r.uod.toFixed(0) : ""}
              </span>
              <span className="display tabular relative w-32 text-right text-4xl">
                {r.nev !== undefined ? formatCr(r.nev) : ""}
              </span>
            </>
          )}
        </div>
      ))}
    </section>
  )
}
