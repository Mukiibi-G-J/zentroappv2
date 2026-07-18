'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  ChefHat,
  Loader2,
  Maximize2,
  Minimize2,
  RefreshCw,
  UtensilsCrossed,
} from 'lucide-react'
import { toast } from 'sonner'
import { restaurantService } from '@/services/restaurant.service'
import type { KitchenOrderItem } from '@/types/restaurant'

type KitchenColumn = 'pending' | 'preparing' | 'ready'

const COLUMNS: {
  key: KitchenColumn
  title: string
  subtitle: string
  headerClass: string
  badgeClass: string
  columnClass: string
}[] = [
  {
    key: 'pending',
    title: 'New',
    subtitle: 'Tap ticket to start',
    headerClass: 'text-amber-900',
    badgeClass: 'bg-amber-100 text-amber-900 border-amber-300',
    columnClass: 'border-amber-200 bg-amber-50/40',
  },
  {
    key: 'preparing',
    title: 'Preparing',
    subtitle: 'Tap when plated',
    headerClass: 'text-sky-900',
    badgeClass: 'bg-sky-100 text-sky-900 border-sky-300',
    columnClass: 'border-sky-200 bg-sky-50/40',
  },
  {
    key: 'ready',
    title: 'Ready',
    subtitle: 'Waiting for service',
    headerClass: 'text-emerald-900',
    badgeClass: 'bg-emerald-100 text-emerald-900 border-emerald-300',
    columnClass: 'border-emerald-200 bg-emerald-50/40',
  },
]

function formatQty(qty: number): string {
  const n = Number(qty)
  return Number.isInteger(n) ? String(n) : n.toFixed(1)
}

function ticketLabel(item: KitchenOrderItem): string {
  return item.item_name || item.item_no || item.item || 'Item'
}

