import { useEffect, useRef, useState } from "react"
import { REQUEST_TIMEOUT_MS } from "./api"
import { rankMoves, sortRows, type ProjectorFeed, type ProjectorRow } from "./projector"

export interface ProjectorState {
  feed: ProjectorFeed | null
  rows: ProjectorRow[]
  moves: Record<number, number>
  offline: boolean
}

// Used only before the first feed arrives; afterwards the server's
// projector_poll_seconds decides.
const FIRST_POLL_MS = 2000

async function fetchProjector(): Promise<ProjectorFeed> {
  const resp = await fetch("api/projector", { cache: "no-store", signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS) })
  if (!resp.ok) throw new Error(`projector ${resp.status}`)
  return (await resp.json()) as ProjectorFeed
}

// Polls the room feed. A failed poll keeps the last picture and marks it offline.
export function useProjector(): ProjectorState {
  const [state, setState] = useState<ProjectorState>({ feed: null, rows: [], moves: {}, offline: false })
  const previous = useRef<ProjectorRow[] | null>(null)

  useEffect(() => {
    let stopped = false
    let timer: ReturnType<typeof setTimeout> | undefined
    let nextMs = FIRST_POLL_MS

    const tick = async () => {
      try {
        const feed = await fetchProjector()
        if (stopped) return
        const rows = sortRows(feed.rows, feed.revealed)
        const moves = rankMoves(previous.current, rows)
        previous.current = rows
        nextMs = feed.clock.projector_poll_seconds * 1000
        setState({ feed, rows, moves, offline: false })
      } catch {
        if (!stopped) setState((s) => ({ ...s, moves: {}, offline: true }))
      }
      if (!stopped) timer = setTimeout(tick, nextMs)
    }
    void tick()
    return () => {
      stopped = true
      if (timer) clearTimeout(timer)
    }
  }, [])

  return state
}
