import { useState } from "react"
import { Brand } from "@/components/brand"
import { Gate } from "@/components/admin/gate"
import { DeclineChecklist } from "@/components/stakeholder/decline"
import { CtoLights } from "@/components/stakeholder/cto-lights"
import { BookingQueue } from "@/components/stakeholder/queue"
import { ScriptCard, TeamFacts } from "@/components/stakeholder/script-card"
import { Skeleton } from "@/components/ui/skeleton"
import { Toaster } from "@/components/ui/sonner"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import {
  createStakeholderApi,
  forgetStakeholderPassword,
  recallStakeholderPassword,
  rememberStakeholderPassword,
} from "@/lib/stakeholder-api"
import { queueFor, ROLE_LABEL, teamFor, type RoleId } from "@/lib/stakeholder"
import { useStakeholder } from "@/lib/use-stakeholder"

const ROLES: RoleId[] = ["vp_sales", "whale_lead", "cto"]

async function checkPassword(password: string): Promise<"ok" | "wrong" | "offline"> {
  const r = await createStakeholderApi(password).board()
  return r.ok ? "ok" : r.unauthorized ? "wrong" : "offline"
}

function Dashboard({ password, onSignOut }: { password: string; onSignOut: () => void }) {
  const state = useStakeholder(password, onSignOut)
  const [role, setRole] = useState<RoleId>("vp_sales")
  const { board } = state

  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-4 px-4 pb-16 pt-6 sm:px-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <Brand sub="Stakeholders" />
        <div className="flex items-center gap-4">
          {board && <p className="eyebrow">Quarter {board.quarter} · week {board.clock.week}</p>}
          <button onClick={onSignOut} className="eyebrow underline-offset-4 hover:underline">
            Sign out
          </button>
        </div>
      </header>
      {state.offline && <p className="text-sm text-warning">Could not reach the server. Showing the last known board.</p>}
      {board ? (
        <>
          <div className="flex flex-col gap-2">
            <p className="eyebrow">You are playing</p>
            <ToggleGroup type="single" variant="outline" value={role} onValueChange={(v) => v && setRole(v as RoleId)} className="w-fit rounded-full bg-background p-1">
              {ROLES.map((r) => (
                <ToggleGroupItem key={r} value={r} className="rounded-full px-5 data-[state=on]:bg-primary data-[state=on]:text-primary-foreground">
                  {ROLE_LABEL[r]}
                </ToggleGroupItem>
              ))}
            </ToggleGroup>
          </div>
          <RoleView role={role} state={state} />
          <DeclineChecklist board={board} state={state} />
        </>
      ) : (
        <Skeleton className="h-64 w-full rounded-2xl" />
      )}
      <Toaster position="bottom-right" />
    </main>
  )
}

// The role picker changes what the screen leads with and nothing else.
function RoleView({ role, state }: { role: RoleId; state: ReturnType<typeof useStakeholder> }) {
  const board = state.board
  if (!board) return null
  const card = board.roles.find((r) => r.role === role)
  const next = queueFor(board, role)[0]
  const meeting = next ? teamFor(board, next.team) : undefined
  const hasLines = board.teams.some((t) => t.cto_line)
  return (
    <div className="flex flex-col gap-4">
      {role === "cto" && <CtoLights teams={board.teams} hasLines={hasLines} />}
      <div className="grid items-start gap-4 lg:grid-cols-2">
        <BookingQueue board={board} role={role} state={state} />
        <div className="flex flex-col gap-4">
          {role === "whale_lead" && meeting && <TeamFacts team={meeting} />}
          {card && <ScriptCard role={card} quarter={board.quarter} />}
        </div>
      </div>
    </div>
  )
}

export function StakeholderPage() {
  const [password, setPassword] = useState<string | null>(() => recallStakeholderPassword())
  const signOut = () => {
    forgetStakeholderPassword()
    setPassword(null)
  }
  if (!password) {
    return (
      <Gate
        title="Stakeholder"
        check={checkPassword}
        onPassword={(p) => {
          rememberStakeholderPassword(p)
          setPassword(p)
        }}
      />
    )
  }
  return <Dashboard password={password} onSignOut={signOut} />
}
