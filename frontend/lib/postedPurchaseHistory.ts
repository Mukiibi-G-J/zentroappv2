import {
  detectQuickRange,
  formatSalesCurrency,
  quickRangeDates,
  type QuickRangeKey,
} from '@/lib/postedSalesHistory'

export const POSTED_PURCHASE_INVOICE_LIST_PAGE = 'PostedPurchaseInvoiceList'

export interface PostedPurchaseHistoryFilters {
  posting_date?: string
  posting_date_from?: string
  posting_date_to?: string
}

export interface PurchaseSummaryTotals {
  total_purchases: number
  total_products: number
  total_invoices: number
}

export const formatPurchaseCurrency = formatSalesCurrency

export {
  detectQuickRange,
  quickRangeDates,
  type QuickRangeKey,
}

/** Map page-engine list scope filters to /api/purchases/summary/ query params. */
export function buildPurchaseSummaryParams(
  filters: PostedPurchaseHistoryFilters,
): Record<string, string> {
  const params: Record<string, string> = {}

  if (filters.posting_date) {
    params.posting_date = filters.posting_date
  } else {
    if (filters.posting_date_from) params.posting_date__gte = filters.posting_date_from
    if (filters.posting_date_to) params.posting_date__lte = filters.posting_date_to
  }

  return params
}

export function buildPostedPurchaseFilterUrl(
  pageId: number,
  filters: PostedPurchaseHistoryFilters & { filterLabel?: string },
  returnUrl?: string | null,
): string {
  const params = new URLSearchParams()
  params.set('page', String(pageId))

  if (filters.posting_date) params.set('posting_date', filters.posting_date)
  if (filters.posting_date_from) params.set('posting_date_from', filters.posting_date_from)
  if (filters.posting_date_to) params.set('posting_date_to', filters.posting_date_to)
  if (filters.filterLabel) params.set('filterLabel', filters.filterLabel)
  if (returnUrl) params.set('return', returnUrl)

  return `/dashboard?${params.toString()}`
}
