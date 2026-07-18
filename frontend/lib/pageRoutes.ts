import type { Page } from '@/types/page'
import {
  COLUMN_FILTER_PREFIX,
  LIST_ORDER_PARAM,
  LIST_SORT_PARAM,
} from '@/lib/listColumnFilters'

export type PageRouteTarget = Pick<Page, 'PageId' | 'ObjectId'>

/** Legacy BC route IDs that were remapped (bookmark-friendly redirects). */
const LEGACY_PAGE_ROUTE_ALIASES: Record<number, number> = {
  // Posted Purchase Invoices list was briefly registered as 9309 (BC Purchase Credit Memos).
  9309: 146,
}

/** BC-style ID for dashboard URLs (?page=31). Falls back to internal PageId. */
export function getPageRouteId(page: PageRouteTarget): number {
  return page.ObjectId ?? page.PageId
}

/**
 * Resolve ?page= query value to a catalog page.
 * Prefers BC object_id, then internal page_id (backward compatible).
 */
export function resolvePageFromRouteParam(
  pages: PageRouteTarget[],
  routeParam: number,
): PageRouteTarget | undefined {
  if (!routeParam || routeParam <= 0) return undefined
  const aliased = LEGACY_PAGE_ROUTE_ALIASES[routeParam] ?? routeParam
  const byObjectId = pages.find((p) => p.ObjectId != null && p.ObjectId === aliased)
  if (byObjectId) return byObjectId
  return pages.find((p) => p.PageId === aliased)
}

export function listDashboardPathByPageId(
  pages: PageRouteTarget[],
  pageId: number,
): string {
  const page = pages.find((p) => p.PageId === pageId)
  return page ? listDashboardPath(page) : `/dashboard?page=${pageId}`
}

/** Route for opening a card/document record from a list or role centre. */
export function getCardRecordPath(
  cardPageId: number,
  systemId: string,
  pageType?: string | null,
  query?: Record<string, string>,
): string {
  const base =
    pageType === 'Document'
      ? `/document/${cardPageId}/${systemId}`
      : `/record/${cardPageId}/${systemId}`
  if (!query || Object.keys(query).length === 0) return base
  const params = new URLSearchParams(query)
  return `${base}?${params.toString()}`
}

export function parseFromListPageId(fromList: string | null | undefined): number | undefined {
  if (fromList == null || fromList === '' || Number.isNaN(Number(fromList))) return undefined
  return Number(fromList)
}

export function listDashboardPath(page: PageRouteTarget): string {
  return `/dashboard?page=${getPageRouteId(page)}`
}

/** List page that opens this card (e.g. FinancialReportList for FinancialReportCard). */
export function resolveListPageForCard(
  pages: Pick<Page, 'PageId' | 'PageType' | 'CardPageId'>[],
  cardPage: Pick<Page, 'PageId' | 'PageType'>,
): Pick<Page, 'PageId' | 'ObjectId'> | undefined {
  if (cardPage.PageType !== 'Card') return undefined
  return pages.find((p) => p.PageType === 'List' && p.CardPageId === cardPage.PageId)
}

/** List page that opens this document (e.g. PurchaseInvoiceList for PurchaseInvoice). */
export function resolveListPageForDocument(
  pages: Pick<Page, 'PageId' | 'PageType' | 'CardPageId'>[],
  documentPage: Pick<Page, 'PageId' | 'PageType'>,
): Pick<Page, 'PageId' | 'ObjectId'> | undefined {
  if (documentPage.PageType !== 'Document') return undefined
  return pages.find((p) => p.PageType === 'List' && p.CardPageId === documentPage.PageId)
}

/** Preserve list sort / column filters when drilling down and returning. */
export function buildListReturnPath(
  page: PageRouteTarget,
  searchParams: URLSearchParams,
  pathname = '/dashboard',
): string {
  const params = new URLSearchParams()
  params.set('page', String(getPageRouteId(page)))

  const sort = searchParams.get(LIST_SORT_PARAM)
  if (sort) params.set(LIST_SORT_PARAM, sort)

  const order = searchParams.get(LIST_ORDER_PARAM)
  if (order) params.set(LIST_ORDER_PARAM, order)

  searchParams.forEach((value, key) => {
    if (key.startsWith(COLUMN_FILTER_PREFIX) && value) {
      params.set(key, value)
    }
  })

  const qs = params.toString()
  return qs ? `${pathname}?${qs}` : listDashboardPath(page)
}

/**
 * Resolve which list page to return to from a card/document.
 * Uses ?fromList= when present (BC object_id or legacy internal PageId).
 */
export function resolveReturnListPage(
  pages: Pick<Page, 'PageId' | 'ObjectId' | 'CardPageId' | 'ContextFilterField'>[],
  cardPageId: number,
  fromListRouteParam?: number,
): Pick<Page, 'PageId' | 'ObjectId' | 'CardPageId' | 'ContextFilterField'> | null {
  if (fromListRouteParam != null) {
    const resolved = resolvePageFromRouteParam(pages, fromListRouteParam)
    if (!resolved) return null
    const match = pages.find(
      (p) =>
        p.PageId === resolved.PageId ||
        (resolved.ObjectId != null && p.ObjectId === resolved.ObjectId),
    )
    return match ?? null
  }
  return pages.find((p) => p.CardPageId === cardPageId) ?? null
}
