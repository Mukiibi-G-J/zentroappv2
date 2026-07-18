'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { useQueryClient } from '@tanstack/react-query'
import { ArrowLeft } from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import { usePage, usePages } from '@/hooks/usePage'
import { usePageDataList, useUpdateField, useDeleteRecord, useCreateRecord } from '@/hooks/usePageData'
import { useWorksheetContext } from '@/hooks/useWorksheetContext'
import { findWorksheetLinesControl } from '@/lib/worksheetControls'
import { worksheetFrozenFieldProps } from '@/lib/worksheetColumns'
import { getFieldCaption } from '@/lib/fieldCaption'
import { extractApiErrorMessage } from '@/lib/apiError'
import { extractErrorMessage } from '@/services/pagedata.service'
import { listFieldValuesEqual, normalizeListFieldSaveValue } from '@/lib/listFieldValue'
import { getRecordFieldValue, recordFieldValuesEqual } from '@/lib/recordFieldValue'
import {
  hasContextRelation,
  contextRelationCacheKey,
  buildRelationRecordValues,
  collectContextValuesFromRecords,
  defaultValuesFromContextRelations,
  getDependentRelationFields,
} from '@/lib/contextRelations'
import { formatRelationDisplay, resolveRelationSelectValue } from '@/lib/relationDisplay'
import { mapTableRelationValue, type RelationOption } from '@/hooks/useRelationOptions'
import { pageService } from '@/services/page.service'
import { listDashboardPath, getCardRecordPath, getPageRouteId } from '@/lib/pageRoutes'
import DynamicField from './DynamicField'
import { ConfirmDialog } from '@/components/ui/ConfirmDialog'
import SearchableRelationSelect from './SearchableRelationSelect'
import WorksheetRowMenu from './WorksheetRowMenu'
import WorksheetFastTab from './WorksheetFastTab'
import FinancialReportOverviewPanel from './FinancialReportOverviewPanel'
import FinancialReportFormatModal from './FinancialReportFormatModal'
import RowDefinitionWorksheetPanel from './RowDefinitionWorksheetPanel'
import WorksheetRibbon from './WorksheetRibbon'
import JournalPreviewDialog, { type JournalPreviewContent } from './JournalPreviewDialog'
import DynamicWorksheetModal from './DynamicWorksheetModal'
import { filterVisiblePageActions } from '@/lib/pageActionVisibility'
import { resolveRibbonIcon } from '@/lib/ribbonIcon'
import {
  APPLY_CUSTOMER_ENTRIES_PAGE_NAME,
  APPLY_VENDOR_ENTRIES_PAGE_NAME,
  applyEntriesPartyKind,
  buildGeneralJournalApplyContext,
  isApplyEntriesAction,
  visibleLinePageActions,
} from '@/lib/documentLineActions'
import {
  type GridActiveCell,
  isLineFieldEditable,
  moveGridActiveCell,
  readActiveCellCommitValue,
} from '@/lib/worksheetGridKeyboard'
import { useWorksheetGridKeyboard } from '@/hooks/useWorksheetGridKeyboard'
import type { ApplyPaymentContext } from '@/lib/applyEntriesContext'
import type { Page } from '@/types/page'
import type { PageAction, PageControlField } from '@/types/page'
import type { DataRecord } from '@/types/pagedata'
import {
  buildAmountsByLineNo,
  dateRangeForPeriodType,
  defaultFinancialReportDateRange,
  downloadBase64File,
  financialReportAmountFieldName,
  FINANCIAL_REPORT_END_DATE_FIELD,
  FINANCIAL_REPORT_PRINT_ACTION,
  FINANCIAL_REPORT_RECALCULATE_ACTION,
  FINANCIAL_REPORT_START_DATE_FIELD,
  isFinancialReportData,
  isFinancialReportDownloadContent,
  isFinancialReportPrintContent,
  openFinancialReportPrintHtml,
  reportDatesFromRecord,
  visibleFinancialReportLineNos,
  type FinancialReportData,
} from '@/lib/financialReport'

interface Props {
  pageId: number
  basePath?: string
}

const stickySelectBase =
  'w-10 min-w-10 shrink-0 px-2 text-center sticky left-0 z-20 overflow-visible shadow-[2px_0_4px_-1px_rgba(0,0,0,0.08)]'

function stickySelectCellClass(isSelected: boolean) {
  return cn(
    stickySelectBase,
    'py-2',
    isSelected ? 'bg-[#eef5f5]' : 'bg-white group-hover:bg-gray-50',
  )
}

