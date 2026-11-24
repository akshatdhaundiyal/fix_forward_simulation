// Black pill with the event name, after the reference site's header mark.
export function Brand({ sub }: { sub?: string }) {
  return (
    <div className="inline-flex items-center gap-3 rounded-2xl bg-primary px-4 py-2.5 text-primary-foreground">
      <span className="font-mono text-[13px] font-semibold uppercase tracking-[0.14em]">
        Fix Forward
      </span>
      {sub ? (
        <span className="font-mono text-[11px] uppercase tracking-[0.12em] text-primary-foreground/60">
          / {sub}
        </span>
      ) : null}
    </div>
  )
}
