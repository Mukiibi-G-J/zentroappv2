import api from '@/lib/api'
import type { DataRecord, UpdateFieldResponse } from '@/types/pagedata'

function extractErrorMessage(err: unknown): string {
  if (err && typeof err === 'object' && 'response' in err) {
    const data = (err as { response?: { data?: { error?: string } } }).response?.data
    if (data?.error) return data.error
  }
  if (err instanceof Error) return err.message
  return 'Request failed'
}

export const pageDataService = {
  async list(
    pageId: number,
    controlId?: number,
    search?: string,
    limit = 100,
    filters?: Record<string, string>,
    offset = 0,
    sort?: { field: string; order: 'asc' | 'desc' } | null,
  ): Promise<DataRecord[]> {
    const res = await api.get<DataRecord[]>('/api/pages/data/', {
      params: {
        PageId: pageId,
        ControlId: controlId,
        search,
        limit,
        offset,
        ...(sort?.field ? { sort: sort.field, order: sort.order } : {}),
        ...filters,
      },
    })
    if (!Array.isArray(res.data)) {
      const msg =
        res.data && typeof res.data === 'object' && 'error' in res.data
          ? String((res.data as { error: string }).error)
          : `Request failed: ${res.status}`
      throw new Error(msg)
    }
    return res.data
  },

  async create(
    pageId: number,
    controlId: number,
    data: Record<string, unknown>,
    parentSystemId?: string,
  ): Promise<DataRecord> {
    const body: Record<string, unknown> = { PageId: pageId, ControlId: controlId, ...data }
    if (parentSystemId) body.parent_system_id = parentSystemId
    const res = await api.post<DataRecord>('/api/pages/data/', body)
    return res.data
  },

  async update(
    pageId: number,
    systemId: string,
    field: string,
    value: unknown,
    listPageId?: number,
    currentRecordValues?: Record<string, unknown>,
  ): Promise<UpdateFieldResponse> {
    const body: Record<string, unknown> = { PageId: pageId, field, value }
    if (listPageId) body.ListPageId = listPageId
    if (currentRecordValues && Object.keys(currentRecordValues).length > 0) {
      body.CurrentRecordValues = currentRecordValues
    }
    const res = await api.patch<UpdateFieldResponse>(`/api/pages/data/${systemId}/`, body)
    return res.data
  },

  async delete(pageId: number, controlId: number, systemId: string): Promise<void> {
    await api.delete(`/api/pages/data/${systemId}/`, { params: { PageId: pageId, ControlId: controlId } })
  },

  async getRecord(pageId: number, controlId: number | undefined, systemId: string): Promise<DataRecord> {
    const params: Record<string, string | number> = { PageId: pageId }
    if (controlId !== undefined) params.ControlId = controlId
    const res = await api.get<DataRecord | { error: string }>(`/api/pages/data/${systemId}/`, { params })
    if (res.data && typeof res.data === 'object' && 'error' in res.data) {
      throw new Error(String(res.data.error))
    }
    return res.data as DataRecord
  },

  /** Previous/next SystemId in list order (Business Central record navigator). */
  async getNeighbors(
    listPageId: number,
    systemId: string,
    filters?: Record<string, string>,
    sort?: { field: string; order: 'asc' | 'desc' } | null,
  ): Promise<{ previousSystemId: string | null; nextSystemId: string | null }> {
    const res = await api.get<{
      previousSystemId: string | null
      nextSystemId: string | null
      error?: string
    }>('/api/pages/data/', {
      params: {
        PageId: listPageId,
        neighbors: '1',
        SystemId: systemId,
        ...(sort?.field ? { sort: sort.field, order: sort.order } : {}),
        ...filters,
      },
    })
    if (res.data && typeof res.data === 'object' && 'error' in res.data && res.data.error) {
      throw new Error(String(res.data.error))
    }
    return {
      previousSystemId: res.data.previousSystemId ?? null,
      nextSystemId: res.data.nextSystemId ?? null,
    }
  },

  async getSetupSolo(pageId: number): Promise<string> {
    const res = await api.get<{ SystemId: string } | { error: string }>('/api/pages/setup-solo/', {
      params: { PageId: pageId },
    })
    if (res.data && typeof res.data === 'object' && 'error' in res.data) {
      throw new Error(String(res.data.error))
    }
    return (res.data as { SystemId: string }).SystemId
  },
}

export { extractErrorMessage }
