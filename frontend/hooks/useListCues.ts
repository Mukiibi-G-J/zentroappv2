'use client'

import { useQuery } from '@tanstack/react-query'
import { pageService } from '@/services/page.service'
import { useBranchCacheKey } from '@/hooks/useBranchCacheKey'
import type { ListCuesData } from '@/types/page'

export function useListCues(pageId: number | undefined) {
  const branchKey = useBranchCacheKey()
  return useQuery<ListCuesData>({
    queryKey: ['list-cues', pageId, branchKey],
    queryFn: () => pageService.getListCues(pageId!),
    enabled: !!pageId,
    staleTime: 30_000,
    refetchInterval: 30_000,
  })
}
