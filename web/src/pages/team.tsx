import { useEffect, useState } from "react"
import { Toaster } from "@/components/ui/sonner"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { TooltipProvider } from "@/components/ui/tooltip"
import { Button } from "@/components/ui/button"
import { ActionsProvider } from "@/components/actions"
import { Brand } from "@/components/brand"
import { Bookings } from "@/components/bookings"
import { CalendarStrip } from "@/components/calendar"
import { CardCatalog } from "@/components/card-catalog"
import { ClockBar } from "@/components/clock-bar"
import { ContractPanel } from "@/components/contract-panel"
import { ConnectionBanner } from "@/components/connection-banner"
import { Explorer } from "@/components/funnel/explorer"
import { IncidentAlert, Incidents } from "@/components/incidents"
import { Operations } from "@/components/operations"
import { OverviewTiles } from "@/components/overview-tiles"
import { OutageNotice } from "@/components/outage-notice"
import { QualityControl } from "@/components/quality-control"
import { Queue } from "@/components/queue"
import { Reports } from "@/components/reports"
import { codeFromHash, forgetCode } from "@/lib/team-code"
import { useCalendar } from "@/lib/use-calendar"
import { useGame } from "@/lib/usegame"
import { cn } from "@/lib/utils"

type Tab = "overview" | "roadmap" | "reports" | "funnel" | "operations" | "incidents" | "stakeholders"

const TABS: { value: Tab; label: string }[] = [
  { value: "overview", label: "Overview" },
  { value: "roadmap", label: "Roadmap" },
  { value: "reports", label: "Reports" },
  { value: "funnel", label: "Funnel" },
  { value: "operations", label: "Operations" },
  { value: "incidents", label: "Incidents" },
  { value: "stakeholders", label: "Stakeholders" },
]

function InvalidCode() {
  useEffect(() => forgetCode(), [])
  return (
    <main className="mx-auto flex min-h-screen max-w-xl flex-col justify-center gap-6 px-6">
      <Brand sub="Console" />
      <div className="surface flex flex-col gap-4 p-8">
        <h1 className="display text-3xl">That team code did not work</h1>
        <p className="text-sm text-muted-foreground">Check the card your host gave your team and enter the code again.</p>
        <Button className="w-fit rounded-full" onClick={() => window.location.assign("./")}>
          Enter a code
        </Button>
      </div>
    </main>
  )
}

function Loading() {
  return (
    <main className="mx-auto flex max-w-6xl flex-col gap-4 px-6 py-8">
      <Skeleton className="h-12 w-64 rounded-2xl" />
      <Skeleton className="h-20 w-full rounded-2xl" />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-44 rounded-2xl" />
        ))}
      </div>
    </main>
  )
}

function Console({ code }: { code: string }) {
  const { state, feed } = useGame(code)
  const calendar = useCalendar()
  const [tab, setTab] = useState<Tab>("overview")
  const { clock, view, status } = state

  if (status === "invalid-code") return <InvalidCode />
  if (!clock || !view) {
    return (
      <>
        <Loading />
        <div className="mx-auto max-w-6xl px-6">
          <ConnectionBanner status={status} />
        </div>
      </>
    )
  }

  return (
    <ActionsProvider feed={feed}>
      <TooltipProvider>
        <main className="mx-auto flex max-w-6xl flex-col gap-4 px-4 pb-16 pt-6 sm:px-6">
          <header className="flex flex-wrap items-center justify-between gap-3">
            <Brand sub={`Team ${view.team}`} />
            <p className="eyebrow">Live now · quarter {view.quarter}</p>
          </header>

          <ClockBar clock={clock} quarter={view.quarter} />
          <ConnectionBanner status={status} />
          <OutageNotice outage={view.outage} />
          <IncidentAlert incidents={view.incidents} onOpen={() => setTab("incidents")} />

          <Tabs value={tab} onValueChange={(v) => setTab(v as Tab)} className="gap-6">
            <TabsList variant="line" className="h-auto w-full justify-start gap-1 overflow-x-auto border-b pb-1">
              {TABS.map((t) => (
                <TabsTrigger
                  key={t.value}
                  value={t.value}
                  className={cn("flex-none rounded-full px-4 py-2 data-active:bg-accent")}
                >
                  {t.label}
                  {t.value === "incidents" && view.tiles.open_incidents > 0 && (
                    <span className="ml-1.5 rounded-full bg-destructive px-1.5 text-[10px] font-semibold text-white">
                      {view.tiles.open_incidents}
                    </span>
                  )}
                </TabsTrigger>
              ))}
            </TabsList>

            <TabsContent value="overview" className="flex flex-col gap-6">
              <OverviewTiles view={view} onOpenIncidents={() => setTab("incidents")} />
              {calendar && <CalendarStrip calendar={calendar} week={clock.week} />}
            </TabsContent>

            <TabsContent value="roadmap" className="flex flex-col gap-6">
              <QualityControl mode={view.quality} />
              <ContractPanel b1={view.b1} day={clock.day} week={clock.week} calendar={calendar} />
              <div className="grid items-start gap-8 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
                <CardCatalog view={view} />
                <div className="xl:sticky xl:top-6">
                  <Queue queue={view.queue} />
                </div>
              </div>
            </TabsContent>

            <TabsContent value="reports">
              <Reports view={view} />
            </TabsContent>

            <TabsContent value="funnel">
              <Explorer code={code} pollSeconds={clock.poll_seconds} light={view} />
            </TabsContent>

            <TabsContent value="operations">
              <Operations code={code} pollSeconds={clock.poll_seconds} light={view} />
            </TabsContent>

            <TabsContent value="stakeholders">
              <Bookings code={code} pollSeconds={clock.poll_seconds} />
            </TabsContent>

            <TabsContent value="incidents">
              <Incidents view={view} onOpenFunnel={() => setTab("funnel")} />
            </TabsContent>
          </Tabs>
        </main>
        <Toaster position="bottom-right" />
      </TooltipProvider>
    </ActionsProvider>
  )
}

export function TeamPage() {
  const code = codeFromHash(window.location.hash)
  useEffect(() => {
    if (!code) window.location.replace("./")
  }, [code])
  if (!code) return null
  return <Console code={code} />
}
