import { Award, Clock3, FileSignature, XCircle } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { contractState, type ContractState } from "@/lib/contract"
import type { Calendar, TeamView } from "@/lib/types"

const COPY: Record<ContractState, { label: string; text: (c: Calendar) => string; icon: typeof Award }> = {
  "not-open": {
    label: "Not open yet",
    icon: Clock3,
    text: (c) =>
      `Whale Alpha's bespoke contract opens for applications in week ${c.contract_window.first}. Whale trust decides who wins it.`,
  },
  open: {
    label: "Applications open",
    icon: FileSignature,
    text: (c) =>
      `Apply from the Roadmap tab before the end of week ${c.contract_window.last}. The teams with the highest Whale trust win.`,
  },
  applied: {
    label: "Application sent",
    icon: FileSignature,
    text: () => "Your application is in. The result is announced when applications close.",
  },
  awarded: {
    label: "Awarded",
    icon: Award,
    text: () => "You won the contract. Its build is in your queue, and it costs your team build time every week once shipped.",
  },
  "not-awarded": {
    label: "Not awarded",
    icon: XCircle,
    text: () => "Your team did not win the bespoke contract.",
  },
}

export function ContractPanel({ b1, week, calendar }: { b1: TeamView["b1"]; week: number; calendar: Calendar | null }) {
  if (!calendar) return null
  const state = contractState(b1, week, calendar)
  const { label, text, icon: Icon } = COPY[state]
  return (
    <section className="surface flex items-start gap-4 p-5">
      <Icon className="mt-0.5 size-5 shrink-0 text-muted-foreground" />
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-2">
          <p className="eyebrow">Whale contract</p>
          <Badge variant={state === "awarded" ? "default" : "outline"}>{label}</Badge>
        </div>
        <p className="text-sm text-muted-foreground">{text(calendar)}</p>
      </div>
    </section>
  )
}
