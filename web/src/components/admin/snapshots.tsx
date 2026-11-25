import { useState } from "react"
import { Camera, RefreshCw, RotateCcw } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import type { SnapshotInfo } from "@/lib/admin-api"
import type { AdminState } from "@/lib/use-admin"
import { Confirm } from "./confirm"

export function Snapshots({ admin }: { admin: AdminState }) {
  const { status, snapshots, api, run } = admin
  const [restoring, setRestoring] = useState<SnapshotInfo | null>(null)
  const [reloading, setReloading] = useState(false)
  if (!status) return null
  const recent = [...snapshots].reverse().slice(0, 8)

  return (
    <section className="surface flex flex-col gap-4 p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="eyebrow">Snapshots and the log</p>
          <p className="text-sm text-muted-foreground">
            The event log is the record. A snapshot is a restore point written every few seconds.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" className="rounded-full bg-background" onClick={() => void run(() => api.snapshotNow(), "Snapshot taken")}>
            <Camera /> Snapshot now
          </Button>
          <Button variant="outline" className="rounded-full bg-background" onClick={() => setReloading(true)}>
            <RefreshCw /> Reload from log
          </Button>
        </div>
      </div>

      {recent.length === 0 ? (
        <p className="text-sm text-muted-foreground">No snapshots yet.</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {recent.map((s) => (
            <li key={s.id} className="flex items-center gap-3 rounded-2xl border bg-background px-4 py-2.5">
              <span className="font-mono text-xs">{s.id}</span>
              <Badge variant="outline">day {s.day}</Badge>
              {s.revealed && <Badge variant="secondary">after reveal</Badge>}
              <Button variant="ghost" size="sm" className="ml-auto rounded-full" onClick={() => setRestoring(s)}>
                <RotateCcw /> Restore
              </Button>
            </li>
          ))}
        </ul>
      )}

      <Confirm
        open={restoring !== null}
        title="Restore this snapshot?"
        action="Restore it"
        onCancel={() => setRestoring(null)}
        onConfirm={() => {
          const s = restoring
          setRestoring(null)
          if (s) void run(() => api.restore(s.id), `Restored to day ${s.day}`)
        }}
      >
        The game rewinds to day {restoring?.day}. Everything teams did after it is dropped, and the server comes back
        paused. The log keeps a record of the rewind.
      </Confirm>
      <Confirm
        open={reloading}
        title="Reload from the log?"
        action="Reload"
        onCancel={() => setReloading(false)}
        onConfirm={() => {
          setReloading(false)
          void run(() => api.reload(), "Reloaded from the log")
        }}
      >
        Rebuilds every team from the event log. Use it after the server reports it cannot write its log. The game comes
        back paused.
      </Confirm>
    </section>
  )
}
