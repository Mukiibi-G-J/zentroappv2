import {
  weekBounds,
  monthBounds,
  todayIsoDate,
  yesterdayIsoDate,
  resolveListFilterToken,
} from '@/lib/listPageFilters'

export const POSTED_SALES_INVOICE_LIST_PAGE = 'PostedSalesInvoiceList'

export interface PostedSalesHistoryFilters {
  posting_date?: string
  posting_date_from?: string
  posting_date_to?: string
  payment_method?: string
  ledger_user_id?: string
}

export interface SalesSummaryTotals {
  total_sales: number
  total_products: number
  total_invoices: number
}

export interface SalesUserSummaryRow {
  user_id: number | null
  user_name: string
  total_sales: number
  total_products: number
  total_invoices: number
}

export function formatSalesCurrency(value: number, currencyCode?: string | null): string {
  const n = Number(value) || 0
  const code = (currencyCode || '').trim().toUpperCase()
  const amount = Math.round(n).toLocaleString()
  return code ? `${code} ${amount}` : amount
}

/** Map page-engine list scope filters to /api/sales/summary/ query params. */
export function buildSalesSummaryParams(filters: PostedSalesHistoryFilters): Record<string, string> {
  const params: Record<string, string> = {}

  if (filters.posting_date) {
    params.posting_date = filters.posting_date
  } else {
    if (filters.posting_date_from) params.posting_date__gte = filters.posting_date_from
    if (filters.posting_date_to) params.posting_date__lte = filters.posting_date_to
  }

  if (filters.payment_method) {
    params.payment_method = filters.payment_method
  }

  if (filters.ledger_user_id) {
    params.user = filters.ledger_user_id
  }

  return params
}

export function buildPostedSalesFilterUrl(
  pageId: number,
  filters: PostedSalesHistoryFilters & { filterLabel?: string },
  returnUrl?: string | null,
): string {
  const params = new URLSearchParams()
  params.set('page', String(pageId))

  if (filters.posting_date) params.set('posting_date', filters.posting_date)
  if (filters.posting_date_from) params.set('posting_date_from', filters.posting_date_from)
  if (filters.posting_date_to) params.set('posting_date_to', filters.posting_date_to)
  if (filters.payment_method) params.set('payment_method', filters.payment_method)
  if (filters.ledger_user_id) params.set('ledger_user_id', filters.ledger_user_id)
  if (filters.filterLabel) params.set('filterLabel', filters.filterLabel)
  if (returnUrl) params.set('return', returnUrl)

  return `/dashboard?${params.toString()}`
}

export type QuickRangeKey =
  | ''
  | 'all_posted'
  | 'today'
  | 'yesterday'
  | 'this_week'
  | 'this_month'
  | 'this_quarter'

export function quickRangeDates(key: QuickRangeKey): { from: string; to: string } | null {
  const today = new Date()
  switch (key) {
    case 'today':
      return { from: todayIsoDate(), to: todayIsoDate() }
    case 'yesterday': {
      const y = yesterdayIsoDate()
      return { from: y, to: y }
    }
    case 'this_week': {
      const { start, end } = weekBounds(today)
      return { from: start, to: end }
    }
    case 'this_month': {
      const { start, end } = monthBounds(today)
      return { from: start, to: end }
    }
    case 'this_quarter':
      return {
        from: resolveListFilterToken('__quarter_start__'),
        to: resolveListFilterToken('__quarter_end__'),
      }
    default:
      return null
  }
}

/** Resolve SalesInvoice system id for receipt print from a posted list row. */
export function salesInvoiceSystemIdFromRecord(
  record: Record<string, unknown>,
): string {
  const linked = record.sales_invoice_system_id
  if (linked != null && String(linked).trim() !== '') {
    return String(linked)
  }
  return String(record.SystemId ?? '')
}

export function detectQuickRange(filters: PostedSalesHistoryFilters): QuickRangeKey {
  const { posting_date, posting_date_from, posting_date_to } = filters
  if (!posting_date && !posting_date_from && !posting_date_to) return 'all_posted'

  if (posting_date) {
    if (posting_date === todayIsoDate()) return 'today'
    if (posting_date === yesterdayIsoDate()) return 'yesterday'
    return ''
  }
  if (!posting_date_from || !posting_date_to) return ''

  const quarterStart = resolveListFilterToken('__quarter_start__')
  const quarterEnd = resolveListFilterToken('__quarter_end__')
  if (posting_date_from === quarterStart && posting_date_to === quarterEnd) return 'this_quarter'

  const week = weekBounds(new Date())
  if (posting_date_from === week.start && posting_date_to === week.end) return 'this_week'

  const month = monthBounds(new Date())
  if (posting_date_from === month.start && posting_date_to === month.end) return 'this_month'

  return ''
}
