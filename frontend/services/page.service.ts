import api from '@/lib/api'
import type { Page, TableRelationValue, PageActionResponse, RoleCentreData, ListCuesData } from '@/types/page'
import type { ActionResult } from '@/types/pagedata'

export type InvokeActionResult = ActionResult | PageActionResponse

export const pageService = {
  async getPages(): Promise<Page[]> {
    const res = await api.get<Page[]>('/api/pages/')
    if (!Array.isArray(res.data)) {
      const msg =
        res.data && typeof res.data === 'object' && 'error' in res.data
          ? String((res.data as { error: string }).error)
          : `Request failed: ${res.status}`
      throw new Error(msg)
    }
    return res.data
  },

  async getPage(pageId: number): Promise<Page> {
    const res = await api.get<Page>('/api/pages/page/', { params: { PageId: pageId } })
    return res.data
  },

  async fetchTableRelations(
    pageId: number,
    pageControlId: number,
    pageControlFieldId: number,
    currentRecordSystemId: string | null = null,
    recordValues: Record<string, unknown> = {},
  ): Promise<TableRelationValue[]> {
    const res = await api.post<TableRelationValue[]>('/api/pages/relations/', {
      PageId: pageId,
      PageControlId: pageControlId,
      PageControlFieldId: pageControlFieldId,
      CurrentRecordSystemId: currentRecordSystemId,
      CurrentRecordValues: recordValues,
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

  async invokeAction(
    pageId: number,
    actionId: string,
    systemId: string,
    payload: Record<string, unknown> = {},
  ): Promise<InvokeActionResult> {
    const res = await api.post<InvokeActionResult>('/api/pages/action/', {
      PageId: pageId,
      ActionId: actionId,
      SystemId: systemId,
      ...payload,
    })
    return res.data
  },

  async executePageAction(
    pageId: number,
    actionId: number,
    payload: Record<string, unknown>,
  ): Promise<PageActionResponse> {
    const res = await api.post<PageActionResponse>('/api/pages/action/', {
      PageId: pageId,
      ActionId: actionId,
      ...payload,
    })
    return res.data
  },

  async getRoleCentreData(pageId: number): Promise<RoleCentreData> {
    const res = await api.get<RoleCentreData>('/api/pages/rolecentre/', {
      params: { PageId: pageId },
    })
    return res.data
  },

  async getListCues(pageId: number): Promise<ListCuesData> {
    const res = await api.get<ListCuesData>('/api/pages/list-cues/', {
      params: { PageId: pageId },
    })
    return res.data
  },
}
