'use client'

import { useBranchOptional } from '@/context/BranchContext'
import { branchCacheKeySegment } from '@/lib/branchHeaders'

/**
 * React Query cache segment for the current branch context.
 * Isolates cached list/role-centre data per branch without stale cross-branch rows.
 */
export function useBranchCacheKey(): string {
  const branch = useBranchOptional()
  if (branch) {
    if (branch.branchScope === 'all') return 'all'
    const id = branch.activeBranch?.id ?? branch.assignedBranch?.id
    return id != null ? String(id) : 'none'
  }
  return branchCacheKeySegment()
}
