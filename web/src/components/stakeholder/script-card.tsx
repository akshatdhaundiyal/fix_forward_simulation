import { Check, X } from "lucide-react"
import { FACT_LABELS, type BoardRole, type BoardTeam } from "@/lib/stakeholder"

// The current quarter's card for a role: what to say without being asked, and
// what to say only if asked. Nothing here states a score, risk or debt figure.
export function ScriptCard({ role, quarter }: { role: BoardRole; quarter: number }) {
  return (
    <section className="surface flex flex-col gap-5 p-5">
      <div>
        <p className="eyebrow">Quarter {quarter} script</p>
        <h2 className="display text-2xl">{role.title}</h2>
      </div>
      {role.unprompted && (
        <div className="flex flex-col gap-1">
          <p className="eyebrow">Say unprompted</p>
          <p className="text-lg leading-snug">{role.unprompted}</p>
        </div>
      )}
      {role.after && (
        <div className="flex flex-col gap-1">
          <p className="eyebrow">Then add</p>
          <p className="text-lg leading-snug">{role.after}</p>
        </div>
      )}
      <div className="flex flex-col gap-3">
        <p className="eyebrow">Say only if asked</p>
        <ul className="flex flex-col gap-3">
          {role.asked.map((qa) => (
            <li key={qa.question} className="rounded-2xl border bg-background px-4 py-3">
              <p className="text-sm italic text-muted-foreground">{qa.question}</p>
              <p className="mt-1">{qa.answer}</p>
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}

// For the Whale lead: three yes or no facts about the team in the room, plus
// any line this quarter's card ties to them. Nothing else about the team.
export function TeamFacts({ team }: { team: BoardTeam }) {
  return (
    <section className="surface flex flex-col gap-4 p-5">
      <div>
        <p className="eyebrow">In the room</p>
        <h2 className="display text-2xl">{team.name}</h2>
      </div>
      <ul className="flex flex-col gap-2">
        {FACT_LABELS.map(({ key, label }) => {
          const yes = team.whale.facts[key]
          return (
            <li key={key} className="flex items-center gap-3 text-sm">
              <span
                className={
                  yes
                    ? "flex size-6 items-center justify-center rounded-full bg-success/15 text-success"
                    : "flex size-6 items-center justify-center rounded-full bg-muted text-muted-foreground"
                }
              >
                {yes ? <Check className="size-3.5" /> : <X className="size-3.5" />}
              </span>
              <span className="flex-1">{label}</span>
              <span className="font-medium">{yes ? "Yes" : "No"}</span>
            </li>
          )
        })}
      </ul>
      {team.whale.lines.length > 0 && (
        <div className="flex flex-col gap-2">
          <p className="eyebrow">Say to this team</p>
          {team.whale.lines.map((line) => (
            <p key={line} className="rounded-2xl border border-primary bg-background px-4 py-3 text-lg leading-snug">
              {line}
            </p>
          ))}
        </div>
      )}
    </section>
  )
}
