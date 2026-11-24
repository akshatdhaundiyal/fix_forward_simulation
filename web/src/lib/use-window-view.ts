import { useEffect, useRef, useState } from "react"
import { createApi } from "./api"
import type { TeamView } from "./types"

// Screens that chart a long window (the funnel explorer, operations) fetch a
// larger view than the console's ordinary 28-day poll. A window view is fetched
// only while its screen is open and is refreshed at a multiple of the normal
// poll interval; slice data makes it much larger (about 1.5 MB for a whole game).
const REFRESH_MULTIPLE = 5

export interface WindowOptions {
  days: number
  slices?: boolean
}

export type WindowState =
  | { status: "loading" }
  | { status: "ready"; view: TeamView }
  | { status: "error"; view?: TeamView }

export function useWindowView(code: string, pollSeconds: number, { days, slices }: WindowOptions): WindowState {
  const [state, setState] = useState<WindowState>({ status: "loading" })
  const etag = useRef<string | null>(null)
  const latest = useRef<TeamView | undefined>(undefined)

  useEffect(() => {
    const api = createApi()
    let stopped = false
    let timer: ReturnType<typeof setTimeout> | undefined

    const load = async () => {
      if (document.visibilityState === "hidden") return
      try {
        const result = await api.view(code, { days, slices, etag: etag.current })
        if (stopped) return
        if (result.kind === "ok") {
          etag.current = result.etag
          latest.current = result.view
          setState({ status: "ready", view: result.view })
        } else if (result.kind === "same" && latest.current) {
          setState({ status: "ready", view: latest.current })
        } else if (result.kind !== "same") {
          setState({ status: "error", view: latest.current })
        }
      } catch {
        if (!stopped) setState({ status: "error", view: latest.current })
      }
    }

    const schedule = () => {
      timer = setTimeout(async () => {
        await load()
        if (!stopped) schedule()
      }, pollSeconds * REFRESH_MULTIPLE * 1000)
    }
    const onVisible = () => {
      if (document.visibilityState === "visible") void load()
    }

    void load()
    schedule()
    document.addEventListener("visibilitychange", onVisible)
    return () => {
      stopped = true
      if (timer) clearTimeout(timer)
      document.removeEventListener("visibilitychange", onVisible)
    }
  }, [code, pollSeconds, days, slices])

  return state
}
