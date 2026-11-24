import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import type { AdminState } from "@/lib/use-admin"
import { Confirm } from "./confirm"

// Paths the server accepts, offered as suggestions. The server is the judge.
const PATHS = ["seg.W.trust", "seg.M.trust", "seg.S.trust", "uod", "penalty", "bespoke_arr", "quality"]

export function EditState({ admin }: { admin: AdminState }) {
  const { status, api, run } = admin
  const [team, setTeam] = useState("1")
  const [path, setPath] = useState("seg.W.trust")
  const [value, setValue] = useState("")
  const [reason, setReason] = useState("")
  const [confirming, setConfirming] = useState(false)
  if (!status) return null

  const numeric = value.trim() !== "" && !Number.isNaN(Number(value))
  const parsed: number | string = numeric ? Number(value) : value
  const ready = value.trim() !== "" && reason.trim() !== ""

  return (
    <section className="surface flex flex-col gap-4 p-5">
      <div>
        <p className="eyebrow">Edit a team's state</p>
        <p className="text-sm text-muted-foreground">Every edit is logged with its reason. Use it to fix a mistake, not to play.</p>
      </div>
      <div className="flex flex-wrap gap-3">
        <label className="flex flex-col gap-1.5 text-xs text-muted-foreground">
          Team
          <select value={team} onChange={(e) => setTeam(e.target.value)} className="h-9 rounded-md border bg-background px-3 text-sm text-foreground">
            {status.teams.map((t) => (
              <option key={t.team} value={t.team}>
                {t.team} · {t.name}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1.5 text-xs text-muted-foreground">
          Field
          <Input list="admin-edit-paths" value={path} onChange={(e) => setPath(e.target.value)} className="h-9 w-44 bg-background font-mono" />
          <datalist id="admin-edit-paths">
            {PATHS.map((p) => (
              <option key={p} value={p} />
            ))}
          </datalist>
        </label>
        <label className="flex flex-col gap-1.5 text-xs text-muted-foreground">
          New value
          <Input value={value} onChange={(e) => setValue(e.target.value)} className="h-9 w-28 bg-background font-mono" />
        </label>
        <label className="flex min-w-60 flex-1 flex-col gap-1.5 text-xs text-muted-foreground">
          Reason (required)
          <Input value={reason} onChange={(e) => setReason(e.target.value)} className="h-9 bg-background" />
        </label>
      </div>
      <Button className="w-fit rounded-full" disabled={!ready} onClick={() => setConfirming(true)}>
        Apply edit
      </Button>
      <Confirm
        open={confirming}
        title="Edit this team's state?"
        action="Apply the edit"
        onCancel={() => setConfirming(false)}
        onConfirm={async () => {
          setConfirming(false)
          if (await run(() => api.edit(Number(team), path, parsed, reason), "Edit applied and logged")) {
            setValue("")
            setReason("")
          }
        }}
      >
        Team {team}: set {path} to {String(parsed)}. Reason: {reason}. The edit is written to the event log and cannot be
        undone except by another edit or a snapshot restore.
      </Confirm>
    </section>
  )
}
