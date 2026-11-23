import { Brand } from "@/components/brand"
import { codeFromHash } from "@/lib/team-code"

// Placeholder frame. The console replaces this once the data layer exists.
export function TeamPage() {
  const code = codeFromHash(window.location.hash)
  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col justify-center gap-6 px-6">
      <Brand sub="Console" />
      <p className="eyebrow">Team code</p>
      <p className="display text-5xl">{code ?? "none"}</p>
    </main>
  )
}
