/** Resolve dynamic list-filter tokens from page actions and cue drill-downs. */

function isoDate(date: Date): string {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

function quarterBounds(date: Date): { start: string; end: string } {
  const quarterIndex = Math.floor(date.getMonth() / 3)
  const startMonth = quarterIndex * 3
  const start = new Date(date.getFullYear(), startMonth, 1)
  const end = new Date(date.getFullYear(), startMonth + 3, 0)
  return { start: isoDate(start), end: isoDate(end) }
}

/** Calendar week (Sun–Sat), matching dayjs startOf/endOf('week'). */
export function weekBounds(date: Date): { start: string; end: string } {
  const d = new Date(date.getFullYear(), date.getMonth(), date.getDate())
  const day = d.getDay()
  const start = new Date(d)
  start.setDate(d.getDate() - day)
  const end = new Date(start)
  end.setDate(start.getDate() + 6)
  return { start: isoDate(start), end: isoDate(end) }
}

export function monthBounds(date: Date): { start: string; end: string } {
  const start = new Date(date.getFullYear(), date.getMonth(), 1)
  const end = new Date(date.getFullYear(), date.getMonth() + 1, 0)
  return { start: isoDate(start), end: isoDate(end) }
}

export function resolveListFilterToken(value: string): string {
  const trimmed = value.trim()
  const today = new Date()

  if (trimmed === '__today__') return isoDate(today)

  if (trimmed === '__yesterday__') {
    const yesterday = new Date(today)
    yesterday.setDate(yesterday.getDate() - 1)
    return isoDate(yesterday)
  }

  if (trimmed === '__quarter_start__') return quarterBounds(today).start
  if (trimmed === '__quarter_end__') return quarterBounds(today).end

  if (trimmed === '__week_start__') return weekBounds(today).start
  if (trimmed === '__week_end__') return weekBounds(today).end

  if (trimmed === '__month_start__') return monthBounds(today).start
  if (trimmed === '__month_end__') return monthBounds(today).end

  return trimmed
}

export const LIST_SCOPE_FILTER_KEYS = [
  'posting_date',
  'posting_date_from',
  'posting_date_to',
  'ledger_user_id',
] as const

export type ListScopeFilterKey = (typeof LIST_SCOPE_FILTER_KEYS)[number]

export const LIST_DATE_SCOPE_PARAM_KEYS = new Set<string>([
  'posting_date',
  'posting_date_from',
  'posting_date_to',
])

export function todayIsoDate(): string {
  return resolveListFilterToken('__today__')
}

export function yesterdayIsoDate(): string {
  return resolveListFilterToken('__yesterday__')
}

/** Parse scope query params from a PageAction relative URL (values resolved to ISO dates). */
export function scopeParamsFromActionUrl(actionRelativeUrl: string): URLSearchParams {
  const trimmed = (actionRelativeUrl || '').trim()
  const queryString = trimmed.includes('?') ? trimmed.split('?', 2)[1] : ''
  const params = new URLSearchParams()

  if (!queryString) return params

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

  return params
}

export function hasListScopeParams(params: URLSearchParams): boolean {
  return LIST_SCOPE_FILTER_KEYS.some((key) => params.has(key))
}

/** True when the action's scope params match the current list URL (for highlighting the active chip). */
export function isListScopeActionActive(
  actionRelativeUrl: string,
  currentParams: URLSearchParams,
): boolean {
  const expected = scopeParamsFromActionUrl(actionRelativeUrl)
  const expectedScope = LIST_SCOPE_FILTER_KEYS.filter((key) => expected.has(key))
  const currentScope = LIST_SCOPE_FILTER_KEYS.filter((key) => currentParams.has(key))

  if (expectedScope.length === 0) {
    return currentScope.length === 0
  }

  if (expectedScope.length !== currentScope.length) return false

  return expectedScope.every((key) => expected.get(key) === resolveScopeParamValue(key, currentParams.get(key)!))
}

function resolveScopeParamValue(key: ListScopeFilterKey, raw: string): string {
  if (LIST_DATE_SCOPE_PARAM_KEYS.has(key)) {
    return resolveListFilterToken(raw)
  }
  return raw
}