function KitchenTicket({
  item,
  column,
  busy,
  onAdvance,
}: {
  item: KitchenOrderItem
  column: KitchenColumn
  busy: boolean
  onAdvance: (item: KitchenOrderItem, column: KitchenColumn) => void
}) {
  const isPending = column === 'pending'
  const isPreparing = column === 'preparing'

  return (
    <button
      type="button"
      disabled={busy}
      onClick={() => onAdvance(item, column)}
      className={`w-full rounded-xl border-2 p-4 text-left shadow-sm transition hover:shadow-md disabled:opacity-60 ${
        isPending
          ? 'border-amber-400 bg-white ring-2 ring-amber-300/60 animate-pulse hover:animate-none'
          : isPreparing
            ? 'border-sky-400 bg-white hover:border-sky-500'
            : 'border-emerald-400 bg-white'
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <h4 className="text-lg font-bold leading-tight text-mainTextColor">
          {ticketLabel(item)}
        </h4>
        <span className="shrink-0 rounded-lg bg-black/5 px-2 py-1 text-lg font-bold tabular-nums">
          ×{formatQty(item.quantity)}
        </span>
      </div>

      <div className="mt-2 space-y-0.5 text-sm text-bodyText">
        <p>
          <span className="font-medium text-mainTextColor">
            {item.order_no ?? `#${item.order}`}
          </span>
          {item.table_number ? (
            <span className="ml-2 rounded bg-black/5 px-1.5 py-0.5 text-xs font-semibold uppercase">
              Tbl {item.table_number}
            </span>
          ) : null}
        </p>
        {item.waiter_name ? <p className="text-xs">Server: {item.waiter_name}</p> : null}
        {item.preparation_time ? (
          <p className="text-xs">⏱ ~{item.preparation_time} min</p>
        ) : null}
      </div>

      {item.special_instructions?.trim() ? (
        <p className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-2 py-1.5 text-xs font-medium text-amber-950">
          {item.special_instructions}
        </p>
      ) : null}

      <p
        className={`mt-3 text-center text-xs font-bold uppercase tracking-wide ${
          isPending ? 'text-amber-800' : isPreparing ? 'text-sky-800' : 'text-emerald-800'
        }`}
      >
        {isPending ? 'Tap → Start preparing' : isPreparing ? 'Tap → Mark ready' : 'Ready for pickup'}
      </p>
    </button>
  )
}

export default function KitchenDisplayPage() {
  const [items, setItems] = useState<KitchenOrderItem[]>([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [isFullscreen, setIsFullscreen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)

  const loadItems = useCallback(async (silent = false) => {
    if (!silent) setLoading(true)
    try {
      const list = await restaurantService.getKitchenItems()
      setItems(list)
    } catch {
      if (!silent) toast.error('Could not load kitchen queue')
    } finally {
      if (!silent) setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadItems()
  }, [loadItems])

  useEffect(() => {
    if (!autoRefresh) return
    const id = window.setInterval(() => void loadItems(true), 5000)
    return () => window.clearInterval(id)
  }, [autoRefresh, loadItems])

  useEffect(() => {
    const onFs = () => setIsFullscreen(Boolean(document.fullscreenElement))
    document.addEventListener('fullscreenchange', onFs)
    return () => document.removeEventListener('fullscreenchange', onFs)
  }, [])

  const grouped = useMemo(() => {
    const pending = items.filter((i) => i.status === 'pending')
    const preparing = items.filter((i) => i.status === 'preparing')
    const ready = items.filter((i) => i.status === 'ready')
    return { pending, preparing, ready }
  }, [items])

  const toggleFullscreen = async () => {
    if (!rootRef.current) return
    try {
      if (!document.fullscreenElement) {
        await rootRef.current.requestFullscreen()
      } else {
        await document.exitFullscreen()
      }
    } catch {
      toast.error('Fullscreen not available')
    }
  }

  const advanceItem = async (item: KitchenOrderItem, column: KitchenColumn) => {
    setBusy(true)
    try {
      if (column === 'pending') {
        await restaurantService.startPreparingOrderItems([item.id])
      } else if (column === 'preparing') {
        await restaurantService.updateOrderItemStatus(item.id, 'ready')
      } else {
        await restaurantService.updateOrderItemStatus(item.id, 'served')
      }
      await loadItems(true)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not update ticket')
    } finally {
      setBusy(false)
    }
  }

  const advanceAllPending = async () => {
    if (!grouped.pending.length) return
    setBusy(true)
    try {
      await restaurantService.startPreparingOrderItems(grouped.pending.map((i) => i.id))
      await loadItems(true)
      toast.success(`Started ${grouped.pending.length} ticket(s)`)
    } catch {
      toast.error('Could not start all tickets')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div
      ref={rootRef}
      className="flex min-h-0 flex-1 flex-col gap-3 overflow-hidden bg-softBg [&:fullscreen]:min-h-screen [&:fullscreen]:overflow-y-auto [&:fullscreen]:p-4"
    >
      <header className="flex shrink-0 flex-wrap items-center justify-between gap-2 rounded-xl border border-strokeColor bg-white px-4 py-3">
        <div className="flex items-center gap-2">
          <ChefHat className="h-6 w-6 text-s1" />
          <div>
            <h1 className="text-lg font-bold text-mainTextColor">Kitchen Display</h1>
            <p className="text-xs text-bodyText">Tap tickets to move them along</p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => void loadItems()}
            className="inline-flex items-center gap-1 rounded-lg border border-strokeColor px-3 py-1.5 text-xs font-medium hover:bg-softBg"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
          <button
            type="button"
            onClick={() => setAutoRefresh((v) => !v)}
            className={`rounded-lg px-3 py-1.5 text-xs font-medium ${
              autoRefresh ? 'bg-s1 text-white' : 'border border-strokeColor hover:bg-softBg'
            }`}
          >
            Auto {autoRefresh ? 'ON' : 'OFF'}
          </button>
          <button
            type="button"
            onClick={() => void toggleFullscreen()}
            className="inline-flex items-center gap-1 rounded-lg border border-strokeColor px-3 py-1.5 text-xs font-medium hover:bg-softBg"
          >
            {isFullscreen ? (
              <>
                <Minimize2 className="h-3.5 w-3.5" />
                Exit fullscreen
              </>
            ) : (
              <>
                <Maximize2 className="h-3.5 w-3.5" />
                Fullscreen
              </>
            )}
          </button>
        </div>
      </header>

      {loading && items.length === 0 ? (
        <div className="flex flex-1 items-center justify-center text-bodyText">
          <Loader2 className="mr-2 h-6 w-6 animate-spin" />
          Loading kitchen queue…
        </div>
      ) : (
        <div className="grid min-h-0 flex-1 grid-cols-1 gap-3 md:grid-cols-3">
          {COLUMNS.map((col) => {
            const list = grouped[col.key]
            return (
              <section
                key={col.key}
                className={`flex min-h-0 flex-col rounded-xl border-2 ${col.columnClass}`}
              >
                <div className="flex items-center justify-between border-b border-inherit px-3 py-2">
                  <div>
                    <h2 className={`text-sm font-bold ${col.headerClass}`}>{col.title}</h2>
                    <p className="text-[11px] text-bodyText">{col.subtitle}</p>
                  </div>
                  <span
                    className={`inline-flex min-w-[1.75rem] items-center justify-center rounded-full border px-2 py-0.5 text-xs font-bold ${col.badgeClass}`}
                  >
                    {list.length}
                  </span>
                </div>

                {col.key === 'pending' && list.length > 1 ? (
                  <div className="border-b border-inherit px-3 py-2">
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void advanceAllPending()}
                      className="w-full rounded-lg bg-amber-500 px-2 py-1.5 text-xs font-semibold text-white hover:bg-amber-600 disabled:opacity-50"
                    >
                      Start all ({list.length})
                    </button>
                  </div>
                ) : null}

                <div className="min-h-0 flex-1 space-y-2 overflow-y-auto p-3">
                  {list.length === 0 ? (
                    <div className="flex flex-col items-center justify-center gap-2 py-12 text-center text-sm text-bodyText">
                      <UtensilsCrossed className="h-8 w-8 opacity-30" />
                      <p>No tickets</p>
                    </div>
                  ) : (
                    list.map((item) => (
                      <KitchenTicket
                        key={item.id}
                        item={item}
                        column={col.key}
                        busy={busy}
                        onAdvance={advanceItem}
                      />
                    ))
                  )}
                </div>
              </section>
            )
          })}
        </div>
      )}
    </div>
  )
}
