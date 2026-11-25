import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { toast } from "sonner"
import { createStakeholderApi, type StakeholderApi, type StakeholderResult } from "./stakeholder-api"
import type { Board } from "./stakeholder"

// Used before the first board arrives; afterwards the server's poll hint decides.
const FIRST_POLL_MS = 3000

export interface StakeholderState {
  board: Board | null
  offline: boolean
  api: StakeholderApi
  // Runs an operation, shows the server's message on refusal, refreshes, and
  // resolves true when the server accepted it.
  run: (op: () => Promise<StakeholderResult>, success?: string) => Promise<boolean>
}

// Polls the stakeholder board while signed in. A 401, on the first call or
// mid-session, calls onUnauthorized.
export function useStakeholder(password: string, onUnauthorized: () => void): StakeholderState {
  const api = useMemo(() => createStakeholderApi(password), [password])
  const [board, setBoard] = useState<Board | null>(null)
  const [offline, setOffline] = useState(false)
  const pending = useRef(false)
  const nextMs = useRef(FIRST_POLL_MS)
  const unauthorized = useRef(onUnauthorized)
  unauthorized.current = onUnauthorized

  const refresh = useCallback(async () => {
    const result = await api.board()
    if (!result.ok) {
      if (result.unauthorized) unauthorized.current()
      else setOffline(true)
      return
    }
    setOffline(false)
    setBoard(result.data)
    nextMs.current = result.data.clock.poll_seconds * 1000
  }, [api])

  useEffect(() => {
    let stopped = false
    let timer: ReturnType<typeof setTimeout> | undefined
    const loop = async () => {
      await refresh()
      if (!stopped) timer = setTimeout(loop, nextMs.current)
    }
    void loop()
    return () => {
      stopped = true
      if (timer) clearTimeout(timer)
    }
  }, [refresh])

  const run = useCallback(
    async (op: () => Promise<StakeholderResult>, success?: string) => {
      // One operation at a time, so a double click cannot send a result twice.
      if (pending.current) return false
      pending.current = true
      let result: StakeholderResult
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

  return { board, offline, api, run }
}
