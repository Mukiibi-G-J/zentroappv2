import { LIST_DATE_SCOPE_PARAM_KEYS, resolveListFilterToken } from '@/lib/listPageFilters'
import { getPageRouteId, type PageRouteTarget } from '@/lib/pageRoutes'
import type { CueData } from '@/types/page'

/** Role Centre cue tile → filtered list page URL. */
export function buildCueDrillDownUrl(
  cue: CueData,
  pages: PageRouteTarget[] = [],
): string | null {
  if (!cue.DrillDownPageId) return null

  const params = new URLSearchParams()
  const target = pages.find((p) => p.PageId === cue.DrillDownPageId)
  const routePageId = target ? getPageRouteId(target) : cue.DrillDownPageId
  params.set('page', String(routePageId))

  const query = (cue.DrillDownQuery || '').trim()
  if (query) {
    for (const part of query.split('&')) {
      const [key, rawValue] = part.split('=')
      if (!key || rawValue === undefined) continue
      const decoded = decodeURIComponent(rawValue)
      if (LIST_DATE_SCOPE_PARAM_KEYS.has(key)) {
        params.set(key, resolveListFilterToken(decoded))
      } else {
        params.set(key, decoded)
      }
    }
  }

  return `/dashboard?${params.toString()}`
}
