'use client'

import { useQuery } from '@tanstack/react-query'
import { pageService } from '@/services/page.service'

/** Page metadata changes rarely; shared by catalog and per-page queries. */
export const PAGE_METADATA_STALE_TIME = 5 * 60 * 1000

export function usePages() {
  return useQuery({
    queryKey: ['pages'],
    queryFn: pageService.getPages,
    staleTime: PAGE_METADATA_STALE_TIME,
  })
}

export function usePage(pageId: number | undefined) {
  const { data: pages } = usePages()
  const fromCatalog = pageId ? pages?.find((p) => p.PageId === pageId) : undefined

  return useQuery({
    queryKey: ['page', pageId],
    queryFn: () => pageService.getPage(pageId!),
    enabled: !!pageId,
    staleTime: PAGE_METADATA_STALE_TIME,
    initialData: fromCatalog,
  })
}
