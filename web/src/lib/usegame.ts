import { useEffect, useMemo, useSyncExternalStore } from "react"
import { createApi } from "./api"
import { Feed, type FeedState } from "./feed"

// Polls the server for one team and exposes the latest state and an action sender.
export function useGame(code: string): { state: FeedState; feed: Feed } {
  const feed = useMemo(() => new Feed(code, createApi()), [code])

  useEffect(() => {
    let stopped = false
    let timer: ReturnType<typeof setTimeout> | undefined
    const loop = async () => {
      await feed.refresh()
      if (!stopped && feed.state.status !== "invalid-code") {
        timer = setTimeout(loop, feed.pollMs())
      }
    }
    void loop()
    return () => {
      stopped = true
      if (timer) clearTimeout(timer)
    }
  }, [feed])

  const state = useSyncExternalStore(
    (listener) => feed.subscribe(listener),
    () => feed.state,
  )
  return { state, feed }
}
