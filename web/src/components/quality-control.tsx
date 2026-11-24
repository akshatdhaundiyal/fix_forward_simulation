import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { useActions } from "@/components/actions"
import type { QualityMode } from "@/lib/types"

// Qualitative only: the numbers live on the printed rules sheet, not in the browser.
const MODES: { value: QualityMode; label: string; blurb: string }[] = [
  { value: "low", label: "Low", blurb: "Fastest to ship. Leaves the most hidden problems behind." },
  { value: "medium", label: "Medium", blurb: "A balance of speed and care." },
  { value: "high", label: "High", blurb: "Slowest to ship. Leaves the fewest hidden problems." },
]

export function QualityControl({ mode }: { mode: QualityMode }) {
  const { run, busy } = useActions()
  const current = MODES.find((m) => m.value === mode) ?? MODES[1]
  return (
    <section className="surface flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex flex-col gap-1">
        <p className="eyebrow">Build quality</p>
        <p className="text-sm text-muted-foreground">{current.blurb}</p>
        <p className="text-xs text-muted-foreground">Applies to work as it is built, and you can change it any time.</p>
      </div>
      <ToggleGroup
        type="single"
        value={mode}
        disabled={busy}
        onValueChange={(value) => {
          if (value && value !== mode) void run({ type: "set_quality", mode: value as QualityMode })
        }}
        variant="outline"
        className="rounded-full bg-background p-1"
        aria-label="Build quality"
      >
        {MODES.map((m) => (
          <ToggleGroupItem
            key={m.value}
            value={m.value}
            className="rounded-full px-5 data-[state=on]:bg-primary data-[state=on]:text-primary-foreground"
          >
            {m.label}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>
    </section>
  )
}
