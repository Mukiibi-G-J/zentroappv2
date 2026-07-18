'use client'

import { useQuery } from '@tanstack/react-query'
import { pageService } from '@/services/page.service'
import { useBranchCacheKey } from '@/hooks/useBranchCacheKey'
import type { RoleCentreData } from '@/types/page'

export function useRoleCentre(pageId: number | undefined) {
  const branchKey = useBranchCacheKey()
  return useQuery<RoleCentreData>({
    queryKey: ['rolecentre', pageId, branchKey],
    queryFn: () => pageService.getRoleCentreData(pageId!),
    enabled: !!pageId,
    staleTime: 30_000,
    refetchInterval: 30_000,
  })
}
