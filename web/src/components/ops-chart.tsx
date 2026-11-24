import { CartesianGrid, Line, LineChart, ReferenceLine, XAxis, YAxis } from "recharts"
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart"
import type { Release } from "@/lib/types"

export interface OpsLine {
  key: string
  label: string
  color: string
}

// One line chart for an operations series, with a marker on every release.
export function OpsChart({
  data,
  lines,
  releases,
  format,
}: {
  data: object[]
  lines: OpsLine[]
  releases: Release[]
  format: (value: number) => string
}) {
  const config = Object.fromEntries(lines.map((l) => [l.key, { label: l.label, color: l.color }])) satisfies ChartConfig

  return (
    <ChartContainer config={config} className="aspect-auto h-56 w-full">
      <LineChart data={data} margin={{ left: 4, right: 16, top: 12, bottom: 4 }}>
        <CartesianGrid vertical={false} strokeDasharray="3 3" />
        <XAxis
          dataKey="day"
          type="number"
          domain={["dataMin", "dataMax"]}
          tickLine={false}
          axisLine={false}
          tickFormatter={(d: number) => `wk ${Math.floor(d / 7) + 1}`}
          minTickGap={32}
        />
        <YAxis width={56} tickLine={false} axisLine={false} domain={["auto", "auto"]} tickFormatter={format} />
        <ChartTooltip
          content={
            <ChartTooltipContent
              labelFormatter={(_, payload) => `Day ${payload?.[0]?.payload?.day ?? ""}`}
              formatter={(value, name) => (
                <span className="flex w-full items-center justify-between gap-4">
                  <span className="text-muted-foreground">{config[name as string]?.label ?? name}</span>
                  <span className="tabular font-mono font-medium">{format(Number(value))}</span>
                </span>
              )}
            />
          }
        />
        {releases.map((r) => (
          <ReferenceLine key={`${r.card}-${r.day}`} x={r.day} stroke="var(--chart-4)" strokeDasharray="4 3" />
        ))}
        {lines.map((l) => (
          <Line
            key={l.key}
            dataKey={l.key}
            type="linear"
            stroke={l.color}
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
        ))}
      </LineChart>
    </ChartContainer>
  )
}
