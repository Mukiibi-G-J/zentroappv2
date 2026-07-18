import api from '@/lib/api'
import type {
  POSCompanyInfo,
  POSCompletedSale,
  POSCustomer,
  POSDraftSale,
  POSPaymentMethod,
  POSSalesSetup,
} from '@/types/pos'

function extractError(err: unknown): string {
  if (err && typeof err === 'object' && 'response' in err) {
    const data = (err as { response?: { data?: { error?: string; detail?: string } } }).response?.data
    if (data?.detail) return String(data.detail).trim()
    if (data?.error) return data.error
  }
  if (err instanceof Error) return err.message
  return 'Request failed'
}

export interface CreateSalesPayload {
  customer: number
  customer_name?: string
  document_date: string
  status: 'Open' | 'Draft'
  amount_received?: number
  change_amount?: number
  payment_method?: number
  invoice_discount_type?: string | null
  invoice_discount_amount?: string
  invoice_discount_percentage?: string
  lines: Array<{
    item: string
    item_no: string
    item_name: string
    quantity: string
    unit_price: string
    total_amount: string
    line_discount_amount?: string
    unit_of_measure?: string
    tracking_code?: string
    description?: string
  }>
}

interface SalesInvoiceApiRow {
  id: number
  invoice_no?: string
  customer_name?: string
  total_amount?: number | string
  status?: string
  lines?: Array<{
    item?: string
    item_no?: string
    item_name?: string
    quantity?: number | string
    unit_price?: number | string
    line_discount_amount?: number | string
    total_amount?: number | string
  }>
}

export interface SalesInvoiceForReceipt {
  system_id: string
  invoice_no?: string
  customer_name?: string
  total_amount?: number
  amount_received?: number
  change_amount?: number
  document_date?: string
  created_at?: string
  total_vat_amount?: number
  status?: string
  branch_code?: string
  user_name?: string
  payment_method_details?: {
    id?: number
    code?: string
    description?: string
    requires_amount_received?: boolean
  }
  lines?: Array<{
    item_name?: string
    resource_name?: string
    description?: string
    quantity?: number
    unit_price?: number
    total_amount?: number
    unit_of_measure?: string
  }>
}

function mapDraft(row: SalesInvoiceApiRow): POSDraftSale {
  return {
    id: row.id,
    invoice_no: row.invoice_no,
    customer_name: row.customer_name ?? '',
    total_amount: Number(row.total_amount ?? 0),
    lines: (row.lines ?? []).map((line) => ({
      item_no: String(line.item_no ?? line.item ?? ''),
      item_name: String(line.item_name ?? ''),
      quantity: Number(line.quantity ?? 0),
      unit_price: Number(line.unit_price ?? 0),
      line_discount_amount: Number(line.line_discount_amount ?? 0),
    })),
  }
}

export const salesService = {
  async getCustomers(search?: string): Promise<POSCustomer[]> {
    const res = await api.get<{ results: POSCustomer[] }>('/api/customers/', {
      params: search ? { search } : undefined,
    })
    return res.data.results ?? []
  },

  async getPaymentMethods(): Promise<POSPaymentMethod[]> {
    const res = await api.get<POSPaymentMethod[]>('/api/financials/payment-methods/')
    return Array.isArray(res.data) ? res.data : []
  },

  async getSalesSetup(): Promise<POSSalesSetup> {
    const res = await api.get<POSSalesSetup>('/api/sales/setup/')
    return res.data
  },

  async getCompanyInfo(): Promise<POSCompanyInfo | null> {
    try {
      const res = await api.get<{ company: POSCompanyInfo }>('/api/sales/company-info/')
      return res.data.company ?? null
    } catch {
      return null
    }
  },

  async createSale(payload: CreateSalesPayload) {
    try {
      const res = await api.post('/api/sales/', payload)
      return res.data as POSCompletedSale & { id: number }
    } catch (err) {
      throw new Error(extractError(err))
    }
  },

  async postInvoice(invoiceId: number) {
    try {
      const res = await api.post<{
        invoice_no?: string
        invoice?: { invoice_no?: string; total_vat_amount?: number }
      }>(`/api/sales/${invoiceId}/post_invoice/`)
      return res.data
    } catch (err) {
      throw new Error(extractError(err))
    }
  },

  async listDrafts(limit = 3): Promise<POSDraftSale[]> {
    const res = await api.get<{ results?: SalesInvoiceApiRow[] } | SalesInvoiceApiRow[]>('/api/sales/', {
      params: { status: 'Draft', limit },
    })
    const rows = Array.isArray(res.data) ? res.data : res.data.results ?? []
    return rows.map(mapDraft)
  },

  async getSale(id: number): Promise<POSDraftSale> {
    const res = await api.get<SalesInvoiceApiRow>(`/api/sales/${id}/`)
    return mapDraft(res.data)
  },

  async getInvoiceForReceipt(systemId: string): Promise<SalesInvoiceForReceipt> {
    try {
      const res = await api.get<SalesInvoiceForReceipt>(`/api/sales/${systemId}/`)
      return res.data
    } catch (err) {
      throw new Error(extractError(err))
    }
  },

  async deleteSale(id: number) {
    await api.delete(`/api/sales/${id}/`)
  },

  async getFavorites() {
    const res = await api.get('/api/sales/favorites/')
    return res.data as {
      slots: Array<{ position: number; item_system_id: string; item_no: string; item_name: string; unit_price: number }>
      min_slots: number
    }
  },

  async getSalesUserSummary(params: {
    status?: string
    date_range_after?: string
    date_range_before?: string
    posting_date?: string
    posting_date__gte?: string
    posting_date__lte?: string
    payment_method?: string
    user?: string
  }) {
    const res = await api.get<{ users: Array<{ user_id: number; user_name: string; total_sales: number; total_products?: number; total_invoices?: number }> }>(
      '/api/sales/summary/',
      { params: { ...params, group_by: 'user' } },
    )
    return res.data
  },

  async getSalesSummary(params: {
    status?: string
    posting_date?: string
    posting_date__gte?: string
    posting_date__lte?: string
    payment_method?: string
    user?: string
  }) {
    const res = await api.get<{
      total_sales: number
      total_products: number
      total_invoices: number
    }>('/api/sales/summary/', { params })
    return res.data
  },
}
