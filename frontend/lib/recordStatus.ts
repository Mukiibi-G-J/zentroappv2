import type { DataRecord } from '@/types/pagedata'

/** Document / journal records with status Posted must not be edited in the UI. */
export function isPostedRecord(data: DataRecord | null | undefined): boolean {
  if (!data) return false
  const status = data.status ?? data.Status
  if (status === null || status === undefined || status === '') return false
  return String(status).toLowerCase() === 'posted'
}

/** Whether header/lines should be read-only (posted journals, closed restaurant checks, etc.). */
export function isDocumentReadOnly(
  data: DataRecord | null | undefined,
  pageName?: string,
): boolean {
  if (pageName === 'PostedPurchaseInvoice' || pageName === 'PostedSalesInvoice') return true
  if (!data) return false
  if (isPostedRecord(data)) return true

  if (pageName === 'RestaurantOrder') {
    if (data.sales_invoice) return true
    const status = String(data.status ?? data.Status ?? '').toLowerCase()
    if (status === 'completed') return true
  }

  return false
}
