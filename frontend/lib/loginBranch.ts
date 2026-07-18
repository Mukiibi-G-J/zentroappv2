import { decodeJwtPayload } from '@/lib/jwt'
import { initializeBranchSessionAfterLogin } from '@/lib/branchSession'
import type { AuthSession, AuthSessionBranchConfig, BranchSummary } from '@/types/auth'

interface JwtBranchClaims {
  global_dimension_1?: BranchSummary | null
  enable_multiple_branches?: boolean
  can_switch_branch?: boolean
}

function branchConfigFromSession(session: AuthSession | null): AuthSessionBranchConfig | null {
  return session?.branch ?? null
}

function branchConfigFromJwt(accessToken: string): AuthSessionBranchConfig {
  const claims = decodeJwtPayload<JwtBranchClaims>(accessToken)
  return {
    assignedBranch: claims.global_dimension_1 ?? null,
    enableMultipleBranches: claims.enable_multiple_branches === true,
    canSwitchBranch: claims.can_switch_branch !== false,
  }
}

/** Prefer /api/auth/me/ branch block; fall back to JWT when me/ has not loaded yet. */
export function resolveBranchConfig(
  accessToken: string,
  session: AuthSession | null,
): AuthSessionBranchConfig {
  const fromSession = branchConfigFromSession(session)
  if (fromSession) return fromSession
  return branchConfigFromJwt(accessToken)
}

export function applyLoginBranchState(accessToken: string, session: AuthSession | null): void {
  const config = resolveBranchConfig(accessToken, session)
  initializeBranchSessionAfterLogin(config)
}
