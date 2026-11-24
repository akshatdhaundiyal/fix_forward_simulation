import { describe, expect, it } from "vitest"
import {
  codeFromHash,
  consoleUrl,
  forgetCode,
  normalizeCode,
  recallCode,
  rememberCode,
} from "./team-code"

function memoryStore() {
  const data = new Map<string, string>()
  return {
    getItem: (k: string) => data.get(k) ?? null,
    setItem: (k: string, v: string) => void data.set(k, v),
    removeItem: (k: string) => void data.delete(k),
  }
}

describe("team code", () => {
  it("normalizes case, spaces and dashes", () => {
    expect(normalizeCode(" ab c-d12 ")).toBe("ABCD12")
  })

  it("reads the code from a URL hash and treats an empty hash as none", () => {
    expect(codeFromHash("#abc123")).toBe("ABC123")
    expect(codeFromHash("")).toBeNull()
    expect(codeFromHash("#")).toBeNull()
  })

  it("remembers and forgets a code through a store", () => {
    const store = memoryStore()
    expect(recallCode(store)).toBeNull()
    rememberCode("ABC123", store)
    expect(recallCode(store)).toBe("ABC123")
    forgetCode(store)
    expect(recallCode(store)).toBeNull()
  })

  it("works when storage throws or is missing", () => {
    const broken = {
      getItem: () => {
        throw new Error("blocked")
      },
      setItem: () => {
        throw new Error("blocked")
      },
      removeItem: () => {
        throw new Error("blocked")
      },
    }
    expect(recallCode(broken)).toBeNull()
    expect(() => rememberCode("ABC123", broken)).not.toThrow()
    expect(() => forgetCode(broken)).not.toThrow()
    expect(recallCode(null)).toBeNull()
  })

  it("builds a relative console link", () => {
    expect(consoleUrl("ABC123")).toBe("team.html#ABC123")
  })
})
