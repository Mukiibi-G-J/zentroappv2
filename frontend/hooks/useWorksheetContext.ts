'use client'

import { useMemo } from 'react'
import { usePathname, useRouter, useSearchParams } from 'next/navigation'
import { usePage, usePages } from '@/hooks/usePage'
import { usePageDataList, usePageDataRecord } from '@/hooks/usePageData'
import type { Page } from '@/types/page'

export const DEFAULT_JOURNAL_BATCH = 'DEFAULT'

export function useWorksheetContext(page: Page | undefined) {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()

  const contextKeyField = page?.ContextKeyField || 'name'
  const isFinancialReportOverview = page?.Name === 'FinancialReportOverview'
  const isRowDefinitionWorksheet = page?.Name === 'FinancialReportRowDefinition'
  const ctxFromDrillDown = searchParams.get('ctx')
  const activeBatch =
    ((isFinancialReportOverview || isRowDefinitionWorksheet) && ctxFromDrillDown)
    || searchParams.get('batch')
    || DEFAULT_JOURNAL_BATCH
  const contextLabel = searchParams.get('ctxLabel')

  const setActiveBatch = (batchName: string) => {
    const params = new URLSearchParams(searchParams.toString())
    if (isFinancialReportOverview || isRowDefinitionWorksheet) {
      params.set('ctx', batchName)
      params.delete('batch')
    } else {
      params.set('batch', batchName)
    }
    router.replace(`${pathname}?${params.toString()}`)
  }

  const { data: headerPage } = usePage(page?.HeaderPageId ?? undefined)
  const { data: allPages = [] } = usePages()

  // The List page whose CardPageId points to the header Card page
  const headerListPage = useMemo(
    () => allPages.find((p) => p.CardPageId === page?.HeaderPageId),
    [allPages, page?.HeaderPageId],
  )

  const headerListControl = headerListPage?.PageControls.find(
    (c) => c.ControlType === 'Repeater' || c.ControlType === 'Group',
  )

  const headerPageId = headerListPage?.PageId ?? 0
  const headerControlId = headerListControl?.PageControlId

  // Fetch all batches for the dropdown
  const { data: allBatches = [] } = usePageDataList(
    headerPageId,
    headerControlId,
    '',
    200,
  )

  // Fetch the currently active batch record
  const { data: batchMatches = [] } = usePageDataList(
    headerPageId,
    headerControlId,
    '',
    50,
    { [contextKeyField]: activeBatch },
  )

  const batchListRecord = batchMatches[0]
  const batchSystemId = batchListRecord?.SystemId
    ? String(batchListRecord.SystemId)
    : undefined

  const { data: headerCardRecord } = usePageDataRecord(
    headerPage?.PageId ?? 0,
    undefined,
    isFinancialReportOverview ? batchSystemId : undefined,
    { cardPage: true },
  )

  const batchRecord =
    isFinancialReportOverview && headerCardRecord
      ? headerCardRecord
      : batchListRecord

  const batchOptions = useMemo(
    () =>
      allBatches
        .map((b) => ({
          value: String(b[contextKeyField] ?? ''),
          label: String(b[contextKeyField] ?? ''),
          caption: b.description ? String(b.description) : null,
        }))
        .filter((o) => o.value),
    [allBatches, contextKeyField],
  )

  // Filters passed to the worksheet line query
  const lineFilters: Record<string, string> = useMemo(() => {
    if (isFinancialReportOverview) {
      const rowGroup = batchRecord?.row_definition
      if (rowGroup === null || rowGroup === undefined || rowGroup === '') return {}
      return { row_group: String(rowGroup) }
    }
    if (isRowDefinitionWorksheet && page?.ContextFilterField && activeBatch) {
      return { [page.ContextFilterField]: activeBatch }
    }
    if (!page?.ContextFilterField) return {}
    return { [page.ContextFilterField]: activeBatch }
  }, [
    isFinancialReportOverview,
    isRowDefinitionWorksheet,
    batchRecord?.row_definition,
    page?.ContextFilterField,
    activeBatch,
  ])

  // Default values injected into every new line
  const lineDefaults: Record<string, unknown> = useMemo(() => {
    if (isRowDefinitionWorksheet && page?.ContextFilterField && activeBatch) {
      return { [page.ContextFilterField]: activeBatch }
    }
    return { batch_name: activeBatch }
  }, [isRowDefinitionWorksheet, page?.ContextFilterField, activeBatch])

  const hasHeader = !!(page?.HeaderPageId && page?.ContextFilterField)

  return {
    activeBatch,
    setActiveBatch,
    batchRecord,
    batchOptions,
    headerPage,
    headerListPage,
    lineFilters,
    lineDefaults,
    hasHeader,
    contextKeyField,
    contextLabel,
    isFinancialReportOverview,
    isRowDefinitionWorksheet,
  }
}
