import { useEffect, useState } from "react"
import { fetchCalendar } from "./api"
import type { Calendar } from "./types"

// The calendar is fixed for the whole game. A failed fetch leaves it null and
// the screens that use it simply do not draw it.
export function useCalendar(): Calendar | null {
  const [calendar, setCalendar] = useState<Calendar | null>(null)
  useEffect(() => {
    let stopped = false
    fetchCalendar()
      .then((c) => !stopped && setCalendar(c))
      .catch(() => undefined)
    return () => {
      stopped = true
    }
  }, [])
  return calendar
}
