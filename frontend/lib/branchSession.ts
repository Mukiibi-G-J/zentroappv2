import type { BranchSummary } from '@/types/auth'

const STORAGE_KEY = 'branch_session'

export type BranchScope = 'single' | 'all'

export interface BranchSessionState {
  activeBranch: BranchSummary | null
  assignedBranch: BranchSummary | null
  branchSelectionPending: boolean
  branchScope: BranchScope
}

/** In-memory snapshot — axios reads headers without JSON parse on every request. */
let memorySnapshot: BranchSessionState | undefined

function defaultState(): BranchSessionState {
  return {
    activeBranch: null,
    assignedBranch: null,
    branchSelectionPending: false,
    branchScope: 'single',
  }
}

function normalizeState(raw: Partial<BranchSessionState> | null): BranchSessionState {
  if (!raw) return defaultState()
  return {
    activeBranch: raw.activeBranch ?? null,
    assignedBranch: raw.assignedBranch ?? null,
    branchSelectionPending: Boolean(raw.branchSelectionPending),
    branchScope: raw.branchScope === 'all' ? 'all' : 'single',
  }
}

function syncMemory(state: BranchSessionState): void {
  memorySnapshot = state
}

export function readBranchSession(): BranchSessionState {
  if (memorySnapshot !== undefined) return memorySnapshot
  if (typeof window === 'undefined') return defaultState()
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) {
      const empty = defaultState()
      syncMemory(empty)
      return empty
    }
    const state = normalizeState(JSON.parse(raw) as Partial<BranchSessionState>)
    syncMemory(state)
    return state
  } catch {
    const empty = defaultState()
    syncMemory(empty)
    return empty
  }
}

function writeBranchSession(state: BranchSessionState): void {
  syncMemory(state)
  if (typeof window === 'undefined') return
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
}

/** Active session branch, else user's assigned branch (matches legacy BaseService). */
export function getEffectiveBranchIdForApi(): number | null {
  const { branchScope, activeBranch, assignedBranch } = readBranchSession()
  if (branchScope === 'all') return null
  return activeBranch?.id ?? assignedBranch?.id ?? null
}

export function getBranchScopeForApi(): BranchScope {
  return readBranchSession().branchScope
}

/** @deprecated Use getEffectiveBranchIdForApi — kept for callers that only need active. */
export function getActiveBranchIdForApi(): number | null {
  return getEffectiveBranchIdForApi()
}

export function setActiveBranch(branch: BranchSummary | null): void {
  const current = readBranchSession()
  writeBranchSession({ ...current, activeBranch: branch, branchScope: 'single' })
}

export function setAssignedBranch(branch: BranchSummary | null): void {
  const current = readBranchSession()
  writeBranchSession({ ...current, assignedBranch: branch })
}

export function setBranchSelectionPending(pending: boolean): void {
  const current = readBranchSession()
  writeBranchSession({ ...current, branchSelectionPending: pending })
}

export function setBranchScope(scope: BranchScope): void {
  const current = readBranchSession()
  writeBranchSession({ ...current, branchScope: scope })
}

export function confirmBranchSelection(branch: BranchSummary): void {
  const current = readBranchSession()
  writeBranchSession({
    ...current,
    activeBranch: branch,
    branchSelectionPending: false,
    branchScope: 'single',
  })
}

export function clearBranchSession(): void {
  memorySnapshot = undefined
  if (typeof window === 'undefined') return
  localStorage.removeItem(STORAGE_KEY)
}

export function initializeBranchSessionAfterLogin(config: {
  assignedBranch: BranchSummary | null
  enableMultipleBranches: boolean
  canSwitchBranch: boolean
}): void {
  const shouldPrompt =
    config.enableMultipleBranches && config.canSwitchBranch !== false

  writeBranchSession({
    activeBranch: config.assignedBranch,
    assignedBranch: config.assignedBranch,
    branchSelectionPending: shouldPrompt,
    branchScope: 'single',
  })
}
