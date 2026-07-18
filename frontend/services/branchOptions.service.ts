import api from '@/lib/api'
import { fetchCompanyBranches } from '@/services/company.service'
import type { BranchSummary } from '@/types/auth'

interface SalesSetupBranches {
  branch_values?: BranchSummary[]
  enable_multiple_branches?: boolean
}

let cachedBranches: BranchSummary[] | null = null
let inflight: Promise<BranchSummary[]> | null = null

async function loadBranchOptions(): Promise<BranchSummary[]> {
  try {
    const res = await api.get<SalesSetupBranches>('/api/sales/setup/')
    const fromSetup = res.data?.branch_values ?? []
    if (fromSetup.length > 0) {
      return fromSetup.map((b) => ({
        id: b.id,
        code: b.code,
        description: b.description || b.code,
      }))
    }
  } catch {
    /* fall through */
  }
  return fetchCompanyBranches()
}

/** Cached branch list — fetched once per app session when the picker opens. */
export function fetchBranchOptions(force = false): Promise<BranchSummary[]> {
  if (!force && cachedBranches) return Promise.resolve(cachedBranches)
  if (!force && inflight) return inflight

  inflight = loadBranchOptions()
    .then((list) => {
      cachedBranches = list
      inflight = null
      return list
    })
    .catch((err) => {
      inflight = null
      throw err
    })

  return inflight
}

export function clearBranchOptionsCache(): void {
  cachedBranches = null
  inflight = null
}
