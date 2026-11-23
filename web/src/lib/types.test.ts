import { readFileSync } from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

const root = path.resolve(import.meta.dirname, "../../..")

function hiddenFieldNames(): string[] {
  const config = readFileSync(path.join(root, "config.py"), "utf8")
  const block = config.match(/HIDDEN_FIELD_NAMES\s*=\s*\[([\s\S]*?)\]/)
  if (!block) throw new Error("HIDDEN_FIELD_NAMES not found in config.py")
  return [...block[1].matchAll(/"([^"]+)"/g)].map((m) => m[1].toLowerCase())
}

describe("view types", () => {
  it("name no field the server keeps from a team's browser", () => {
    const source = readFileSync(path.join(import.meta.dirname, "types.ts"), "utf8")
    // Only the shapes the server sends. The action union below the marker holds
    // what a team sends, which may name a cause the team picked.
    const sent = source.split("// Team actions")[0]
    const properties = new Set(
      [...sent.matchAll(/^\s*"?([A-Za-z_][A-Za-z0-9_]*)"?\??:/gm)].map((m) => m[1].toLowerCase()),
    )
    expect(properties.size).toBeGreaterThan(20)
    const leaked = hiddenFieldNames().filter((name) => properties.has(name))
    expect(leaked).toEqual([])
  })
})
