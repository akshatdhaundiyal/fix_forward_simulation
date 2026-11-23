import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core"
import {
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable"
import { CSS } from "@dnd-kit/utilities"
import { GripVertical, Trash2 } from "lucide-react"
import { useState } from "react"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import { useActions } from "@/components/actions"
import { reorderPosition } from "@/lib/queue"
import type { QueueItem } from "@/lib/types"
import { cn } from "@/lib/utils"

const KIND_LABEL: Record<QueueItem["kind"], string> = {
  card: "Initiative",
  report: "Report",
  fix: "Fix",
  patch: "Patch",
}

function Row({ item, first, onRemove }: { item: QueueItem; first: boolean; onRemove: (item: QueueItem) => void }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: item.id })
  const left = Math.max(0, item.cost - item.progress)
  const pct = item.cost > 0 ? (item.progress / item.cost) * 100 : 0
  return (
    <li
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={cn(
        "flex items-center gap-3 rounded-2xl border bg-background p-3 pr-2",
        isDragging && "relative z-10 shadow-soft ring-2 ring-ring/40",
      )}
    >
      <button
        {...attributes}
        {...listeners}
        aria-label={`Move ${item.label}. Press space, then use the arrow keys.`}
        className="cursor-grab touch-none rounded-md p-1 text-muted-foreground hover:bg-accent hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50 outline-none active:cursor-grabbing"
      >
        <GripVertical className="size-4" />
      </button>
      <div className="flex min-w-0 flex-1 flex-col gap-1.5">
        <div className="flex items-center gap-2">
          <p className="truncate text-sm font-medium">{item.label}</p>
          <Badge variant="outline" className="shrink-0">
            {KIND_LABEL[item.kind]}
          </Badge>
          {first && <Badge className="shrink-0">Building now</Badge>}
        </div>
        <div className="flex items-center gap-3">
          <Progress value={pct} className="h-1.5 flex-1" />
          <span className="tabular w-36 shrink-0 whitespace-nowrap text-right font-mono text-xs text-muted-foreground">
            {left.toFixed(0)} of {item.cost} BU left
          </span>
        </div>
      </div>
      <Button variant="ghost" size="icon" aria-label={`Remove ${item.label}`} onClick={() => onRemove(item)}>
        <Trash2 />
      </Button>
    </li>
  )
}

export function Queue({ queue }: { queue: QueueItem[] }) {
  const { run, busy } = useActions()
  const [confirming, setConfirming] = useState<QueueItem | null>(null)
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  )

  function onDragEnd(event: DragEndEvent) {
    if (!event.over || busy) return
    const move = reorderPosition(queue, Number(event.active.id), Number(event.over.id))
    if (move) void run({ type: "queue_reorder", item: move.item, position: move.position })
  }

  function remove(item: QueueItem) {
    // Removing something already partly built loses that work, so ask first.
    if (item.progress > 0) setConfirming(item)
    else void run({ type: "queue_remove", item: item.id })
  }

  return (
    <section className="flex flex-col gap-4">
      <div>
        <p className="eyebrow">Build queue</p>
        <p className="text-sm text-muted-foreground">
          Your team builds from the top. Drag to reorder; a paused item keeps its progress.
        </p>
      </div>
      {queue.length === 0 ? (
        <div className="rounded-2xl border border-dashed p-8 text-center text-sm text-muted-foreground">
          The queue is empty, so your team is idle. Add an initiative to start building.
        </div>
      ) : (
        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
          <SortableContext items={queue.map((q) => q.id)} strategy={verticalListSortingStrategy}>
            <ol className="flex flex-col gap-2">
              {queue.map((item, i) => (
                <Row key={item.id} item={item} first={i === 0} onRemove={remove} />
              ))}
            </ol>
          </SortableContext>
        </DndContext>
      )}

      <AlertDialog open={confirming !== null} onOpenChange={(open) => !open && setConfirming(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove {confirming?.label}?</AlertDialogTitle>
            <AlertDialogDescription>
              Your team has already built {confirming?.progress.toFixed(0)} of {confirming?.cost} BU. Removing it loses
              that work for good.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep it</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (confirming) void run({ type: "queue_remove", item: confirming.id })
                setConfirming(null)
              }}
            >
              Remove and lose the work
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  )
}
