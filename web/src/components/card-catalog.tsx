import { Plus } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { useActions } from "@/components/actions"
import { STAGE_LABELS, formatCr } from "@/lib/format"
import { latestUtility } from "@/lib/queue"
import { SEGMENT_NAMES, type Card, type CardStatus, type Report, type TeamView } from "@/lib/types"
import { cn } from "@/lib/utils"

const STATUS_LABEL: Record<CardStatus, string> = {
  available: "Available",
  queued: "In your queue",
  shipped: "Shipped",
  done_this_quarter: "Done this quarter",
  apply: "Applications open",
  awarded: "Awarded",
}

const SEG_DOT: Record<string, string> = {
  W: "bg-chart-5",
  M: "bg-chart-3",
  S: "bg-chart-2",
}

function TrustChips({ effect }: { effect: Card["trust_effect"] }) {
  const entries = Object.entries(effect).filter(([, v]) => v)
  if (entries.length === 0) return null
  return (
    <>
      {entries.map(([seg, v]) => (
        <Badge key={seg} variant="outline" className="tabular font-mono">
          trust {seg} {(v as number) > 0 ? "+" : ""}
          {v}
        </Badge>
      ))}
    </>
  )
}

function CatalogCard({ card, reports, b1WindowOpen }: { card: Card; reports: Report[]; b1WindowOpen: boolean }) {
  const { run, busy } = useActions()
  const utility = latestUtility(reports, card)
  const canQueue = card.status === "available"
  const canApply = card.status === "apply"

  return (
    <article
      className={cn(
        "flex flex-col gap-3 rounded-2xl border bg-background p-4 transition-shadow hover:shadow-soft",
        !canQueue && !canApply && "opacity-70",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h3 className="text-sm font-semibold leading-snug">{card.name}</h3>
          <p className="flex items-center gap-2 text-xs text-muted-foreground">
            {card.seg ? (
              <>
                <span className={cn("size-2 rounded-full", SEG_DOT[card.seg])} />
                {SEGMENT_NAMES[card.seg]}
              </>
            ) : (
              "Whole company"
            )}
            {card.stage && <span>· {STAGE_LABELS[card.stage] ?? card.stage}</span>}
          </p>
        </div>
        <Badge variant={canQueue ? "secondary" : "outline"} className="shrink-0">
          {STATUS_LABEL[card.status]}
        </Badge>
      </div>

      <div className="flex flex-wrap items-center gap-2 text-xs">
        <Badge variant="outline" className="tabular font-mono">
          {card.cost} BU
        </Badge>
        {card.pitch_arr > 0 && (
          <Badge variant="outline" className="tabular font-mono">
            pitch {formatCr(card.pitch_arr)}
          </Badge>
        )}
        <TrustChips effect={card.trust_effect} />
        {utility && (
          <Badge className="tabular font-mono" title={`From your day ${utility.day} report`}>
            utility {utility.value}
          </Badge>
        )}
      </div>

      {(canQueue || canApply) && (
        <Button
          size="sm"
          variant={canQueue ? "default" : "outline"}
          className="w-fit rounded-full"
          disabled={busy || (canApply && !b1WindowOpen)}
          onClick={() =>
            void run(canApply ? { type: "apply_b1" } : { type: "queue_add", card: card.id }, canApply ? "Application sent" : undefined)
          }
        >
          {canApply ? (
            "Apply for this contract"
          ) : (
            <>
              <Plus /> Add to queue
            </>
          )}
        </Button>
      )}
    </article>
  )
}

export function CardCatalog({ view }: { view: TeamView }) {
  const initiatives = view.cards.filter((c) => c.seg !== null || c.bespoke || c.stage !== null)
  const standing = view.cards.filter((c) => !initiatives.includes(c))
  return (
    <section className="flex flex-col gap-4">
      <div>
        <p className="eyebrow">Initiatives</p>
        <p className="text-sm text-muted-foreground">
          New cards unlock each quarter. Order a segment report to see how useful each one is.
        </p>
      </div>
      <div className="grid gap-3 lg:grid-cols-2">
        {initiatives.map((c) => (
          <CatalogCard key={c.id} card={c} reports={view.reports} b1WindowOpen={view.b1.window_open} />
        ))}
      </div>
      {standing.length > 0 && (
        <>
          <p className="eyebrow mt-2">Platform and customers</p>
          <div className="grid gap-3 lg:grid-cols-2">
            {standing.map((c) => (
              <CatalogCard key={c.id} card={c} reports={view.reports} b1WindowOpen={view.b1.window_open} />
            ))}
          </div>
        </>
      )}
    </section>
  )
}
