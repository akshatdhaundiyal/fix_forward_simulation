import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { toast } from "sonner"
import { createAdminApi, type AdminApi, type AdminResult, type AdminStatus, type SnapshotInfo } from "./admin-api"

const FIRST_POLL_MS = 3000

export interface AdminState {
  status: AdminStatus | null
  snapshots: SnapshotInfo[]
  offline: boolean
  api: AdminApi
  // Runs an operation, shows the server's message on refusal, refreshes, and
  // resolves true when the server accepted it.
  run: (op: () => Promise<AdminResult>, success?: string) => Promise<boolean>
}

// Polls the operator's view while signed in. A 401 calls onUnauthorized.
export function useAdmin(password: string, onUnauthorized: () => void): AdminState {
  const api = useMemo(() => createAdminApi(password), [password])
  const [status, setStatus] = useState<AdminStatus | null>(null)
  const [snapshots, setSnapshots] = useState<SnapshotInfo[]>([])
  const [offline, setOffline] = useState(false)
  const pending = useRef(false)
  const unauthorized = useRef(onUnauthorized)
  unauthorized.current = onUnauthorized

  const refresh = useCallback(async () => {
    const [s, snaps] = await Promise.all([api.status(), api.snapshots()])
    if (!s.ok) {
      if (s.unauthorized) unauthorized.current()
      else setOffline(true)
      return
    }
    setOffline(false)
    setStatus(s.data)
    if (snaps.ok) setSnapshots(snaps.data.snapshots)
  }, [api])

  useEffect(() => {
    let stopped = false
    let timer: ReturnType<typeof setTimeout> | undefined
    const loop = async () => {
      await refresh()
      if (!stopped) timer = setTimeout(loop, FIRST_POLL_MS)
    }
    void loop()
    return () => {
      stopped = true
      if (timer) clearTimeout(timer)
    }
  }, [refresh])

  const run = useCallback(
    async (op: () => Promise<AdminResult>, success?: string) => {
      // One operation at a time: a second click while one is in flight would
      // repeat a clock extension or an incident trigger.
      if (pending.current) return false
      pending.current = true
      let result: AdminResult
      try {
        result = await op()
      } finally {
        pending.current = false
      }
      if (!result.ok) {
        if (result.unauthorized) unauthorized.current()
        else toast.error(result.error)
        return false
      }
      if (success) toast.success(success)
      await refresh()
      return true
    },
    [refresh],
  )

  return { status, snapshots, offline, api, run }
}
