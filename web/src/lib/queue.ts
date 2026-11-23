import type { Card, QueueItem, Report, TeamView } from "./types"

// A drop becomes queue_reorder: the server removes the item and inserts it at
// this index, which is where the item should sit afterwards.
export function reorderPosition(
  queue: QueueItem[],
  activeId: number,
  overId: number,
): { item: number; position: number } | null {
  if (activeId === overId) return null
  const target = queue.findIndex((q) => q.id === overId)
  if (target < 0 || !queue.some((q) => q.id === activeId)) return null
  return { item: activeId, position: target }
}

export function backlogBu(queue: QueueItem[]): number {
  return queue.reduce((sum, q) => sum + Math.max(0, q.cost - q.progress), 0)
}

// The newest report for the card's own segment that covers it.
export function latestUtility(reports: Report[], card: Card): { value: number; day: number } | null {
  if (!card.seg) return null
  let best: { value: number; day: number } | null = null
  for (const r of reports) {
    if (r.seg !== card.seg || r.utility[card.id] === undefined) continue
    if (!best || r.day >= best.day) best = { value: r.utility[card.id], day: r.day }
  }
  return best
}

export function rollbackCandidates(view: TeamView): Card[] {
  return view.cards.filter((c) => c.status === "shipped" && !c.bespoke)
}
