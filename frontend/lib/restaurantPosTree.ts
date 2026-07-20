import type { CSSProperties } from 'react'
import type {
  MenuPosHomeLayoutSlot,
  MenuPosTreeResponse,
  PosTreeGroupNode,
  PosTreeMenuItem,
} from '@/types/restaurant'

export type PosGridEntry =
  | {
      kind: 'group'
      id: number
      name: string
      tile_color: string
      icon: string
      display_order: number
    }
  | ({ kind: 'item' } & PosTreeMenuItem)

function findGroupAtPath(roots: PosTreeGroupNode[], path: number[]): PosTreeGroupNode | null {
  let level = roots
  let cur: PosTreeGroupNode | null = null
  for (const id of path) {
    cur = level.find((n) => n.id === id) ?? null
    if (!cur) return null
    level = cur.children ?? []
  }
  return cur
}

function posEntriesFromHomeLayout(layout: MenuPosHomeLayoutSlot[] | undefined | null): PosGridEntry[] | null {
  if (!layout?.length) return null
  const sorted = [...layout].sort((a, b) => {
    if (a.row !== b.row) return a.row - b.row
    if (a.column !== b.column) return a.column - b.column
    return (a.display_order ?? 0) - (b.display_order ?? 0)
  })
  const out: PosGridEntry[] = []
  for (const s of sorted) {
    if (s.kind === 'group' && s.display_group) {
      const dg = s.display_group
      out.push({
        kind: 'group',
        id: dg.id,
        name: dg.name,
        tile_color: dg.tile_color,
        icon: dg.icon,
        display_order: dg.display_order,
      })
    } else if (s.kind === 'item' && s.menu_item) {
      out.push({ kind: 'item', ...s.menu_item })
    }
  }
  return out.length ? out : null
}

export function posGridEntries(tree: MenuPosTreeResponse | null, path: number[]): PosGridEntry[] {
  if (!tree) return []
  if (path.length === 0) {
    const fromLayout = posEntriesFromHomeLayout(tree.home_layout)
    if (fromLayout) return fromLayout

    const groups = tree.root_groups
      .map((n) => ({
        kind: 'group' as const,
        id: n.id,
        name: n.name,
        tile_color: n.tile_color,
        icon: n.icon,
        display_order: n.display_order,
      }))
      .sort((a, b) => a.display_order - b.display_order || a.name.localeCompare(b.name))
    const items = tree.ungrouped_items
      .map((it) => ({ kind: 'item' as const, ...it }))
      .sort((a, b) => a.display_order - b.display_order || a.item_name.localeCompare(b.item_name))
    return [...groups, ...items]
  }
  const node = findGroupAtPath(tree.root_groups, path)
  if (!node) return []
  if (node.children?.length) {
    return node.children
      .map((n) => ({
        kind: 'group' as const,
        id: n.id,
        name: n.name,
        tile_color: n.tile_color,
        icon: n.icon,
        display_order: n.display_order,
      }))
      .sort((a, b) => a.display_order - b.display_order || a.name.localeCompare(b.name))
  }
  return (node.items ?? [])
    .map((it) => ({ kind: 'item' as const, ...it }))
    .sort((a, b) => a.display_order - b.display_order || a.item_name.localeCompare(b.item_name))
}

/** All sellable menu items in the POS tree (for global search). */
export function flattenPosTreeItems(tree: MenuPosTreeResponse | null): PosGridEntry[] {
  if (!tree) return []
  const byId = new Map<number, PosGridEntry>()

  const addItem = (it: PosTreeMenuItem) => {
    byId.set(it.id, { kind: 'item', ...it })
  }

  const walk = (nodes: PosTreeGroupNode[]) => {
    for (const n of nodes) {
      for (const it of n.items ?? []) addItem(it)
      if (n.children?.length) walk(n.children)
    }
  }

  walk(tree.root_groups ?? [])
  for (const it of tree.ungrouped_items ?? []) addItem(it)

  for (const slot of tree.home_layout ?? []) {
    if (slot.kind === 'item' && slot.menu_item) addItem(slot.menu_item)
  }

  return [...byId.values()].sort(
    (a, b) =>
      (a.kind === 'item' ? a.display_order : 0) - (b.kind === 'item' ? b.display_order : 0) ||
      (a.kind === 'item' ? a.item_name : a.name).localeCompare(
        b.kind === 'item' ? b.item_name : b.name,
      ),
  )
}

export function filterPosEntries(
  entries: PosGridEntry[],
  query: string,
  allItems?: PosGridEntry[],
): PosGridEntry[] {
  const q = query.trim().toLowerCase()
  if (!q) return entries

  const matches = (e: PosGridEntry) => {
    if (e.kind === 'group') return e.name.toLowerCase().includes(q)
    return (
      e.item_name.toLowerCase().includes(q) ||
      (e.item_no || '').toLowerCase().includes(q)
    )
  }

  // Prefer flat item search so guests can find "Black Tea" from the home grid.
  if (allItems?.length) {
    const itemHits = allItems.filter((e) => e.kind === 'item' && matches(e))
    if (itemHits.length) return itemHits
  }

  return entries.filter(matches)
}

const TILE_FALLBACK = [
  'bg-rose-500',
  'bg-amber-500',
  'bg-emerald-500',
  'bg-sky-500',
  'bg-violet-500',
  'bg-orange-500',
]

export function posTileClass(tileColor: string, idx: number): string {
  if (tileColor?.startsWith('#')) return ''
  if (tileColor && !tileColor.startsWith('Hi')) {
    const map: Record<string, string> = {
      rose: 'bg-rose-500',
      amber: 'bg-amber-500',
      emerald: 'bg-emerald-500',
      sky: 'bg-sky-500',
      violet: 'bg-violet-500',
      indigo: 'bg-indigo-500',
      orange: 'bg-orange-500',
      teal: 'bg-teal-500',
    }
    return `${map[tileColor] ?? TILE_FALLBACK[idx % TILE_FALLBACK.length]} text-white`
  }
  return `${TILE_FALLBACK[idx % TILE_FALLBACK.length]} text-white`
}

export function posTileStyle(tileColor: string): CSSProperties | undefined {
  if (tileColor?.startsWith('#')) {
    return { backgroundColor: tileColor, color: '#fff' }
  }
  return undefined
}

export function tableStatusClass(status: string): string {
  switch (status) {
    case 'occupied':
      return 'border-amber-400 bg-amber-50 text-amber-900'
    case 'reserved':
      return 'border-violet-400 bg-violet-50 text-violet-900'
    case 'cleaning':
      return 'border-sky-400 bg-sky-50 text-sky-900'
    case 'maintenance':
      return 'border-gray-400 bg-gray-100 text-gray-700'
    default:
      return 'border-emerald-300 bg-emerald-50 text-emerald-900'
  }
}

export function orderItemStatusClass(status: string): string {
  switch (status) {
    case 'preparing':
      return 'bg-amber-100 text-amber-800'
    case 'ready':
      return 'bg-sky-100 text-sky-800'
    case 'served':
      return 'bg-emerald-100 text-emerald-800'
    case 'cancelled':
      return 'bg-gray-100 text-gray-500 line-through'
    default:
      return 'bg-gray-100 text-gray-700'
  }
}
