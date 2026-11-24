import { useEffect, useState } from "react"
import { fetchCalendar } from "./api"
import type { Calendar } from "./types"

// The calendar is fixed for the whole game. A failed fetch leaves it null, the
// screens that use it do not draw it, and the fetch is retried until it lands.
const RETRY_MS = 3000

export function useCalendar(): Calendar | null {
  const [calendar, setCalendar] = useState<Calendar | null>(null)
  useEffect(() => {
    let stopped = false
    let timer: ReturnType<typeof setTimeout> | undefined
    const load = () =>
      fetchCalendar()
        .then((c) => !stopped && setCalendar(c))
        .catch(() => {
          if (!stopped) timer = setTimeout(load, RETRY_MS)
        })
    void load()
    return () => {
      stopped = true
      if (timer) clearTimeout(timer)
    }
  }, [])
  return calendar
}
