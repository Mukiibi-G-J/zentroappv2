'use client'

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useSession } from '@/context/SessionContext'
import {
  confirmBranchSelection,
  readBranchSession,
  setActiveBranch as persistActiveBranch,
  setAssignedBranch as persistAssignedBranch,
  setBranchSelectionPending as persistBranchPending,
} from '@/lib/branchSession'
import { clearBranchOptionsCache } from '@/services/branchOptions.service'
import type { AuthSessionBranchConfig, BranchSummary, BranchScope } from '@/types/auth'

interface BranchContextValue {
  activeBranch: BranchSummary | null
  assignedBranch: BranchSummary | null
  enableMultipleBranches: boolean
  canSwitchBranch: boolean
  branchScope: BranchScope
  branchSelectionPending: boolean
  openBranchPicker: () => void
  confirmBranch: (branch: BranchSummary) => void
}

const BranchContext = createContext<BranchContextValue | null>(null)

function configFromSession(branch?: AuthSessionBranchConfig): AuthSessionBranchConfig {
  return (
    branch ?? {
      assignedBranch: null,
      enableMultipleBranches: false,
      canSwitchBranch: true,
    }
  )
}

export function BranchProvider({ children }: { children: ReactNode }) {
  const { session } = useSession()
  const queryClient = useQueryClient()
  const branchConfig = configFromSession(session?.branch)

  // Always start equal on server + first client paint; read localStorage in effect.
  const [stored, setStored] = useState({
    activeBranch: null as BranchSummary | null,
    assignedBranch: null as BranchSummary | null,
    branchSelectionPending: false,
    branchScope: 'single' as BranchScope,
  })

  useEffect(() => {
    setStored(readBranchSession())
  }, [])

  useEffect(() => {
    if (!session?.branch) return
    const current = readBranchSession()
    if (session.branch.assignedBranch) {
      persistAssignedBranch(session.branch.assignedBranch)
    }
    if (current.activeBranch || current.branchSelectionPending) {
      setStored(readBranchSession())
      return
    }

    const assigned = session.branch.assignedBranch
    if (assigned) {
      persistActiveBranch(assigned)
      setStored(readBranchSession())
    }
  }, [session?.branch])

  const activeBranch = stored.activeBranch ?? branchConfig.assignedBranch
  const showPickerGate =
    branchConfig.enableMultipleBranches && branchConfig.canSwitchBranch !== false

  const openBranchPicker = useCallback(() => {
    if (!showPickerGate) return
    persistBranchPending(true)
    setStored(readBranchSession())
  }, [showPickerGate])

  const confirmBranch = useCallback(
    (branch: BranchSummary) => {
      confirmBranchSelection(branch)
      setStored(readBranchSession())
      clearBranchOptionsCache()
      void queryClient.invalidateQueries({ queryKey: ['pagedata'] })
      void queryClient.invalidateQueries({ queryKey: ['rolecentre'] })
    },
    [queryClient],
  )

  const value = useMemo<BranchContextValue>(
    () => ({
      activeBranch,
      assignedBranch: branchConfig.assignedBranch,
      enableMultipleBranches: branchConfig.enableMultipleBranches,
      canSwitchBranch: branchConfig.canSwitchBranch !== false,
      branchScope: stored.branchScope ?? 'single',
      branchSelectionPending: stored.branchSelectionPending && showPickerGate,
      openBranchPicker,
      confirmBranch,
    }),
    [
      activeBranch,
      branchConfig,
      confirmBranch,
      openBranchPicker,
      showPickerGate,
      stored.branchSelectionPending,
      stored.branchScope,
    ],
  )

  return <BranchContext.Provider value={value}>{children}</BranchContext.Provider>
}

export function useBranch() {
  const ctx = useContext(BranchContext)
  if (!ctx) {
    throw new Error('useBranch must be used within BranchProvider')
  }
  return ctx
}

/** Safe optional hook for components outside dashboard shell. */
export function useBranchOptional() {
  return useContext(BranchContext)
}
