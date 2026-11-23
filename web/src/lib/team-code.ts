// The team code travels in the URL hash (never sent to the server, so it stays
// out of request logs) and is remembered in localStorage as a convenience only.

const STORAGE_KEY = "fixforward.teamCode"

type Store = Pick<Storage, "getItem" | "setItem" | "removeItem">

export function normalizeCode(raw: string): string {
  return raw.toUpperCase().replace(/[^A-Z0-9]/g, "")
}

export function codeFromHash(hash: string): string | null {
  const code = normalizeCode(hash.replace(/^#/, ""))
  return code === "" ? null : code
}

function defaultStore(): Store | null {
  try {
    return globalThis.localStorage ?? null
  } catch {
    return null
  }
}

export function recallCode(store: Store | null = defaultStore()): string | null {
  try {
    const stored = store?.getItem(STORAGE_KEY)
    return stored ? normalizeCode(stored) || null : null
  } catch {
    return null
  }
}

export function rememberCode(code: string, store: Store | null = defaultStore()): void {
  try {
    store?.setItem(STORAGE_KEY, code)
  } catch {
    // Storage can be blocked or full; the console works without it.
  }
}

export function forgetCode(store: Store | null = defaultStore()): void {
  try {
    store?.removeItem(STORAGE_KEY)
  } catch {
    // Nothing to do.
  }
}

export function consoleUrl(code: string): string {
  return `team.html#${code}`
}
