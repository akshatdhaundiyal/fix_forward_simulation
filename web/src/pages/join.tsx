import { useState } from "react"
import { ArrowRight } from "lucide-react"
import { Brand } from "@/components/brand"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { consoleUrl, normalizeCode, recallCode, rememberCode } from "@/lib/team-code"

type Check = "idle" | "checking" | "unknown" | "offline"

export function JoinPage() {
  const [code, setCode] = useState(() => recallCode() ?? "")
  const [check, setCheck] = useState<Check>("idle")

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    const clean = normalizeCode(code)
    if (!clean) return
    setCheck("checking")
    try {
      // days=1 keeps the check small; a wrong code gets the same 404 every time.
      const resp = await fetch(`api/team/${clean}/view?days=1`, { cache: "no-store" })
      if (resp.status === 404) {
        setCheck("unknown")
        return
      }
      if (!resp.ok) {
        setCheck("offline")
        return
      }
      rememberCode(clean)
      window.location.assign(consoleUrl(clean))
    } catch {
      setCheck("offline")
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-xl flex-col justify-center gap-8 px-6 py-16">
      <Brand sub="Q4 2026" />
      <div className="surface flex flex-col gap-6 p-8 sm:p-10">
        <div className="flex flex-col gap-3">
          <p className="eyebrow">Live product simulation</p>
          <h1 className="display text-4xl leading-tight sm:text-5xl">Enter your team code</h1>
          <p className="text-sm text-muted-foreground">
            You will find it on the card your host gave your team.
          </p>
        </div>
        <form onSubmit={submit} className="flex flex-col gap-3 sm:flex-row">
          <Input
            value={code}
            onChange={(e) => {
              setCode(normalizeCode(e.target.value))
              setCheck("idle")
            }}
            autoFocus
            autoComplete="off"
            autoCapitalize="characters"
            spellCheck={false}
            maxLength={12}
            placeholder="ABC123"
            aria-label="Team code"
            aria-invalid={check === "unknown"}
            className="h-12 rounded-full bg-background px-5 font-mono text-lg tracking-[0.3em] uppercase"
          />
          <Button
            type="submit"
            size="lg"
            disabled={!code || check === "checking"}
            className="h-12 rounded-full px-6"
          >
            {check === "checking" ? "Checking" : "Open console"}
            <ArrowRight />
          </Button>
        </form>
        <p
          role="status"
          className={
            "min-h-5 text-sm " + (check === "idle" || check === "checking" ? "text-transparent" : "text-destructive")
          }
        >
          {check === "unknown" && "That code did not match a team. Check the card and try again."}
          {check === "offline" && "Could not reach the game server. Check you are on the event network."}
        </p>
      </div>
    </main>
  )
}
