import type { Page } from '@/types/page'
import { LIST_DATE_SCOPE_PARAM_KEYS, resolveListFilterToken } from '@/lib/listPageFilters'

/** Build a dashboard URL for a list-page toolbar action (no source record). */
export function buildListPageActionUrl(
  basePath: string,
  actionRelativeUrl: string,
  allPages: Page[],
  returnUrl: string,
): string | null {
  const trimmed = (actionRelativeUrl || '').trim()
  if (!trimmed) return null

  const [pageName, queryString] = trimmed.split('?', 2)
  const targetPage = allPages.find((p) => p.Name === pageName)
  if (!targetPage) return null

  const params = new URLSearchParams()
  params.set('page', String(targetPage.PageId))
  params.set('return', returnUrl)

  if (queryString) {
    for (const part of queryString.split('&')) {
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

  return `${basePath}?${params.toString()}`
}
