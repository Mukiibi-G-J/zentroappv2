import api from '@/lib/api'
import type {
  LotCheckResult,
  TrackingSpecification,
  TrackingSpecificationSummary,
} from '@/types/tracking'

export async function fetchTrackingSpecifications(
  purchaseInvoiceLineId: number,
): Promise<TrackingSpecification[]> {
  const res = await api.get<TrackingSpecification[]>('/api/tracking-specifications/', {
    params: { purchase_invoice_line: purchaseInvoiceLineId },
  })
  return Array.isArray(res.data) ? res.data : []
}

export async function fetchTrackingSpecificationSummary(
  lineId: number,
  contextType: 'purchase' | 'adjustment' = 'purchase',
): Promise<TrackingSpecificationSummary> {
  const res = await api.get<TrackingSpecificationSummary>(
    `/api/tracking-specifications/summary/${lineId}/`,
    { params: { context_type: contextType } },
  )
  return res.data
}

export async function createTrackingSpecification(
  data: Partial<TrackingSpecification>,
): Promise<TrackingSpecification> {
  const res = await api.post<TrackingSpecification>('/api/tracking-specifications/', data)
  return res.data
}

export async function updateTrackingSpecification(
  id: number,
  data: Partial<TrackingSpecification>,
): Promise<TrackingSpecification> {
  const res = await api.patch<TrackingSpecification>(`/api/tracking-specifications/${id}/`, data)
  return res.data
}

export async function deleteTrackingSpecification(id: number): Promise<void> {
  await api.delete(`/api/tracking-specifications/${id}/`)
}

export async function checkLotNumber(lotNo: string, itemNo: string): Promise<LotCheckResult> {
  const res = await api.get<LotCheckResult>('/api/tracking-specifications/check_lot/', {
    params: { lot_no: lotNo, item: itemNo },
  })
  return res.data
}
