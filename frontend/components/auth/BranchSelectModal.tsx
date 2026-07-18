'use client'

import { useCallback, useEffect, useState } from 'react'
import { Check, MapPin } from 'lucide-react'
import { useBranch } from '@/context/BranchContext'
import { fetchBranchOptions } from '@/services/branchOptions.service'
import type { BranchSummary } from '@/types/auth'
import { cn } from '@/lib/utils'

export function BranchSelectModal() {
  const {
    branchSelectionPending,
    canSwitchBranch,
    enableMultipleBranches,
    activeBranch,
    assignedBranch,
    confirmBranch,
  } = useBranch()

  const [branches, setBranches] = useState<BranchSummary[]>([])
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [confirming, setConfirming] = useState(false)

  const isOpen = branchSelectionPending && enableMultipleBranches && canSwitchBranch

  useEffect(() => {
    if (!isOpen) return

    let cancelled = false
    setLoading(true)
    setLoadError(null)

    void fetchBranchOptions()
      .then((values) => {
        if (cancelled) return
        setBranches(values)
        const defaultId =
          activeBranch?.id ?? assignedBranch?.id ?? values[0]?.id ?? null
        setSelectedId(defaultId)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setBranches([])
        setLoadError(err instanceof Error ? err.message : 'Could not load branches.')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [isOpen, activeBranch?.id, assignedBranch?.id])

  const handleConfirm = useCallback(() => {
    if (selectedId == null) return
    const branch = branches.find((b) => b.id === selectedId)
    if (!branch) return
    setConfirming(true)
    confirmBranch(branch)
    setConfirming(false)
  }, [branches, confirmBranch, selectedId])

  if (!isOpen) return null

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="branch-select-title"
    >
      <div className="flex max-h-[90dvh] w-full max-w-md flex-col overflow-hidden rounded-xl bg-white shadow-2xl">
        <div className="flex flex-col p-6">
          <div className="mb-1 flex items-center gap-2 text-p1">
            <MapPin className="h-5 w-5 shrink-0" aria-hidden />
            <h2 id="branch-select-title" className="text-xl font-bold text-mainTextColor">
              Select Branch
            </h2>
          </div>
          <p className="mb-5 text-sm text-bodyText">
            Choose the branch you want to work with for this session.
          </p>

          {loading ? (
            <div className="flex items-center justify-center py-12">
              <div className="h-8 w-8 animate-spin rounded-full border-2 border-p1 border-t-transparent" />
            </div>
          ) : branches.length === 0 ? (
            <p className="text-sm text-bodyText">
              {loadError ??
                'No branches are configured. Contact your administrator to set up branches.'}
            </p>
          ) : (
            <>
              <ul className="mb-5 max-h-[min(24rem,50dvh)] space-y-2 overflow-y-auto">
                {branches.map((branch) => {
                  const isSelected = selectedId === branch.id
                  return (
                    <li key={branch.id}>
                      <button
                        type="button"
                        onClick={() => setSelectedId(branch.id)}
                        className={cn(
                          'flex w-full items-center gap-3 rounded-xl border-2 p-4 text-left transition-colors',
                          isSelected
                            ? 'border-p1 bg-p1/5 shadow-sm'
                            : 'border-strokeColor hover:border-p1/40 hover:bg-softBg',
                        )}
                      >
                        <span
                          className={cn(
                            'flex h-6 w-6 shrink-0 items-center justify-center rounded-full',
                            isSelected
                              ? 'bg-p1 text-white'
                              : 'border-2 border-strokeColor bg-white',
                          )}
                        >
                          {isSelected && <Check className="h-3.5 w-3.5" strokeWidth={3} />}
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="block truncate font-semibold text-mainTextColor">
                            {branch.code}
                          </span>
                          {branch.description && branch.description !== branch.code && (
                            <span className="mt-0.5 block truncate text-sm text-bodyText">
                              {branch.description}
                            </span>
                          )}
                        </span>
                      </button>
                    </li>
                  )
                })}
              </ul>
              <button
                type="button"
                disabled={selectedId == null || confirming}
                onClick={handleConfirm}
                className={cn(
                  'h-10 w-full rounded-lg bg-p1 text-sm font-medium text-white transition-colors',
                  'hover:bg-p1/90 disabled:pointer-events-none disabled:opacity-50',
                )}
              >
                {confirming ? 'Continuing…' : 'Continue'}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
