import { useEffect, useRef, useState } from "react"
import { createApi } from "@/lib/api"
import type { TeamView } from "@/lib/types"

// The funnel explorer needs slice data, which makes the view large (about 1.5 MB
// for a whole game). It is fetched only while the explorer is open, over a
// quarter of days, and refreshed at a multiple of the normal poll interval.
export const EXPLORER_DAYS = 91
const REFRESH_MULTIPLE = 5

export type HeavyState =
  | { status: "loading" }
  | { status: "ready"; view: TeamView }
  | { status: "error"; view?: TeamView }

export function useHeavyView(code: string, pollSeconds: number): HeavyState {
  const [state, setState] = useState<HeavyState>({ status: "loading" })
  const etag = useRef<string | null>(null)
  const latest = useRef<TeamView | undefined>(undefined)

  useEffect(() => {
    const api = createApi()
    let stopped = false
    let timer: ReturnType<typeof setTimeout> | undefined

    const load = async () => {
      if (document.visibilityState === "hidden") return
      try {
        const result = await api.view(code, { days: EXPLORER_DAYS, slices: true, etag: etag.current })
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
  }, [code, pollSeconds])

  return state
}
