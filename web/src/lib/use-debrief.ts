import { useEffect, useState } from "react"
import { fetchDebriefWith, type DebriefData } from "./debrief"

const RETRY_MS = 3000

// Loads the debrief once the final reveal has happened, retrying until it lands.
// Before the reveal it asks for nothing, so no hidden series is requested early.
export function useDebrief(revealed: boolean): DebriefData | null {
  const [data, setData] = useState<DebriefData | null>(null)
  useEffect(() => {
    if (!revealed || data) return
    let stopped = false
    let timer: ReturnType<typeof setTimeout> | undefined
    const load = () =>
      fetchDebriefWith()
        .then((d) => {
          if (stopped) return
          if (d) setData(d)
          else timer = setTimeout(load, RETRY_MS)
        })
        .catch(() => {
          if (!stopped) timer = setTimeout(load, RETRY_MS)
        })
    void load()
    return () => {
      stopped = true
      if (timer) clearTimeout(timer)
    }
  }, [revealed, data])
  return data
}
