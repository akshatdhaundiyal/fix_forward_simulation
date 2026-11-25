import { CartesianGrid, Line, LineChart, ReferenceLine, XAxis, YAxis } from "recharts"
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart"
import { bandAt, teamTitle, weeklyRows, type Band, type DebriefData, type DebriefTeam, type DebriefView } from "@/lib/debrief"
import { formatCr } from "@/lib/format"
import { cn } from "@/lib/utils"

const COLORS = ["var(--chart-1)", "var(--chart-2)", "var(--chart-4)", "var(--chart-5)"]
const BAND_CLASS: Record<Band, string> = { green: "bg-success", amber: "bg-warning", red: "bg-destructive" }
const BAND_WORD: Record<Band, string> = { green: "Green", amber: "Amber", red: "Red" }

function colorFor(data: DebriefData, team: DebriefTeam) {
  return COLORS[data.teams.indexOf(team) % COLORS.length]
}

function NoHistory() {
  return (
    <p className="rounded-2xl border bg-card p-6 text-xl text-muted-foreground">
      These teams have no weekly history to chart. The server was restarted from a snapshot, which keeps no history.
    </p>
  )
}

// Hidden debt over the 52 weeks for the week-26 leader, the final winner and the
// biggest collapse, with the CTO's band lines drawn across it.
function DebtCurves({ data }: { data: DebriefData }) {
  const rows = weeklyRows(data, (p) => p.debt)
  const config = Object.fromEntries(
    data.teams.map((t) => [`t${t.team}`, { label: teamTitle(t), color: colorFor(data, t) }]),
  ) satisfies ChartConfig
  if (data.teams.every((t) => t.series.length === 0)) return <NoHistory />
  return (
    <section className="flex flex-col gap-4">
      <h2 className="display text-4xl">The debt nobody could see</h2>
      <ChartContainer config={config} className="aspect-auto h-[28rem] w-full">
        <LineChart data={rows} margin={{ left: 8, right: 24, top: 16, bottom: 8 }}>
          <CartesianGrid vertical={false} strokeDasharray="3 3" />
          <XAxis dataKey="week" tickLine={false} axisLine={false} tickFormatter={(w: number) => `wk ${w}`} minTickGap={24} />
          <YAxis width={56} tickLine={false} axisLine={false} />
          {data.band_limits.map((limit) => (
            <ReferenceLine key={limit} y={limit} stroke="var(--muted-foreground)" strokeDasharray="6 4" />
          ))}
          <ChartTooltip content={<ChartTooltipContent />} />
          {data.teams.map((t) => (
            <Line key={t.team} dataKey={`t${t.team}`} type="linear" stroke={colorFor(data, t)} strokeWidth={3} dot={false} connectNulls={false} isAnimationActive={false} />
          ))}
        </LineChart>
      </ChartContainer>
      <ul className="flex flex-wrap gap-x-8 gap-y-2 text-xl">
        {data.teams.map((t) => (
          <li key={t.team} className="flex items-center gap-3">
            <span className="size-4 rounded-full" style={{ background: colorFor(data, t) }} />
            {teamTitle(t)}
          </li>
        ))}
      </ul>
      <p className="text-lg text-muted-foreground">
        Dashed lines mark where the CTO's light turned amber ({data.band_limits[0]}) and red ({data.band_limits[1]}).
      </p>
    </section>
  )
}

// "It was on your dashboard, and your CTO told you": each team's error rate with its CTO band underneath.
function DashboardView({ data }: { data: DebriefData }) {
  if (data.teams.every((t) => t.series.length === 0)) return <NoHistory />
  const weeks = Array.from({ length: data.weeks }, (_, i) => i + 1)
  return (
    <section className="flex flex-col gap-8">
      <h2 className="display text-4xl">It was on your dashboard, and your CTO told you</h2>
      {data.teams.map((t) => {
        const rows = weeklyRows({ ...data, teams: [t] }, (p) => p.error_rate * 100)
        const config = { [`t${t.team}`]: { label: "Error rate", color: colorFor(data, t) } } satisfies ChartConfig
        return (
          <div key={t.team} className="flex flex-col gap-3 rounded-3xl border bg-card p-6 shadow-soft">
            <h3 className="display text-2xl">{teamTitle(t)}</h3>
            <ChartContainer config={config} className="aspect-auto h-52 w-full">
              <LineChart data={rows} margin={{ left: 8, right: 24, top: 8, bottom: 4 }}>
                <CartesianGrid vertical={false} strokeDasharray="3 3" />
                <XAxis dataKey="week" tickLine={false} axisLine={false} tickFormatter={(w: number) => `wk ${w}`} minTickGap={24} />
                <YAxis width={56} tickLine={false} axisLine={false} tickFormatter={(v: number) => `${v.toFixed(1)}%`} />
                <ChartTooltip content={<ChartTooltipContent />} />
                <Line dataKey={`t${t.team}`} type="linear" stroke={colorFor(data, t)} strokeWidth={3} dot={false} isAnimationActive={false} />
              </LineChart>
            </ChartContainer>
            <div className="flex flex-col gap-1">
              <p className="eyebrow text-sm">The CTO's light, week by week</p>
              <div className="flex gap-0.5" role="img" aria-label={`CTO light for ${t.name} across the year`}>
                {weeks.map((w) => {
                  const band = bandAt(t, w)
                  return (
                    <span
                      key={w}
                      title={`Week ${w}: ${band ? BAND_WORD[band] : "no record"}`}
                      className={cn("h-6 flex-1 rounded-sm", band ? BAND_CLASS[band] : "bg-muted")}
                    />
                  )
                })}
              </div>
            </div>
          </div>
        )
      })}
    </section>
  )
}

function Gains({ data }: { data: DebriefData }) {
  return (
    <section className="flex flex-col gap-6">
      <h2 className="display text-4xl">What these features were really worth</h2>
      <p className="text-xl text-muted-foreground">Who built them without buying a report?</p>
      <ul className="flex flex-col gap-3">
        {data.gains.map((g) => (
          <li key={g.card} className="flex items-center gap-6 rounded-3xl border bg-card px-6 py-5 shadow-soft">
            <span className="display flex-1 text-3xl">{g.name}</span>
            <span className="w-56 text-right">
              <span className="eyebrow block text-sm">Pitched</span>
              <span className="tabular display text-4xl">{formatCr(g.pitch)}</span>
            </span>
            <span className="w-56 text-right">
              <span className="eyebrow block text-sm">Really added</span>
              <span className="tabular display text-4xl">{formatCr(g.target_gain)}</span>
            </span>
          </li>
        ))}
      </ul>
    </section>
  )
}

export function Debrief({ view, data }: { view: Exclude<DebriefView, "ranking">; data: DebriefData | null }) {
  if (!data) return <p className="text-2xl text-muted-foreground">Loading the debrief.</p>
  if (view === "curves") return <DebtCurves data={data} />
  if (view === "dashboard") return <DashboardView data={data} />
  return <Gains data={data} />
}
