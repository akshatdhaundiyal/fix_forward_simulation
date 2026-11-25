import { useState } from "react"
import { Pause, Play, Timer } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { countdownText, runState } from "@/lib/format"
import type { AdminState } from "@/lib/use-admin"
import { cn } from "@/lib/utils"

function Box({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="surface flex flex-col gap-4 p-5">
      <p className="eyebrow">{title}</p>
      {children}
    </section>
  )
}

export function ClockControls({ admin }: { admin: AdminState }) {
  const { status, api, run } = admin
  const [extend, setExtend] = useState("60")
  const [countdown, setCountdown] = useState("420")
  if (!status) return null
  const clock = status.clock
  const state = runState(clock)
  const counting = clock.countdown_remaining !== null && !clock.finished

  return (
    <Box title="Clock">
      <div className="flex flex-wrap items-center gap-x-8 gap-y-3">
        <div>
          <p className="display tabular text-4xl leading-none">
            Week {clock.week}
            <span className="ml-2 font-sans text-sm text-muted-foreground">day {clock.day}</span>
          </p>
          <p className={cn("mt-1 text-sm", state.tone === "go" ? "text-success" : "text-muted-foreground")}>
            {state.label}
          </p>
        </div>
        {counting && (
          <div>
            <p className="eyebrow">{clock.hold ? "Break held" : "Break ends in"}</p>
            <p className="display tabular text-3xl leading-none">{countdownText(clock.countdown_remaining as number)}</p>
          </div>
        )}
        <div className="ml-auto flex gap-2">
          <Button className="rounded-full" onClick={() => void run(() => api.clock("resume"))} disabled={clock.running || clock.finished}>
            <Play /> Resume
          </Button>
          <Button variant="outline" className="rounded-full bg-background" onClick={() => void run(() => api.clock("pause"))} disabled={!clock.running}>
            <Pause /> Pause
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap items-end gap-x-6 gap-y-4">
        <div className="flex flex-col gap-2">
          <p className="eyebrow">Speed</p>
          <ToggleGroup
            type="single"
            variant="outline"
            value={String(clock.speed)}
            onValueChange={(v) => v && void run(() => api.clock("speed", Number(v)))}
            className="rounded-full bg-background p-1"
          >
            {status.speed_choices.map((s) => (
              <ToggleGroupItem key={s} value={String(s)} className="rounded-full px-4 data-[state=on]:bg-primary data-[state=on]:text-primary-foreground">
                {s}x
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
        </div>

        <div className="flex flex-col gap-2">
          <p className="eyebrow">Extend the break (seconds)</p>
          <div className="flex gap-2">
            <Input value={extend} onChange={(e) => setExtend(e.target.value)} inputMode="numeric" className="h-9 w-24 bg-background" aria-label="Seconds to extend" />
            <Button variant="outline" className="rounded-full bg-background" disabled={!counting} onClick={() => void run(() => api.clock("extend", Number(extend)))}>
              Extend
            </Button>
            <Button variant="outline" className="rounded-full bg-background" disabled={!counting} onClick={() => void run(() => api.clock("hold"))}>
              {clock.hold ? "Held" : "Hold"}
            </Button>
          </div>
        </div>

        <div className="flex flex-col gap-2">
          <p className="eyebrow">Set the countdown (seconds)</p>
          <div className="flex gap-2">
            <Input value={countdown} onChange={(e) => setCountdown(e.target.value)} inputMode="numeric" className="h-9 w-24 bg-background" aria-label="Countdown seconds" />
            <Button variant="outline" className="rounded-full bg-background" disabled={!counting} onClick={() => void run(() => api.clock("countdown", Number(countdown)))}>
              <Timer /> Set
            </Button>
          </div>
        </div>
      </div>
    </Box>
  )
}
