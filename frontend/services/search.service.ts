import api from '@/lib/api'
import type { ApiGlobalSearchSection } from '@/types/search'

export const searchService = {
  async globalSearch(query: string): Promise<ApiGlobalSearchSection[]> {
    const res = await api.post<{ data: ApiGlobalSearchSection[] }>(
      '/api/search/global/',
      { query },
    )
    return res.data.data ?? []
  },
}
