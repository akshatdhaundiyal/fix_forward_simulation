import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react"
import { toast } from "sonner"
import type { Feed } from "@/lib/feed"
import type { TeamAction } from "@/lib/types"

interface Actions {
  // Sends an action and refetches. Resolves true when the server accepted it;
  // a rejection is shown as a toast carrying the server's own message.
  run: (action: TeamAction, success?: string) => Promise<boolean>
  busy: boolean
}

const Ctx = createContext<Actions | null>(null)

export function ActionsProvider({ feed, children }: { feed: Feed; children: ReactNode }) {
  const [inflight, setInflight] = useState(0)

  const run = useCallback(
    async (action: TeamAction, success?: string) => {
      setInflight((n) => n + 1)
      try {
        const outcome = await feed.act(action)
        if (!outcome.ok) {
          toast.error(outcome.error)
          return false
        }
        if (success) toast.success(success)
        return true
      } finally {
        setInflight((n) => n - 1)
      }
    },
    [feed],
  )

  const value = useMemo(() => ({ run, busy: inflight > 0 }), [run, inflight])
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useActions(): Actions {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error("useActions needs an ActionsProvider")
  return ctx
}
