export interface ItemTrackingCode {
  code: string
  description?: string
  require_lot_no: boolean
  require_serial_no: boolean
  require_expiry_date: boolean
}

export interface POSTrackingOption {
  lot_no: string
  document_no: string
  remaining_quantity: number
  expiry_date: string | null
  entry_type: string
}

export interface POSCartLine {
  clientId: string
  systemId: string
  no: string
  name: string
  quantity: number
  unitPrice: number
  unitOfMeasure: string
  lineDiscountAmount: number
  trackingCode?: ItemTrackingCode | null
  selectedLotNo?: string
}

export interface POSCustomer {
  id: number
  no: string
  name: string
  payment_method?: number | null
  customer_type?: string | null
  /** Outstanding receivables balance from open ledger entries. */
  balance?: number | null
}

export interface POSPaymentMethod {
  id: number
  code: string
  description: string
  requires_amount_received: boolean
}

export interface POSSalesSetup {
  enable_line_discounts?: boolean
  enable_invoice_discounts?: boolean
  allow_price_editing?: boolean
  line_discounts_enabled?: boolean
  disable_price_editing?: boolean
  vat_enabled?: boolean
  enable_multiple_branches?: boolean
  branch_values?: { id: number; code: string; description: string }[]
}

export interface POSProduct {
  SystemId: string
  no: string
  item_name: string
  type?: string
  unit_price: number
  inventory?: number
  blocked?: boolean
  tracking_code?: ItemTrackingCode | null
}

export interface POSCompanyInfo {
  name: string
  displayName: string
  logo?: string | null
  address?: string
  phone?: string
  email?: string
  website?: string
  tin?: string
  vatNo?: string
}

export interface POSCompletedSale {
  id: number
  invoice_no?: string
  receipt_no?: string
  total_amount: number
  amount_received: number
  change_amount: number
  customer_name?: string
  customer_no?: string
  payment_method_name?: string
  payment_method_details?: {
    id: number
    code: string
    description: string
    requires_amount_received: boolean
  }
  document_date?: string
  created_at?: string
  vat_enabled?: boolean
  vat_amount?: number
  total_excl_vat?: number
  lines: Array<{
    item_name: string
    quantity: number
    unit_price: number
    total_amount: number
    unit_of_measure?: string
  }>
}

export interface POSDraftSale {
  id: number
  invoice_no?: string
  customer_name: string
  total_amount: number
  lines: Array<{
    item_no: string
    item_name: string
    quantity: number
    unit_price: number
    line_discount_amount: number
  }>
}
