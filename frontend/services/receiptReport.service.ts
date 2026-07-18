import api from '@/lib/api'
import type {
  KotBarPayload,
  ReceiptBranding,
  ReceiptBuildPayload,
  ResolvedReceiptTemplate,
  SaleReceiptPayload,
} from '@/shared/receipt/types'

export interface ReceiptReportRunResult {
  reportId: number
  reportName: string
  caption: string
  payload: Record<string, unknown>
  template: ResolvedReceiptTemplate
  branding: ReceiptBranding
}

function extractError(err: unknown): string {
  if (err && typeof err === 'object' && 'response' in err) {
    const data = (err as { response?: { data?: { error?: string; detail?: string } } }).response?.data
    if (data?.detail) return String(data.detail).trim()
    if (data?.error) return data.error
  }
  if (err instanceof Error) return err.message
  return 'Request failed'
}

function normalizeTemplate(raw: Record<string, unknown>): ResolvedReceiptTemplate {
  return {
    id: raw.id as number | undefined,
    code: String(raw.code ?? ''),
    name: String(raw.name ?? ''),
    receiptType: (raw.receiptType ?? raw.receipt_type ?? 'sale') as ResolvedReceiptTemplate['receiptType'],
    layoutPreset: (raw.layoutPreset ?? raw.layout_preset ?? 'standard') as ResolvedReceiptTemplate['layoutPreset'],
    paperProfile: (raw.paperProfile ?? raw.paper_profile ?? {}) as ResolvedReceiptTemplate['paperProfile'],
    sections: (raw.sections ?? []) as ResolvedReceiptTemplate['sections'],
    editorMode: (raw.editorMode ?? raw.editor_mode ?? 'visual') as ResolvedReceiptTemplate['editorMode'],
    formatString: String(raw.formatString ?? raw.format_string ?? ''),
    isSystem: Boolean(raw.is_system ?? raw.isSystem),
    isActive: raw.is_active !== false && raw.isActive !== false,
  }
}

function mapLineItems(lines: unknown): SaleReceiptPayload['lines'] {
  if (!Array.isArray(lines)) return []
  return lines.map((line) => {
    const row = line as Record<string, unknown>
    return {
      item_name: String(row.itemName ?? row.item_name ?? ''),
      quantity: row.quantity as number | string,
      unit_price: (row.unitPrice ?? row.unit_price) as number | string | undefined,
      total_price: (row.totalPrice ?? row.total_price ?? row.total_amount) as number | string | undefined,
      total_amount: (row.totalPrice ?? row.total_amount) as number | string | undefined,
      special_instructions: (row.specialInstructions ?? row.special_instructions) as string | null | undefined,
      fire_state_display: (row.fireStateDisplay ?? row.fire_state_display) as string | null | undefined,
      seat_no: (row.seatNo ?? row.seat_no) as number | null | undefined,
    }
  })
}

/** Convert API run payload into renderer input. */
export function normalizeReportPayload(raw: Record<string, unknown>): ReceiptBuildPayload {
  const receiptType = String(raw.receiptType ?? raw.receipt_type ?? 'sale')

  if (receiptType === 'kot' || receiptType === 'bar') {
    return {
      receiptType,
      title: raw.title as string | undefined,
      orderNo: String(raw.orderNo ?? raw.order_no ?? ''),
      tableLabel: String(raw.tableLabel ?? raw.table_label ?? ''),
      orderTypeDisplay: String(raw.orderTypeDisplay ?? raw.order_type_display ?? ''),
      waiterName: (raw.waiterName ?? raw.waiter_name) as string | undefined,
      printedAt: String(raw.printedAt ?? raw.printed_at ?? new Date().toISOString()),
      items: mapLineItems(raw.items ?? raw.lines),
    } satisfies KotBarPayload
  }

  if (receiptType === 'interim_bill') {
    return {
      receiptType: 'interim_bill',
      invoiceNo: String(raw.orderNo ?? raw.order_no ?? ''),
      orderNo: String(raw.orderNo ?? raw.order_no ?? ''),
      tableLabel: String(raw.tableLabel ?? raw.table_label ?? ''),
      orderTypeDisplay: String(raw.orderTypeDisplay ?? raw.order_type_display ?? ''),
      waiterName: (raw.waiterName ?? raw.waiter_name) as string | undefined,
      documentDate: String(raw.documentDate ?? raw.document_date ?? new Date().toISOString()),
      customerName: (raw.customerName ?? raw.customer_name) as string | undefined,
      lines: mapLineItems(raw.lines),
      totalAmount: Number(raw.totalAmount ?? raw.total_amount ?? 0),
    } satisfies SaleReceiptPayload
  }

  if (receiptType === 'payment_journal') {
    return {
      receiptType: 'payment_journal',
      documentNo: String(raw.documentNo ?? raw.document_no ?? ''),
      documentDate: String(raw.documentDate ?? raw.document_date ?? new Date().toISOString().slice(0, 10)),
      lines: mapLineItems(raw.lines),
      totalAmount: Number(raw.totalAmount ?? raw.total_amount ?? 0),
      paymentMethod: (raw.paymentMethod ?? raw.payment_method) as string | undefined,
    }
  }

  return {
    receiptType: receiptType === 'prepayment' ? 'prepayment' : 'sale',
    invoiceNo: String(raw.invoiceNo ?? raw.invoice_no ?? ''),
    documentDate: String(raw.documentDate ?? raw.document_date ?? new Date().toISOString()),
    customerName: (raw.customerName ?? raw.customer_name) as string | undefined,
    customerNo: (raw.customerNo ?? raw.customer_no) as string | undefined,
    lines: mapLineItems(raw.lines),
    totalAmount: Number(raw.totalAmount ?? raw.total_amount ?? 0),
    totalExclVat: raw.totalExclVat != null ? Number(raw.totalExclVat) : undefined,
    vatAmount: raw.vatAmount != null ? Number(raw.vatAmount) : undefined,
    vatEnabled: Boolean(raw.vatEnabled),
    amountReceived: raw.amountReceived != null ? Number(raw.amountReceived) : undefined,
    changeAmount: raw.changeAmount != null ? Number(raw.changeAmount) : undefined,
    paymentMethod: (raw.paymentMethod ?? raw.payment_method) as string | undefined,
    sellerName: (raw.sellerName ?? raw.seller_name) as string | undefined,
  } satisfies SaleReceiptPayload
}

export const receiptReportService = {
  async runReport(
    reportId: number,
    body: Record<string, unknown>,
  ): Promise<ReceiptReportRunResult> {
    try {
      const { data } = await api.post<ReceiptReportRunResult>(
        `/api/receipt-reports/${reportId}/run/`,
        body,
      )
      return {
        ...data,
        template: normalizeTemplate(data.template as unknown as Record<string, unknown>),
      }
    } catch (err) {
      throw new Error(extractError(err))
    }
  },
}
