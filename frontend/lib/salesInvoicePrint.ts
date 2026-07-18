import type { Page } from '@/types/page'

/** Posted sales invoice lists should offer row Print (receipt). */
export function canPrintSalesInvoiceList(page: Page | undefined): boolean {
  if (!page) return false
  if (page.Name === 'PostedSalesInvoiceList') return true
  return (
    page.SourceTable === 'PostedSalesInvoice'
    || (
      page.SourceTable === 'SalesInvoice'
      && page.ListFilterField === 'status'
      && String(page.ListFilterValue ?? '').includes('Posted')
    )
  )
}
