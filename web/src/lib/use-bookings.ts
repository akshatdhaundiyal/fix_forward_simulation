import { useCallback, useEffect, useRef, useState } from "react"
import { fetchBookings } from "./api"
import type { BookingsView } from "./bookings"

// Places move slowly, so bookings are read at a multiple of the poll interval.
export const BOOKINGS_POLL_MULTIPLE = 5

export interface BookingsState {
  view: BookingsView | null
  offline: boolean
  refresh: () => Promise<void>
}

// Polls only while the component using it is mounted, which is while the
// Stakeholders tab is open.
export function useBookings(code: string, pollSeconds: number): BookingsState {
  const [view, setView] = useState<BookingsView | null>(null)
  const [offline, setOffline] = useState(false)
  const alive = useRef(true)

  const refresh = useCallback(async () => {
    try {
      const next = await fetchBookings(code)
      if (!alive.current) return
      setView(next)
      setOffline(false)
    } catch {
      if (alive.current) setOffline(true)
    }
  }, [code])

  useEffect(() => {
    alive.current = true
    let timer: ReturnType<typeof setTimeout> | undefined
    const loop = async () => {
      await refresh()
      if (alive.current) timer = setTimeout(loop, pollSeconds * BOOKINGS_POLL_MULTIPLE * 1000)
    }
    void loop()
    return () => {
      alive.current = false
      if (timer) clearTimeout(timer)
    }
  }, [refresh, pollSeconds])

  return { view, offline, refresh }
}