function formatValue(value: unknown, field: PageControlField): string {
  if (value === null || value === undefined || value === '') return '—'
  if (field.FieldType === 'Boolean') return value ? 'Yes' : 'No'
  if (field.FieldType === 'Date' && value) {
    try { return new Date(String(value)).toLocaleDateString() } catch { return String(value) }
  }
  if (field.FieldType === 'Decimal') {
    return Number(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  }
  if (field.FieldType === 'Integer') return Number(value).toLocaleString()
  return String(value)
}

export default function DynamicWorksheetPage({ pageId, basePath = '/dashboard' }: Props) {
  const router = useRouter()
  const searchParams = useSearchParams()
  const qc = useQueryClient()
  const [search, setSearch] = useState('')
  const [selectedRow, setSelectedRow] = useState<string | null>(null)
  const [selectedRows, setSelectedRows] = useState<Set<string>>(() => new Set())
  const [multiSelectMode, setMultiSelectMode] = useState(false)
  const [editingCell, setEditingCell] = useState<GridActiveCell | null>(null)
  const [typeahead, setTypeahead] = useState<{ cell: GridActiveCell; char: string } | null>(null)
  const worksheetGridRef = useRef<HTMLDivElement>(null)
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null)
  const [pendingBulkDelete, setPendingBulkDelete] = useState(false)
  const [pendingAction, setPendingAction] = useState<PageAction | null>(null)
  const [financialReportModalAction, setFinancialReportModalAction] = useState<PageAction | null>(null)
  const defaultReportDates = defaultFinancialReportDateRange()
  const [reportStartDate, setReportStartDate] = useState(defaultReportDates.startDate)
  const [reportEndDate, setReportEndDate] = useState(defaultReportDates.endDate)
  const reportDatesSyncRef = useRef('')
  const [actionLoading, setActionLoading] = useState(false)
  const [postingPreview, setPostingPreview] = useState<JournalPreviewContent | null>(null)
  const [financialReportData, setFinancialReportData] = useState<FinancialReportData | null>(null)
  const [applyModalOpen, setApplyModalOpen] = useState(false)
  const [applyWorksheetPage, setApplyWorksheetPage] = useState<Page | null>(null)
  const [applyModalContext, setApplyModalContext] = useState<ApplyPaymentContext | null>(null)
  const [relationOptions, setRelationOptions] = useState<Record<number, RelationOption[]>>({})
  const [contextRelationOptions, setContextRelationOptions] = useState<
    Record<string, RelationOption[]>
  >({})
  const loadedContextOptions = useRef(new Set<string>())

  const { data: page, isLoading: pageLoading } = usePage(pageId)
  const { data: allPages = [] } = usePages()
  const worksheetCtx = useWorksheetContext(page)
  const {
    activeBatch,
    setActiveBatch,
    batchOptions,
    headerListPage,
    lineFilters,
    lineDefaults,
    hasHeader,
    batchRecord,
    headerPage,
    contextLabel,
    isFinancialReportOverview,
    isRowDefinitionWorksheet,
  } = worksheetCtx

  const backPath = useMemo(() => {
    const returnUrl = searchParams.get('return')
    if (returnUrl) return returnUrl
    if (headerListPage) return listDashboardPath(headerListPage)
    return null
  }, [searchParams, headerListPage])

  const navigateBack = useCallback(() => {
    if (backPath) router.push(backPath)
    else router.back()
  }, [backPath, router])

  // Worksheet lines: Group/Repeater bound to page source table
  const listControl = findWorksheetLinesControl(page)
  const pageControlId = listControl?.PageControlId

  const visibleFields = useMemo(
    () => listControl?.Fields.filter((f) => f.Visible) ?? [],
    [listControl?.Fields],
  )

  useEffect(() => {
    setFinancialReportData(null)
  }, [activeBatch, isFinancialReportOverview])

  useEffect(() => {
    if (!isFinancialReportOverview || !batchRecord?.SystemId) return
    const syncKey = String(batchRecord.SystemId)
    if (reportDatesSyncRef.current === syncKey) return
    reportDatesSyncRef.current = syncKey
    const range = reportDatesFromRecord(batchRecord)
    setReportStartDate(range.startDate)
    setReportEndDate(range.endDate)
  }, [batchRecord, isFinancialReportOverview])

  const reportPeriodType = String(
    (batchRecord && getRecordFieldValue(batchRecord, 'period_type')) || 'Month',
  )

  const reportDatesValid = Boolean(
    reportStartDate && reportEndDate && reportStartDate <= reportEndDate,
  )

  const financialReportFilterKey = useMemo(() => {
    if (!isFinancialReportOverview || !activeBatch || !batchRecord) return ''
    return [
      activeBatch,
      reportStartDate,
      reportEndDate,
      batchRecord.period_type,
      batchRecord.dimension_1_filter,
      batchRecord.show_all_lines,
    ]
      .map((value) => String(value ?? ''))
      .join('|')
  }, [
    activeBatch,
    batchRecord,
    isFinancialReportOverview,
    reportEndDate,
    reportStartDate,
  ])

  const financialReportAmountsByLine = useMemo(
    () => (financialReportData ? buildAmountsByLineNo(financialReportData) : null),
    [financialReportData],
  )

  const financialReportVisibleLineNos = useMemo(
    () => (financialReportData ? visibleFinancialReportLineNos(financialReportData) : null),
    [financialReportData],
  )

  const displayFields = useMemo(() => {
    if (!isFinancialReportOverview || !financialReportData?.columns.length) {
      return visibleFields
    }
    const amountFields: PageControlField[] = financialReportData.columns.map((column, index) => ({
      FieldId: 9_000_000 + column.line_no,
      PageId: pageId,
      PageControlId: listControl?.PageControlId ?? 0,
      PageControlFieldId: 9_000_000 + column.line_no,
      Name: financialReportAmountFieldName(column.key),
      Caption: column.header || `Column ${column.line_no}`,
      FieldType: 'Decimal',
      Visible: true,
      Editable: false,
      PrimaryKey: false,
      Required: false,
      TabIndex: visibleFields.length + index,
    }))
    return [...visibleFields, ...amountFields]
  }, [financialReportData, isFinancialReportOverview, listControl?.PageControlId, pageId, visibleFields])

  const { data: records = [], isLoading: dataLoading, refetch, isFetching } = usePageDataList(
    pageId,
    listControl?.PageControlId,
    search,
    500,
    lineFilters,
  )

  const displayRecords = useMemo(() => {
    if (!isFinancialReportOverview || !financialReportVisibleLineNos) {
      return records
    }
    return records.filter((record) => {
      const lineNo = Number(getRecordFieldValue(record, 'line_no'))
      return financialReportVisibleLineNos.has(lineNo)
    })
  }, [financialReportVisibleLineNos, isFinancialReportOverview, records])

  const contextRelationFields = useMemo(
    () => visibleFields.filter((f) => hasContextRelation(f)),
    [visibleFields],
  )

  const contextRelationDefaults = useMemo(
    () => defaultValuesFromContextRelations(listControl?.Fields ?? []),
    [listControl?.Fields],
  )

  const updateField = useUpdateField(pageId, listControl?.PageControlId)
  const deleteRecord = useDeleteRecord(pageId, listControl?.PageControlId ?? 0)
  const createRecord = useCreateRecord(pageId, listControl?.PageControlId ?? 0, listControl?.Fields ?? [])

  const headerCardControl = headerPage?.PageControls.find((c) => c.ControlType === 'Group')
  const updateHeaderField = useUpdateField(
    headerPage?.PageId ?? 0,
    headerCardControl?.PageControlId,
    {
      cardPage: true,
      listPageId: headerListPage?.PageId,
    },
  )

  const saveReportDateField = useCallback(
    (fieldName: 'start_date' | 'end_date', value: string) => {
      if (!batchRecord?.SystemId || !headerPage?.PageId) return
      const field: PageControlField = {
        ...(fieldName === 'start_date'
          ? FINANCIAL_REPORT_START_DATE_FIELD
          : FINANCIAL_REPORT_END_DATE_FIELD),
        FieldId: 0,
        PageId: headerPage.PageId,
        PageControlId: headerCardControl?.PageControlId ?? 0,
        PageControlFieldId: fieldName === 'start_date' ? -9001 : -9002,
        Visible: false,
        Editable: true,
        PrimaryKey: false,
        Required: false,
        TabIndex: 0,
      }
      const systemId = String(batchRecord.SystemId)
      qc.setQueriesData<DataRecord>(
        { queryKey: ['pagedata', 'record', headerPage.PageId, 'card', systemId] },
        (old) => (old ? { ...old, [fieldName]: value } : old),
      )
      updateHeaderField.mutate(
        { systemId, field, value },
        {
          onError: (err: unknown) => {
            qc.invalidateQueries({
              queryKey: ['pagedata', 'record', headerPage.PageId, 'card', systemId],
            })
            toast.error(extractErrorMessage(err))
          },
        },
      )
    },
    [batchRecord?.SystemId, headerCardControl?.PageControlId, headerPage?.PageId, qc, updateHeaderField],
  )

  const handleReportStartDateChange = useCallback(
    (value: string) => {
      setReportStartDate(value)
      reportDatesSyncRef.current = ''
      if (reportPeriodType === 'Day') {
        setReportEndDate(value)
        saveReportDateField('start_date', value)
        saveReportDateField('end_date', value)
        return
      }
      saveReportDateField('start_date', value)
    },
    [reportPeriodType, saveReportDateField],
  )

  const handleReportEndDateChange = useCallback(
    (value: string) => {
      setReportEndDate(value)
      reportDatesSyncRef.current = ''
      if (reportPeriodType === 'Day') {
        setReportStartDate(value)
        saveReportDateField('start_date', value)
        saveReportDateField('end_date', value)
        return
      }
      saveReportDateField('end_date', value)
    },
    [reportPeriodType, saveReportDateField],
  )

  const overviewTitle = useMemo(() => {
    if (isRowDefinitionWorksheet) {
      return String(contextLabel || batchRecord?.description || activeBatch || page?.Caption || 'Row Definition')
    }
    if (!isFinancialReportOverview) return page?.Caption ?? ''
    return String(contextLabel || batchRecord?.description || activeBatch || page?.Caption || '')
  }, [isRowDefinitionWorksheet, isFinancialReportOverview, contextLabel, batchRecord, activeBatch, page?.Caption])

  const overviewSubtitle = useMemo(() => {
    if (isRowDefinitionWorksheet && batchRecord) {
      return batchRecord.description ? String(batchRecord.description) : null
    }
    if (!isFinancialReportOverview || !batchRecord) return null
    if (financialReportData?.period_label) {
      return financialReportData.period_label
    }
    const parts = [
      batchRecord.name,
      batchRecord.description,
      batchRecord.row_definition,
      batchRecord.column_definition,
    ].filter(Boolean)
    return parts.join(' - ')
  }, [isFinancialReportOverview, batchRecord, financialReportData?.period_label])

  const getWorksheetFieldValue = useCallback(
    (record: DataRecord, field: PageControlField) => {
      if (
        isFinancialReportOverview
        && field.Name.startsWith('report_amount_')
        && financialReportAmountsByLine
      ) {
        const lineNo = Number(getRecordFieldValue(record, 'line_no'))
        const colKey = field.Name.replace('report_amount_', '')
        const amounts = financialReportAmountsByLine.get(lineNo)
        return amounts?.[colKey] ?? null
      }
      return getRecordFieldValue(record, field.Name)
    },
    [financialReportAmountsByLine, isFinancialReportOverview],
  )

  const handleOverviewFieldSave = useCallback(
    (field: PageControlField, value: unknown) => {
      if (!batchRecord?.SystemId || !headerPage?.PageId) return

      const systemId = String(batchRecord.SystemId)
      const currentValue = getRecordFieldValue(batchRecord, field.Name)

      if (field.Name === 'period_type') {
        const periodType = String(value || 'Month')
        const range = dateRangeForPeriodType(periodType)
        setReportStartDate(range.startDate)
        setReportEndDate(range.endDate)
        reportDatesSyncRef.current = systemId
        saveReportDateField('start_date', range.startDate)
        saveReportDateField('end_date', range.endDate)
      }

      if (recordFieldValuesEqual(field.Name, currentValue, value)) {
        if (field.Name === 'period_type') {
          updateHeaderField.mutate(
            { systemId, field, value },
            {
              onError: (err: unknown) => {
                qc.invalidateQueries({
                  queryKey: ['pagedata', 'record', headerPage.PageId, 'card', systemId],
                })
                toast.error(extractErrorMessage(err))
              },
            },
          )
        }
        return
      }

      qc.setQueriesData<DataRecord>(
        { queryKey: ['pagedata', 'record', headerPage.PageId, 'card', systemId] },
        (old) => (old ? { ...old, [field.Name]: value } : old),
      )

      updateHeaderField.mutate(
        { systemId, field, value },
        {
          onError: (err: unknown) => {
            qc.invalidateQueries({
              queryKey: ['pagedata', 'record', headerPage.PageId, 'card', systemId],
            })
            toast.error(extractErrorMessage(err))
          },
        },
      )
    },
    [batchRecord, headerPage?.PageId, qc, saveReportDateField, updateHeaderField],
  )

  const totals = useMemo(() => {
    const amount = records.reduce(
      (sum, r) => sum + (Number(getRecordFieldValue(r, 'amount')) || 0),
      0,
    )
    let totalBalance = 0
    let balance = 0
    for (const record of records) {
      const debit = Number(getRecordFieldValue(record, 'debit_amount')) || 0
      const credit = Number(getRecordFieldValue(record, 'credit_amount')) || 0
      const lineAmount =
        debit || credit
          ? debit - credit
          : Number(getRecordFieldValue(record, 'amount')) || 0
      totalBalance += lineAmount
      if (selectedRow === record.SystemId) {
        balance = totalBalance
      }
    }
    if (!selectedRow && records.length > 0) {
      balance = totalBalance
    }
    return { amount, totalBalance, balance, numberOfLines: records.length }
  }, [records, selectedRow])

  const hasAmountColumn = visibleFields.some((f) => f.Name === 'amount')
  const hasJournalBalanceFooter =
    hasAmountColumn ||
    visibleFields.some((f) => f.Name === 'debit_amount' || f.Name === 'credit_amount')

  // Load static (non-context) relation options once
  const relationFieldKey = useMemo(() => {
    if (!listControl) return ''
    return listControl.Fields
      .filter((f) => f.Visible && f.HasTableRelation)
      .map((f) => f.PageControlFieldId)
      .join(',')
  }, [listControl?.Fields])

  useEffect(() => {
    if (!listControl || !relationFieldKey) return
    const relationFields = listControl.Fields.filter(
      (f) => f.Visible && f.HasTableRelation && !hasContextRelation(f),
    )
    let cancelled = false
    ;(async () => {
      const next: typeof relationOptions = {}
      for (const field of relationFields) {
        const values = await pageService.fetchTableRelations(
          pageId,
          listControl.PageControlId,
          field.PageControlFieldId,
        )
        if (cancelled) return
        next[field.PageControlFieldId] = values.map(mapTableRelationValue)
      }
      if (!cancelled) setRelationOptions(next)
    })()
    return () => { cancelled = true }
  }, [pageId, pageControlId, relationFieldKey])

  const loadContextRelationOptions = useCallback(async (
    field: PageControlField,
    record: DataRecord | Record<string, unknown>,
  ) => {
    if (!listControl) return
    const cacheKey = contextRelationCacheKey(field, record)
    if (!cacheKey) return
    if (loadedContextOptions.current.has(cacheKey)) return
    try {
      const values = await pageService.fetchTableRelations(
        pageId,
        listControl.PageControlId,
        field.PageControlFieldId,
        null,
        buildRelationRecordValues(field, record) ?? {},
      )
      loadedContextOptions.current.add(cacheKey)
      setContextRelationOptions((prev) => ({
        ...prev,
        [cacheKey]: values.map(mapTableRelationValue),
      }))
    } catch {
      loadedContextOptions.current.delete(cacheKey)
    }
  }, [pageId, listControl])

  useEffect(() => {
    for (const field of contextRelationFields) {
      for (const value of collectContextValuesFromRecords(field, records)) {
        void loadContextRelationOptions(field, { [field.RelationContextField!]: value })
      }
    }
  }, [records, contextRelationFields, loadContextRelationOptions])

  const getFieldRelationOptions = useCallback(
    (field: PageControlField, record: DataRecord) => {
      if (hasContextRelation(field)) {
        const cacheKey = contextRelationCacheKey(field, record)
        if (!cacheKey) return []
        return contextRelationOptions[cacheKey] ?? []
      }
      return relationOptions[field.PageControlFieldId] ?? []
    },
    [contextRelationOptions, relationOptions],
  )

  const handleCreateLineError = useCallback((err: unknown) => {
    toast.error(extractApiErrorMessage(err))
  }, [])

  const handleAddRow = useCallback(() => {
    if (!page?.InsertAllowed || !listControl) return
    const maxLineNo = records.reduce((max, r) => Math.max(max, Number(r.line_no) || 0), 0)
    const isJournalLinePage = page.SourceTable === 'GeneralJournalLine'
    createRecord.mutate(
      {
        SystemId: crypto.randomUUID(),
        line_no: maxLineNo + 10000,
        ...(isJournalLinePage
          ? {
              posting_date: new Date().toISOString().slice(0, 10),
              document_type: 'Payment',
              amount: 0,
            }
          : {}),
        ...contextRelationDefaults,
        ...lineDefaults,
      },
      { onError: handleCreateLineError },
    )
  }, [page, listControl, records, createRecord, lineDefaults, contextRelationDefaults, handleCreateLineError])

  const handleInsertLineAfter = useCallback((record: DataRecord) => {
    if (!page?.InsertAllowed || !listControl) return
    const idx = records.findIndex((r) => r.SystemId === record.SystemId)
    const cur = Number(record.line_no) || 0
    const nxt = idx >= 0 && idx < records.length - 1
      ? Number(records[idx + 1].line_no) || cur + 20000
      : cur + 10000
    const newLineNo = nxt > cur + 1 ? Math.floor((cur + nxt) / 2) : cur + 10000
    const isJournalLinePage = page.SourceTable === 'GeneralJournalLine'
    createRecord.mutate(
      {
        SystemId: crypto.randomUUID(),
        line_no: newLineNo,
        ...(isJournalLinePage
          ? {
              posting_date: record.posting_date ?? new Date().toISOString().slice(0, 10),
              amount: 0,
            }
          : {}),
        ...contextRelationDefaults,
        ...lineDefaults,
      },
      { onError: handleCreateLineError },
    )
  }, [page, listControl, records, createRecord, lineDefaults, contextRelationDefaults, handleCreateLineError])

  const toggleRowSelection = useCallback((systemId: string) => {
    setSelectedRows((prev) => {
      const next = new Set(prev)
      if (next.has(systemId)) next.delete(systemId)
      else next.add(systemId)
      return next
    })
  }, [])

  const handleSelectMore = useCallback((systemId: string) => {
    if (multiSelectMode) {
      setMultiSelectMode(false)
      setSelectedRows(new Set())
      setSelectedRow(systemId)
      return
    }
    setMultiSelectMode(true)
    setSelectedRow(null)
    setSelectedRows(new Set([systemId]))
  }, [multiSelectMode])

  const isRowSelected = useCallback(
    (systemId: string) => (multiSelectMode ? selectedRows.has(systemId) : selectedRow === systemId),
    [multiSelectMode, selectedRows, selectedRow],
  )

  const handleFieldSaveError = useCallback((err: unknown) => {
    toast.error(extractApiErrorMessage(err))
  }, [])

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement
      if (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.tagName === 'SELECT') return
      if (t.closest('[class*="relation-select"]')) return
      if (e.key === 'F2') { e.preventDefault(); handleAddRow() }
      if (e.key === 'Delete' && page?.DeleteAllowed) {
        e.preventDefault()
        if (multiSelectMode && selectedRows.size > 0) setPendingBulkDelete(true)
        else if (selectedRow) setPendingDeleteId(selectedRow)
      }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [selectedRow, selectedRows, multiSelectMode, page, handleAddRow])

  const fieldEditable = useCallback(
    (field: PageControlField) =>
      isLineFieldEditable(field, !!page?.ModifyAllowed, listControl?.Editable !== false),
    [listControl?.Editable, page?.ModifyAllowed],
  )

  const focusCell = useCallback(
    (record: DataRecord, field: PageControlField, opts?: { typeahead?: string }) => {
      setSelectedRow(record.SystemId)
      const cell: GridActiveCell = { systemId: record.SystemId, field: field.Name }
      setEditingCell(cell)
      setTypeahead(
        opts?.typeahead != null && opts.typeahead !== ''
          ? { cell, char: opts.typeahead }
          : null,
      )
      if (hasContextRelation(field)) void loadContextRelationOptions(field, record)
      if (!fieldEditable(field)) {
        requestAnimationFrame(() => {
          worksheetGridRef.current?.focus({ preventScroll: true })
        })
      }
    },
    [fieldEditable, loadContextRelationOptions],
  )

  const saveFieldValue = useCallback(
    (record: DataRecord, field: PageControlField, value: unknown) => {
      const normalized = normalizeListFieldSaveValue(field, value)
      if (listFieldValuesEqual(normalized, getRecordFieldValue(record, field.Name), field)) return
      if (
        field.HasTableRelation
        && (normalized == null || normalized === '')
        && getRecordFieldValue(record, field.Name) != null
        && getRecordFieldValue(record, field.Name) !== ''
      ) {
        return
      }

      const mutationOpts = { onError: handleFieldSaveError }

      const dependentFields = getDependentRelationFields(listControl?.Fields ?? [], field.Name)
      if (dependentFields.length > 0) {
        updateField.mutate({ systemId: record.SystemId, field, value: normalized }, mutationOpts)
        for (const dep of dependentFields) {
          void loadContextRelationOptions(dep, { ...record, [field.Name]: normalized })
          if (getRecordFieldValue(record, dep.Name)) {
            updateField.mutate({ systemId: record.SystemId, field: dep, value: null }, mutationOpts)
          }
        }
        return
      }
      updateField.mutate({ systemId: record.SystemId, field, value: normalized }, mutationOpts)
    },
    [handleFieldSaveError, listControl?.Fields, loadContextRelationOptions, updateField],
  )

  const commitActiveCell = useCallback(() => {
    if (!editingCell) return
    const record = records.find((row) => row.SystemId === editingCell.systemId)
    const field = visibleFields.find((f) => f.Name === editingCell.field)
    if (!record || !field || !fieldEditable(field)) return
    if (field.HasTableRelation) return

    const commitValue = readActiveCellCommitValue(
      document.activeElement as HTMLElement | null,
      field,
    )
    if (commitValue !== undefined) {
      saveFieldValue(record, field, commitValue)
    }
  }, [editingCell, fieldEditable, records, saveFieldValue, visibleFields])

  const navigateCell = useCallback(
    (direction: 'left' | 'right' | 'up' | 'down') => {
      commitActiveCell()
      if (!editingCell || records.length === 0) return
      const next = moveGridActiveCell(editingCell, direction, visibleFields, records)
      if (!next) return
      const record = records.find((row) => row.SystemId === next.systemId)
      const field = visibleFields.find((f) => f.Name === next.field)
      if (!record || !field) return
      focusCell(record, field)
    },
    [commitActiveCell, editingCell, focusCell, records, visibleFields],
  )

  useWorksheetGridKeyboard({
    enabled: !!page?.ModifyAllowed && records.length > 0,
    gridRef: worksheetGridRef,
    records,
    visibleFields,
    editingCell,
    selectedRowId: selectedRow,
    fieldEditable,
    focusCell,
    commitActiveCell,
    navigateCell,
    onEscape: () => setTypeahead(null),
  })

  useEffect(() => {
    if (!typeahead) return
    const timer = window.setTimeout(() => setTypeahead(null), 0)
    return () => window.clearTimeout(timer)
  }, [typeahead])

  const handleFieldBlur = (record: DataRecord, field: PageControlField, value: unknown) => {
    saveFieldValue(record, field, value)
  }

  const handleCellClick = (record: DataRecord, field: PageControlField) => {
    if (multiSelectMode) { toggleRowSelection(record.SystemId); return }
    commitActiveCell()
    setSelectedRow(record.SystemId)
    if (!fieldEditable(field)) return
    focusCell(record, field)
  }

  const handleBulkDelete = () => {
    selectedRows.forEach((id) => deleteRecord.mutate(id))
    setSelectedRows(new Set())
    setMultiSelectMode(false)
    setPendingBulkDelete(false)
  }

  const runAction = async (
    action: PageAction,
    extraPayload: Record<string, unknown> = {},
  ) => {
    setActionLoading(true)
    try {
      const result = await pageService.executePageAction(pageId, action.ActionId, {
        batchName: activeBatch,
        ...extraPayload,
      })
      if (result.Command === 'DOWNLOAD') {
        const content = result.Content
        if (isFinancialReportDownloadContent(content)) {
          downloadBase64File(content.FileBase64, content.FileName, content.MimeType)
          toast.success('Report downloaded')
          setFinancialReportModalAction(null)
          return
        }
        toast.error('Download returned no file content')
        return
      }
      if (result.Command === 'PREVIEW') {
        const content = result.Content
        if (isFinancialReportPrintContent(content)) {
          openFinancialReportPrintHtml(content.Html)
          if (content.FinancialReport) {
            setFinancialReportData(content.FinancialReport)
          }
          toast.success('Report generated')
          return
        }
        if (content && typeof content === 'object' && 'Entries' in content) {
          setPostingPreview(content as JournalPreviewContent)
        } else {
          toast.error('Preview returned no entries')
        }
        return
      }
      const message =
        result.Message ||
        (typeof result.Content === 'object' && (result.Content as { Message?: string })?.Message
          ? (result.Content as { Message: string }).Message
          : typeof result.Content === 'string'
            ? result.Content
            : `${action.Caption} completed`)
      if (typeof result.Content === 'object' && result.Content !== null && 'FinancialReport' in result.Content) {
        const reportPayload = (result.Content as { FinancialReport?: unknown }).FinancialReport
        if (isFinancialReportData(reportPayload)) {
          setFinancialReportData(reportPayload)
        }
      }
      toast.success(message)
      if (result.Command === 'REFRESH' || result.Command === 'MESSAGE') refetch()
      setFinancialReportModalAction(null)
    } catch (err) {
      toast.error(extractApiErrorMessage(err))
    } finally {
      setActionLoading(false)
      setPendingAction(null)
    }
  }

  const pageActions = useMemo(
    () => (page?.PageActions ?? []).filter((a) => a.Visible),
    [page?.PageActions],
  )

  const recalculateFinancialReportAction = useMemo(
    () => pageActions.find((action) => action.Name === FINANCIAL_REPORT_RECALCULATE_ACTION),
    [pageActions],
  )

  const recalculateFinancialReport = useCallback(
    async ({ silent = false }: { silent?: boolean } = {}) => {
      if (!recalculateFinancialReportAction || !activeBatch || !reportDatesValid) return
      setActionLoading(true)
      try {
        const result = await pageService.executePageAction(
          pageId,
          recalculateFinancialReportAction.ActionId,
          {
            batchName: activeBatch,
            startDate: reportStartDate,
            endDate: reportEndDate,
          },
        )
        if (
          typeof result.Content === 'object'
          && result.Content !== null
          && 'FinancialReport' in result.Content
        ) {
          const reportPayload = (result.Content as { FinancialReport?: unknown }).FinancialReport
          if (isFinancialReportData(reportPayload)) {
            setFinancialReportData(reportPayload)
          }
        }
        if (!silent) toast.success('Report recalculated')
      } catch (err) {
        toast.error(extractApiErrorMessage(err))
      } finally {
        setActionLoading(false)
      }
    },
    [
      activeBatch,
      pageId,
      recalculateFinancialReportAction,
      reportDatesValid,
      reportEndDate,
      reportStartDate,
    ],
  )

  useEffect(() => {
    if (!isFinancialReportOverview || !financialReportFilterKey || !reportDatesValid) return
    const timer = window.setTimeout(() => {
      void recalculateFinancialReport({ silent: true })
    }, 450)
    return () => window.clearTimeout(timer)
  }, [
    financialReportFilterKey,
    isFinancialReportOverview,
    recalculateFinancialReport,
    reportDatesValid,
  ])

  const applyVendorEntriesPage = useMemo(
    () => allPages.find((p) => p.Name === APPLY_VENDOR_ENTRIES_PAGE_NAME),
    [allPages],
  )
  const applyCustomerEntriesPage = useMemo(
    () => allPages.find((p) => p.Name === APPLY_CUSTOMER_ENTRIES_PAGE_NAME),
    [allPages],
  )

  const selectedLineRecord = useMemo(
    () => records.find((r) => r.SystemId === selectedRow) ?? null,
    [records, selectedRow],
  )

  const applyLineActions = useMemo(
    () => pageActions.filter(isApplyEntriesAction),
    [pageActions],
  )

  const batchPageActions = useMemo(
    () => pageActions.filter((a) => !isApplyEntriesAction(a)),
    [pageActions],
  )

  const ribbonPageActions = useMemo(() => {
    const lineActions = selectedLineRecord
      ? filterVisiblePageActions(applyLineActions, selectedLineRecord)
      : []
    return [...batchPageActions, ...lineActions]
  }, [batchPageActions, applyLineActions, selectedLineRecord])

  const resolveApplyWorksheetPage = useCallback(
    (line: DataRecord) => {
      const actions = visibleLinePageActions(applyLineActions, line)
      const action = actions[0]
      if (!action) return undefined
      return applyEntriesPartyKind(action) === 'customer'
        ? applyCustomerEntriesPage
        : applyVendorEntriesPage
    },
    [applyCustomerEntriesPage, applyLineActions, applyVendorEntriesPage],
  )

  const openApplyForLine = useCallback(
    (line: DataRecord) => {
      if (String(line.status ?? '').trim().toLowerCase() === 'posted') {
        toast.error('Cannot apply entries on a posted line')
        return
      }
      const worksheetPage = resolveApplyWorksheetPage(line)
      if (!worksheetPage) {
        toast.error('Run seed_pages to configure Apply Entries worksheets')
        return
      }
      const ctx = buildGeneralJournalApplyContext(line)
      if (!ctx) {
        toast.error('Set Account Type to Customer or Vendor and choose an Account No.')
        return
      }
      setSelectedRow(line.SystemId)
      setApplyWorksheetPage(worksheetPage)
      setApplyModalContext({
        ...ctx,
        onApplied: () => {
          void refetch()
        },
      })
      setApplyModalOpen(true)
    },
    [refetch, resolveApplyWorksheetPage],
  )

  const rowApplyExtraItems = useCallback(
    (line: DataRecord) => {
      if (String(line.status ?? '').trim().toLowerCase() === 'posted') return []
      return visibleLinePageActions(applyLineActions, line).map((action) => {
        const Icon = resolveRibbonIcon(action.ImageUrl)
        const worksheetPage = applyEntriesPartyKind(action) === 'customer'
          ? applyCustomerEntriesPage
          : applyVendorEntriesPage
        return {
          id: `action-${action.ActionId}`,
          label: action.Caption,
          icon: Icon,
          disabled: !worksheetPage,
          onClick: () => openApplyForLine(line),
        }
      })
    },
    [applyCustomerEntriesPage, applyLineActions, applyVendorEntriesPage, openApplyForLine],
  )

  const handleActionClick = (action: PageAction) => {
    if (isApplyEntriesAction(action)) {
      if (!selectedLineRecord) {
        toast.error('Select a journal line first')
        return
      }
      if (!filterVisiblePageActions([action], selectedLineRecord).length) {
        toast.error('Apply Entries is not available for this line')
        return
      }
      openApplyForLine(selectedLineRecord)
      return
    }

    if (isFinancialReportOverview && action.Name === FINANCIAL_REPORT_RECALCULATE_ACTION) {
      if (!activeBatch) {
        toast.error('Select a financial report first')
        return
      }
      void recalculateFinancialReport({ silent: false })
      return
    }

    if (isFinancialReportOverview && action.Name === FINANCIAL_REPORT_PRINT_ACTION) {
      if (!activeBatch) {
        toast.error('Select a financial report first')
        return
      }
      if (!reportDatesValid) {
        toast.error('Choose a valid date range in Options')
        return
      }
      setFinancialReportModalAction(action)
      return
    }

    const target = (action.ActionRelativeUrl || '').trim()
    if (target && !target.startsWith('#')) {
      const targetPageName = target.split('?', 1)[0]
      const targetPage = allPages.find((p) => p.Name === targetPageName)
      if (targetPage?.PageType === 'Card' && batchRecord?.SystemId) {
        router.push(
          getCardRecordPath(
            targetPage.PageId,
            String(batchRecord.SystemId),
            'Card',
            headerListPage
              ? { fromList: String(getPageRouteId(headerListPage)) }
              : undefined,
          ),
        )
        return
      }
    }

    if (action.RequiresConfirmation && action.ConfirmationMessage) {
      setPendingAction(action)
    } else {
      runAction(action)
    }
  }

  const gridFields = isFinancialReportOverview ? displayFields : visibleFields
  const gridRecords = isFinancialReportOverview ? displayRecords : records

  if (pageLoading) return <WorksheetSkeleton />

  return (
    <div className="flex-1 min-h-0 overflow-y-auto space-y-3">
      <div className="flex items-start gap-3">
        {backPath ? (
          <button
            type="button"
            onClick={navigateBack}
            className="mt-0.5 shrink-0 rounded-lg p-2 text-bodyText transition hover:bg-gray-100"
            title="Back"
          >
            <ArrowLeft size={16} />
          </button>
        ) : null}
        <div className="min-w-0">
          <h2 className="text-xl font-semibold text-mainTextColor">{overviewTitle}</h2>
          {overviewSubtitle ? (
            <p className="mt-1 text-sm font-medium text-mainTextColor">{overviewSubtitle}</p>
          ) : null}
        </div>
      </div>

      {isFinancialReportOverview && hasHeader ? (
        <FinancialReportOverviewPanel
          headerPage={headerPage}
          reportRecord={batchRecord}
          reportOptions={batchOptions}
          activeReportName={activeBatch}
          onReportChange={setActiveBatch}
          onFieldSave={handleOverviewFieldSave}
          startDate={reportStartDate}
          endDate={reportEndDate}
          onStartDateChange={handleReportStartDateChange}
          onEndDateChange={handleReportEndDateChange}
          readOnly={page?.ModifyAllowed === false}
        />
      ) : isRowDefinitionWorksheet && hasHeader ? (
        <RowDefinitionWorksheetPanel
          definitionOptions={batchOptions}
          activeDefinitionName={activeBatch}
          onDefinitionChange={setActiveBatch}
        />
      ) : hasHeader ? (
        <WorksheetFastTab
          batchOptions={batchOptions}
          activeBatch={activeBatch}
          onBatchChange={setActiveBatch}
        />
      ) : null}

      <WorksheetRibbon
        pageActions={ribbonPageActions}
        insertAllowed={!!page?.InsertAllowed}
        search={search}
        onSearch={setSearch}
        onRefresh={() => refetch()}
        onAddNew={handleAddRow}
        onAction={handleActionClick}
        onOpenBatches={
          headerListPage
            ? () => router.push(listDashboardPath(headerListPage))
            : undefined
        }
        isRefreshing={isFetching}
        isAdding={createRecord.isPending}
        actionLoading={actionLoading}
      />

      <div
        ref={worksheetGridRef}
        tabIndex={0}
        className="rounded-xl border border-gray-200 bg-white overflow-x-auto max-h-[60vh] overflow-y-auto outline-none"
      >
        <table className="min-w-max text-sm">
          <thead className="sticky top-0 z-30">
            <tr className="bg-gray-50 border-b border-gray-200">
              <th className={cn(stickySelectBase, 'py-3 z-50 bg-gray-50')} />
              {gridFields.map((f, fi) => {
                const frozen = worksheetFrozenFieldProps(gridFields, fi, 'header')
                return (
                  <th key={f.FieldId} className={frozen.className} style={frozen.style}>
                    {getFieldCaption(f, page)}
                  </th>
                )
              })}
            </tr>
          </thead>

          <tbody className="divide-y divide-gray-100 [&_td]:overflow-visible">
            {dataLoading ? (
              [...Array(5)].map((_, i) => (
                <tr key={i}>
                  <td className={cn(stickySelectBase, 'py-3 bg-white')} />
                  {gridFields.map((f, fi) => {
                    const frozen = worksheetFrozenFieldProps(gridFields, fi, 'skeleton')
                    return (
                      <td key={f.FieldId} className={frozen.className} style={frozen.style}>
                        <div className="h-4 bg-gray-100 rounded animate-pulse" />
                      </td>
                    )
                  })}
                </tr>
              ))
            ) : gridRecords.length === 0 ? (
              <tr>
                <td colSpan={gridFields.length + 1} className="px-4 py-12 text-center text-bodyText">
                  {isFinancialReportOverview
                    ? 'No report lines — choose a report and click Recalculate'
                    : 'No lines — press F2 or Add New to create a line'}
                </td>
              </tr>
            ) : (
              gridRecords.map((record) => {
                const rowSelected = isRowSelected(record.SystemId)
                const isHeaderRow =
                  isFinancialReportOverview && String(record.row_type ?? '') === 'Header'
                return (
                  <tr
                    key={record.SystemId}
                    className={cn(
                      'group transition',
                      rowSelected ? 'bg-s1/5' : 'hover:bg-gray-50',
                      isHeaderRow && !rowSelected && 'bg-sky-50/80',
                    )}
                  >
                    <td className={stickySelectCellClass(rowSelected)}>
                      {multiSelectMode ? (
                        <input
                          type="checkbox"
                          checked={selectedRows.has(record.SystemId)}
                          onChange={() => toggleRowSelection(record.SystemId)}
                          onClick={(e) => e.stopPropagation()}
                          className="accent-s1"
                        />
                      ) : (
                        <input
                          type="radio"
                          name="worksheet-row"
                          checked={selectedRow === record.SystemId}
                          onChange={() => setSelectedRow(record.SystemId)}
                          className="accent-s1"
                        />
                      )}
                    </td>

                    {gridFields.map((field, fi) => {
                      const canEdit = fieldEditable(field)
                      const isActive =
                        editingCell?.systemId === record.SystemId && editingCell.field === field.Name
                      const isEditing = isActive && canEdit
                      const fieldValue = getWorksheetFieldValue(record, field)
                      const options = field.HasTableRelation
                        ? getFieldRelationOptions(field, record)
                        : []
                      const caption = getFieldCaption(field, page)
                      const typeaheadChar =
                        typeahead?.cell.systemId === record.SystemId
                        && typeahead?.cell.field === field.Name
                          ? typeahead.char
                          : undefined
                      const frozen = worksheetFrozenFieldProps(gridFields, fi, 'body', {
                        isSelected: rowSelected,
                        extraClass: canEdit ? 'cursor-text' : undefined,
                      })

                      const cellContent = isEditing ? (
                        field.HasTableRelation ? (
                          <SearchableRelationSelect
                            autoFocus
                            initialInput={typeaheadChar}
                            options={options}
                            value={resolveRelationSelectValue(fieldValue, options)}
                            placeholder={`Search ${caption}…`}
                            onChange={(val) => handleFieldBlur(record, field, val)}
                          />
                        ) : (
                          <DynamicField
                            field={field}
                            value={fieldValue}
                            singleLine
                            autoFocus
                            initialInput={typeaheadChar}
                            onBlur={(value) => handleFieldBlur(record, field, value)}
                          />
                        )
                      ) : (
                        <span className="text-mainTextColor truncate">
                          {field.HasTableRelation && options.length > 0
                            ? formatRelationDisplay(fieldValue, field, options)
                            : formatValue(fieldValue, field)}
                        </span>
                      )

                      return (
                        <td
                          key={field.FieldId}
                          className={cn(
                            frozen.className,
                            isActive && !isEditing && 'ring-2 ring-s1/30 ring-inset',
                          )}
                          style={frozen.style}
                          onClick={() => handleCellClick(record, field)}
                        >
                          {fi === 0 ? (
                            <div className="flex items-center gap-1.5 min-w-0">
                              <WorksheetRowMenu
                                insertAllowed={!!page?.InsertAllowed}
                                deleteAllowed={!!page?.DeleteAllowed}
                                multiSelectActive={multiSelectMode}
                                rowSelected={rowSelected}
                                onNewLine={() => handleInsertLineAfter(record)}
                                onDeleteLine={() => setPendingDeleteId(record.SystemId)}
                                onSelectMore={() => handleSelectMore(record.SystemId)}
                                extraItems={rowApplyExtraItems(record)}
                              />
                              <div className="min-w-0 flex-1">{cellContent}</div>
                            </div>
                          ) : (
                            cellContent
                          )}
                        </td>
                      )
                    })}
                  </tr>
                )
              })
            )}
          </tbody>

          {hasAmountColumn && records.length > 0 && (
            <tfoot>
              <tr className="bg-gray-50 border-t border-gray-200 font-medium">
                <td className={cn(stickySelectBase, 'py-3 z-20 bg-gray-50')} />
                {visibleFields.map((field, fi) => {
                  const frozen = worksheetFrozenFieldProps(visibleFields, fi, 'footer', {
                    extraClass: field.Name === 'amount' ? 'text-right' : undefined,
                  })
                  if (field.Name === 'amount') {
                    return (
                      <td key={field.FieldId} className={cn(frozen.className, 'text-mainTextColor')} style={frozen.style}>
                        {totals.amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </td>
                    )
                  }
                  return <td key={field.FieldId} className={frozen.className} style={frozen.style} />
                })}
              </tr>
            </tfoot>
          )}
        </table>
      </div>

      <div className="flex items-center justify-between gap-3 flex-wrap">
        <p className="text-xs text-bodyText">
          {gridRecords.length} line{gridRecords.length !== 1 ? 's' : ''}
          {isFinancialReportOverview && records.length !== gridRecords.length && (
            <span className="ml-1 text-bodyText/70">
              (of {records.length})
            </span>
          )}
          {hasHeader && (
            <span className="ml-2">
              · Batch <span className="font-medium text-mainTextColor">{activeBatch}</span>
            </span>
          )}
          {multiSelectMode && selectedRows.size > 0 && (
            <span className="ml-2 text-s1">{selectedRows.size} selected</span>
          )}
        </p>
        {hasJournalBalanceFooter && records.length > 0 && (
          <div className="flex items-center gap-4 text-xs text-bodyText">
            <span>
              Number of Lines{' '}
              <span className="font-medium text-mainTextColor tabular-nums">
                {totals.numberOfLines}
              </span>
            </span>
            <span>
              Balance{' '}
              <span className="font-medium text-mainTextColor tabular-nums">
                {totals.balance.toLocaleString(undefined, {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2,
                })}
              </span>
            </span>
            <span>
              Total Balance{' '}
              <span className="font-medium text-mainTextColor tabular-nums">
                {totals.totalBalance.toLocaleString(undefined, {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2,
                })}
              </span>
            </span>
          </div>
        )}
        {multiSelectMode && selectedRows.size > 0 && page?.DeleteAllowed && (
          <button
            type="button"
            onClick={() => setPendingBulkDelete(true)}
            className="text-xs font-medium text-red-600 hover:text-red-700"
          >
            Delete {selectedRows.size} line{selectedRows.size !== 1 ? 's' : ''}
          </button>
        )}
      </div>

      {/* Confirm single delete */}
      {pendingDeleteId && (
        <ConfirmDialog
          open
          title="Delete line?"
          message="Delete this line?"
          confirmLabel="Delete"
          variant="danger"
          onConfirm={() => {
            deleteRecord.mutate(pendingDeleteId)
            if (selectedRow === pendingDeleteId) setSelectedRow(null)
            setPendingDeleteId(null)
          }}
          onCancel={() => setPendingDeleteId(null)}
        />
      )}

      {pendingBulkDelete && (
        <ConfirmDialog
          open
          title="Delete lines?"
          message={`Delete ${selectedRows.size} selected line${selectedRows.size !== 1 ? 's' : ''}?`}
          confirmLabel="Delete"
          variant="danger"
          onConfirm={handleBulkDelete}
          onCancel={() => setPendingBulkDelete(false)}
        />
      )}

      {pendingAction && (
        <ConfirmDialog
          open
          title={pendingAction.Caption}
          message={pendingAction.ConfirmationMessage ?? 'Proceed with this action?'}
          confirmLabel={pendingAction.Caption}
          onConfirm={() => {
            if (pendingAction) runAction(pendingAction)
            setPendingAction(null)
          }}
          onCancel={() => setPendingAction(null)}
        />
      )}

      <JournalPreviewDialog
        open={postingPreview !== null}
        preview={postingPreview}
        onClose={() => setPostingPreview(null)}
      />

      <DynamicWorksheetModal
        open={applyModalOpen}
        worksheetPage={applyWorksheetPage ?? undefined}
        applyPayment={applyModalContext}
        onClose={() => {
          setApplyModalOpen(false)
          setApplyModalContext(null)
          setApplyWorksheetPage(null)
        }}
      />

      <FinancialReportFormatModal
        open={financialReportModalAction?.Name === FINANCIAL_REPORT_PRINT_ACTION}
        title={financialReportModalAction?.Caption ?? 'Print'}
        reportLabel={batchRecord?.description as string | undefined ?? activeBatch}
        loading={actionLoading}
        onClose={() => setFinancialReportModalAction(null)}
        onExportPdf={() => {
          if (!financialReportModalAction) return
          void runAction(financialReportModalAction, {
            startDate: reportStartDate,
            endDate: reportEndDate,
            format: 'pdf',
          })
        }}
        onExportExcel={() => {
          if (!financialReportModalAction) return
          void runAction(financialReportModalAction, {
            startDate: reportStartDate,
            endDate: reportEndDate,
            format: 'excel',
          })
        }}
      />
    </div>
  )
}

function WorksheetSkeleton() {
  return (
    <div className="flex flex-col w-full h-full space-y-4">
      <div className="h-8 w-56 bg-gray-200 rounded animate-pulse" />
      {/* Ribbon bar */}
      <div className="h-11 bg-white rounded-xl border border-gray-200 animate-pulse" />
      {/* Table */}
      <div className="rounded-xl border border-gray-200 bg-white overflow-hidden flex-1">
        <div className="h-11 bg-gray-50 border-b border-gray-200 px-4 flex items-center gap-4">
          {[...Array(6)].map((_, j) => (
            <div key={j} className="h-3 bg-gray-200 rounded animate-pulse flex-1" />
          ))}
        </div>
        {[...Array(10)].map((_, i) => (
          <div key={i} className="h-12 border-b border-gray-100 px-4 flex items-center gap-4" style={{ opacity: 1 - i * 0.08 }}>
            {[...Array(6)].map((_, j) => (
              <div key={j} className="h-4 bg-gray-100 rounded animate-pulse flex-1" />
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}
