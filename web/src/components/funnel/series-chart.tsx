import { CartesianGrid, Line, LineChart, ReferenceLine, XAxis, YAxis } from "recharts"
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart"
import { percent } from "@/lib/format"
import type { Metric, Series } from "@/lib/funnel"
import type { Release } from "@/lib/types"

function formatValue(metric: Metric, value: number): string {
  if (metric === "arr") return `₹${value.toFixed(2)} Cr`
  if (metric === "leads") return value.toFixed(1)
  return percent(value, metric === "churn" ? 3 : 1)
}

export function SeriesChart({
  series,
  metric,
  label,
  releases,
}: {
  series: Series
  metric: Metric
  label: string
  releases: Release[]
}) {
  const config = { value: { label, color: "var(--chart-1)" } } satisfies ChartConfig

  return (
    <ChartContainer config={config} className="aspect-auto h-80 w-full">
      <LineChart data={series.data} margin={{ left: 4, right: 16, top: 16, bottom: 4 }}>
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
        <YAxis
          width={56}
          tickLine={false}
          axisLine={false}
          domain={["auto", "auto"]}
          tickFormatter={(v: number) => formatValue(metric, v)}
        />
        <ChartTooltip
          content={
            <ChartTooltipContent
              labelFormatter={(_, payload) => `Day ${payload?.[0]?.payload?.day ?? ""}`}
              formatter={(value) => (
                <span className="tabular font-mono font-medium">{formatValue(metric, Number(value))}</span>
              )}
            />
          }
        />
        {releases.map((r) => (
          <ReferenceLine
            key={`${r.card}-${r.day}`}
            x={r.day}
            stroke="var(--chart-4)"
            strokeDasharray="4 3"
            label={{ value: r.name, position: "insideTopRight", fontSize: 10, fill: "var(--muted-foreground)" }}
          />
        ))}
        <Line dataKey="value" type="linear" stroke="var(--chart-1)" strokeWidth={2} dot={false} isAnimationActive={false} />
      </LineChart>
    </ChartContainer>
  )
}
