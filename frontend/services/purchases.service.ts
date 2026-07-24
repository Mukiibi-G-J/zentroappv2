import api from '@/lib/api'

export const purchasesService = {
  async getPurchaseSummary(params: {
    posting_date?: string
    posting_date__gte?: string
    posting_date__lte?: string
  }) {
    const res = await api.get<{
      total_purchases: number
      total_products: number
      total_invoices: number
    }>('/api/purchases/summary/', { params })
    return res.data
  },
}
