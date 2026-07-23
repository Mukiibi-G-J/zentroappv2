import type { PageControlField } from '@/types/page'
import type { POSSalesSetup } from '@/types/pos'

export const LINE_DISCOUNT_FIELD = 'line_discount_amount'

export const INVOICE_DISCOUNT_FIELDS = new Set([
  'invoice_discount_type',
  'invoice_discount_amount',
  'invoice_discount_percentage',
])

export function lineDiscountsEnabled(setup?: POSSalesSetup | null): boolean {
  return Boolean(setup?.enable_line_discounts ?? setup?.line_discounts_enabled)
}

export function invoiceDiscountsEnabled(setup?: POSSalesSetup | null): boolean {
  return Boolean(setup?.enable_invoice_discounts)
}

/** Hide discount columns/fields unless Sales & Receivables Setup enables them. */
export function filterDiscountFieldsBySetup(
  fields: PageControlField[],
  setup?: POSSalesSetup | null,
): PageControlField[] {
  const lineOk = lineDiscountsEnabled(setup)
  const invoiceOk = invoiceDiscountsEnabled(setup)
  return fields.filter((f) => {
    if (f.Name === LINE_DISCOUNT_FIELD) return lineOk
    if (INVOICE_DISCOUNT_FIELDS.has(f.Name)) return invoiceOk
    return true
  })
}

export function computeInvoiceDiscountValue(
  lineSubtotal: number,
  type: 'amount' | 'percentage' | null | undefined,
  amount: number,
  percentage: number,
): number {
  if (!type) return 0
  if (type === 'amount') return Math.min(Math.max(0, amount), Math.max(0, lineSubtotal))
  if (type === 'percentage') {
    const pct = Math.min(100, Math.max(0, percentage))
    return (lineSubtotal * pct) / 100
  }
  return 0
}
