import type { PageAction } from '@/types/page'

/** BC ribbon tab order — Home first (Apply Entries), then Process / Entry / Report. */
export const RIBBON_TAB_ORDER = [
  'Home',
  'Process',
  'Entry',
  'Report',
  'Navigate',
  'Actions',
  'Line',
  'Row',
] as const

const PROMOTED_TABS = new Set(['Process', 'Entry', 'Report'])

export function ribbonTabName(action: PageAction): string {
  return action.RibbonTab?.trim() || 'Home'
}

export function ribbonGroupName(action: PageAction): string {
  return (action.RibbonGroup || '').trim()
}

export function ribbonTabsFromActions(actions: PageAction[]): string[] {
  const seen = new Set<string>()
  const result: string[] = []
  for (const action of actions) {
    const tab = ribbonTabName(action)
    if (!seen.has(tab)) {
      seen.add(tab)
      result.push(tab)
    }
  }
  return sortRibbonTabs(result)
}

export function actionsForRibbonTab(actions: PageAction[], tab: string): PageAction[] {
  return actions.filter((action) => ribbonTabName(action) === tab)
}

export function sortRibbonTabs(tabs: string[]): string[] {
  return [...tabs].sort((a, b) => {
    const ai = RIBBON_TAB_ORDER.indexOf(a as (typeof RIBBON_TAB_ORDER)[number])
    const bi = RIBBON_TAB_ORDER.indexOf(b as (typeof RIBBON_TAB_ORDER)[number])
    return (ai === -1 ? 999 : ai) - (bi === -1 ? 999 : bi)
  })
}

export function defaultRibbonTab(tabs: string[]): string {
  const sorted = sortRibbonTabs(tabs)
  // Prefer Home when present (BC Customer Ledger Entries: Apply Entries lives on Home).
  if (sorted.includes('Home')) return 'Home'
  if (sorted.includes('Process')) return 'Process'
  if (sorted.includes('Entry')) return 'Entry'
  return sorted[0] ?? 'Home'
}

export function shouldShowRibbonTabBar(tabs: string[]): boolean {
  if (tabs.length > 1) return true
  if (tabs.length === 1 && tabs[0] !== 'Home') return true
  return tabs.some((tab) => PROMOTED_TABS.has(tab))
}

export type RibbonRenderItem =
  | { kind: 'action'; action: PageAction }
  | { kind: 'menu'; group: string; actions: PageAction[] }

/**
 * Collapse page-engine actions that share RibbonGroup into dropdown menus.
 * Standalone actions (empty RibbonGroup) stay as individual buttons.
 * Order follows the first occurrence of each group / action in the tab list.
 */
export function groupRibbonActions(actions: PageAction[]): RibbonRenderItem[] {
  const items: RibbonRenderItem[] = []
  const emittedGroups = new Set<string>()

  for (const action of actions) {
    const group = ribbonGroupName(action)
    if (!group) {
      items.push({ kind: 'action', action })
      continue
    }
    if (emittedGroups.has(group)) continue
    emittedGroups.add(group)
    const members = actions.filter((a) => ribbonGroupName(a) === group)
    if (members.length === 1) {
      items.push({ kind: 'action', action: members[0] })
    } else {
      items.push({ kind: 'menu', group, actions: members })
    }
  }
  return items
}
