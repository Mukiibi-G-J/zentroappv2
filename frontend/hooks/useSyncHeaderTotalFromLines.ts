'use client'

import { useEffect, useMemo, type Dispatch, type SetStateAction } from 'react'
import type { PageControl } from '@/types/page'
import type { DataRecord } from '@/types/pagedata'

export function headerShowsTotalField(groups: PageControl[]): boolean {
  return groups.some((g) => g.Fields.some((f) => f.Name === 'total_amount' && f.Visible))
}

/** Keep header total_amount in sync with loaded document lines (computed field on server). */
export function useSyncHeaderTotalFromLines(
  setLocalRecord: Dispatch<SetStateAction<DataRecord | null>>,
  options: {
    lineTotal: number
    linesLoading: boolean
    recordReady: boolean
    headerGroups: PageControl[]
  },
) {
  const showTotal = useMemo(
    () => headerShowsTotalField(options.headerGroups),
    [options.headerGroups],
  )

  useEffect(() => {
    if (!options.recordReady || !showTotal || options.linesLoading) return
    setLocalRecord((prev) => {
      if (!prev) return prev
      if (Number(prev.total_amount) === options.lineTotal) return prev
      return { ...prev, total_amount: options.lineTotal }
    })
  }, [
    options.lineTotal,
    options.linesLoading,
    options.recordReady,
    showTotal,
    setLocalRecord,
  ])
}
