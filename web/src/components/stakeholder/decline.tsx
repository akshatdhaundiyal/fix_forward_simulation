import { useState } from "react"
import { Button } from "@/components/ui/button"
import { DECLINE_ITEMS, declineTicks, type Board } from "@/lib/stakeholder"
import type { StakeholderState } from "@/lib/use-stakeholder"

const ITEMS = ["First actor satisfied", "Second actor satisfied", "Third actor satisfied"]

// The decline conversation: three actors, three ticks. Only the number of ticks
// is sent. The server accepts one entry per team and says so on a repeat.
export function DeclineChecklist({ board, state }: { board: Board; state: StakeholderState }) {
  const [team, setTeam] = useState("")
  const [ticked, setTicked] = useState<boolean[]>(Array(DECLINE_ITEMS).fill(false))
  const open = board.teams.filter((t) => !t.declined)
  const ticks = declineTicks(ticked)

  async function send() {
    if (!team) return
    const name = board.teams.find((t) => String(t.team) === team)?.name ?? `team ${team}`
    const ok = await state.run(() => state.api.decline(Number(team), ticks), `Result entered for ${name}`)
    if (ok) {
      setTeam("")
      setTicked(Array(DECLINE_ITEMS).fill(false))
    }
  }

  return (
    <section className="surface flex flex-col gap-4 p-5">
      <div>
        <p className="eyebrow">Decline conversation</p>
        <h2 className="display text-2xl">Enter a result</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          For teams that did not apply for the bespoke contract. Tick what the team did in the room.
          One entry per team. {board.teams.length - open.length} of {board.teams.length} entered.
        </p>
      </div>
      <select
        value={team}
        onChange={(e) => setTeam(e.target.value)}
        aria-label="Team"
        className="h-11 w-full max-w-xs rounded-full border bg-background px-4 text-sm"
      >
        <option value="">Choose a team</option>
        {board.teams.map((t) => (
          <option key={t.team} value={t.team} disabled={t.declined}>
            {t.name}{t.declined ? " (entered)" : ""}
          </option>
        ))}
      </select>
      <ul className="flex flex-col gap-2">
        {ITEMS.map((label, i) => (
          <li key={label}>
            <label className="flex cursor-pointer items-center gap-3 rounded-2xl border bg-background px-4 py-3">
              <input
                type="checkbox"
                className="size-5 accent-primary"
                checked={ticked[i]}
                onChange={(e) => setTicked((prev) => prev.map((v, j) => (j === i ? e.target.checked : v)))}
              />
              <span>{label}</span>
            </label>
          </li>
        ))}
      </ul>
      <div className="flex flex-wrap items-center gap-3">
        <Button className="rounded-full" disabled={!team} onClick={() => void send()}>
          Send {ticks} of {DECLINE_ITEMS}
        </Button>
        {ticks < DECLINE_ITEMS - 1 && team && (
          <p className="text-sm text-muted-foreground">Fewer than two ticks lowers the team's Whale trust.</p>
        )}
      </div>
    </section>
  )
}
