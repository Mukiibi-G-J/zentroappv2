import type { ItemTrackingCode } from '@/types/pos'

export interface TrackingSpecification {
  id: number
  item: string
  serial_no?: string | null
  lot_no?: string | null
  expiry_date?: string | null
  quantity_base: number
  description?: string | null
  purchase_invoice?: number | null
  purchase_invoice_line?: number | null
  sales_invoice?: number | null
  sales_invoice_line?: number | null
}

export interface TrackingSpecificationSummary {
  expected_quantity: number
  total_quantity: number
  remaining_quantity: number
  specifications_count: number
}

export interface LotCheckResult {
  exists: boolean
  expiry_date?: string | null
  lot_no?: string
  remaining_quantity?: number
  location?: string | null
}

export interface PurchaseTrackingContext {
  mode?: 'open' | 'posted'
  purchaseInvoiceId?: number
  purchaseInvoiceLineId?: number
  salesInvoiceId?: number
  salesInvoiceLineId?: number
  itemJournalId?: number
  vendorInvoiceNo?: string
  itemNo: string
  itemName: string
  trackingCode: ItemTrackingCode
  /** Line quantity in base UOM (qty × qty per UOM). */
  expectedQuantity: number
}
