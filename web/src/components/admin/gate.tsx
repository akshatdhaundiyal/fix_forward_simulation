import { useState } from "react"
import { ArrowRight } from "lucide-react"
import { Brand } from "@/components/brand"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { createAdminApi } from "@/lib/admin-api"

// Password gate shared by the operator's screen. The password is checked with
// the status route before it is kept for the session.
export function Gate({ title, onPassword, check }: {
  title: string
  onPassword: (password: string) => void
  check?: (password: string) => Promise<"ok" | "wrong" | "offline">
}) {
  const [password, setPassword] = useState("")
  const [state, setState] = useState<"idle" | "checking" | "wrong" | "offline">("idle")

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    if (!password) return
    setState("checking")
    const verdict = check
      ? await check(password)
      : await createAdminApi(password)
          .status()
          .then((r) => (r.ok ? "ok" : r.unauthorized ? "wrong" : "offline") as "ok" | "wrong" | "offline")
    if (verdict === "ok") onPassword(password)
    else setState(verdict)
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-xl flex-col justify-center gap-8 px-6 py-16">
      <Brand sub={title} />
      <form onSubmit={submit} className="surface flex flex-col gap-5 p-8">
        <div>
          <p className="eyebrow">Staff only</p>
          <h1 className="display text-4xl">Enter the {title.toLowerCase()} password</h1>
        </div>
        <div className="flex flex-col gap-3 sm:flex-row">
          <Input
            type="password"
            value={password}
            onChange={(e) => {
              setPassword(e.target.value)
              setState("idle")
            }}
            autoFocus
            autoComplete="off"
            aria-label="Password"
            aria-invalid={state === "wrong"}
            className="h-12 rounded-full bg-background px-5"
          />
          <Button type="submit" size="lg" disabled={!password || state === "checking"} className="h-12 rounded-full px-6">
            {state === "checking" ? "Checking" : "Sign in"}
            <ArrowRight />
          </Button>
        </div>
        <p role="status" className="min-h-5 text-sm text-destructive">
          {state === "wrong" && "That password did not work."}
          {state === "offline" && "Could not reach the game server."}
        </p>
      </form>
    </main>
  )
}
