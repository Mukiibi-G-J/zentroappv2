const PENDING_CREATION_KEY = 'zentro_pending_company_creation'
/** Drop resumed sessions older than this (ms). */
export const PENDING_CREATION_MAX_AGE_MS = 45 * 60 * 1000

export type CompanyCreationSessionPayload = {
  organizationName: string
  organizationSize: string
  businessCategory: string
  businessObjective: string
}

export type PendingCompanyCreation = {
  taskId: string
  planName: string
  companyData: CompanyCreationSessionPayload
  /** Unix ms when create was accepted by the API. */
  createdAt?: number
  credentials?: {
    email: string
    password: string
  }
}

export function readPendingCompanyCreation(): PendingCompanyCreation | null {
  if (typeof window === 'undefined') return null
  try {
    const raw = sessionStorage.getItem(PENDING_CREATION_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as PendingCompanyCreation
    if (!parsed?.taskId || !parsed?.companyData?.organizationName || !parsed?.planName) {
      return null
    }
    const createdAt = parsed.createdAt ?? 0
    if (createdAt && Date.now() - createdAt > PENDING_CREATION_MAX_AGE_MS) {
      sessionStorage.removeItem(PENDING_CREATION_KEY)
      return null
    }
    return parsed
  } catch {
    return null
  }
}

export function writePendingCompanyCreation(p: PendingCompanyCreation): void {
  if (typeof window === 'undefined') return
  sessionStorage.setItem(
    PENDING_CREATION_KEY,
    JSON.stringify({
      ...p,
      createdAt: p.createdAt ?? Date.now(),
    }),
  )
}

export function clearPendingCompanyCreation(): void {
  if (typeof window === 'undefined') return
  sessionStorage.removeItem(PENDING_CREATION_KEY)
}
