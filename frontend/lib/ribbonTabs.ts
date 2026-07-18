import type { PageAction } from '@/types/page'

/** BC promoted ribbon tab order (Process / Entry / Report). */
export const RIBBON_TAB_ORDER = [
  'Process',
  'Entry',
  'Report',
  'Navigate',
  'Home',
  'Actions',
  'Line',
  'Row',
] as const

const PROMOTED_TABS = new Set(['Process', 'Entry', 'Report'])

export function ribbonTabName(action: PageAction): string {
  return action.RibbonTab?.trim() || 'Home'
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
  if (sorted.includes('Process')) return 'Process'
  if (sorted.includes('Entry')) return 'Entry'
  return sorted[0] ?? 'Home'
}

export function shouldShowRibbonTabBar(tabs: string[]): boolean {
  if (tabs.length > 1) return true
  if (tabs.length === 1 && tabs[0] !== 'Home') return true
  return tabs.some((tab) => PROMOTED_TABS.has(tab))
}
