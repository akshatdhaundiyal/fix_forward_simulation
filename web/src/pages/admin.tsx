import { useState } from "react"
import { Brand } from "@/components/brand"
import { ClockControls } from "@/components/admin/clock-controls"
import { EditState } from "@/components/admin/edit-state"
import { Gate } from "@/components/admin/gate"
import { Health } from "@/components/admin/health"
import { IncidentControls } from "@/components/admin/incident-controls"
import { Snapshots } from "@/components/admin/snapshots"
import { Skeleton } from "@/components/ui/skeleton"
import { Toaster } from "@/components/ui/sonner"
import { forgetAdminPassword, recallAdminPassword, rememberAdminPassword } from "@/lib/admin-api"
import { useAdmin } from "@/lib/use-admin"

function Dashboard({ password, onSignOut }: { password: string; onSignOut: () => void }) {
  const admin = useAdmin(password, onSignOut)
  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-4 px-4 pb-16 pt-6 sm:px-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <Brand sub="Operator" />
        <button onClick={onSignOut} className="eyebrow underline-offset-4 hover:underline">
          Sign out
        </button>
      </header>
      {admin.status ? (
        <>
          <ClockControls admin={admin} />
          <Health admin={admin} />
          <IncidentControls admin={admin} />
          <EditState admin={admin} />
          <Snapshots admin={admin} />
        </>
      ) : (
        <Skeleton className="h-64 w-full rounded-2xl" />
      )}
      <Toaster position="bottom-right" />
    </main>
  )
}

export function AdminPage() {
  const [password, setPassword] = useState<string | null>(() => recallAdminPassword())
  const signOut = () => {
    forgetAdminPassword()
    setPassword(null)
  }
  if (!password) {
    return (
      <Gate
        title="Operator"
        onPassword={(p) => {
          rememberAdminPassword(p)
          setPassword(p)
        }}
      />
    )
  }
  return <Dashboard password={password} onSignOut={signOut} />
}
