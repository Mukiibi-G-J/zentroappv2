'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { usePathname, useRouter, useSearchParams } from 'next/navigation'
import { Loader2, Plus, RefreshCw, ArrowLeft, MoreVertical, ExternalLink, Trash2, X, Printer, ChevronRight, ListChecks, Eye, Pencil, Check, Search, UserRound } from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import { useSession } from '@/context/SessionContext'
import { startImpersonation } from '@/services/auth.service'
import { resolvePostLoginPath } from '@/lib/postLoginRedirect'
import { writeStoredSession } from '@/lib/session'
import { usePage, usePages } from '@/hooks/usePage'
import {
  usePageDataInfinite,
  useDeleteRecord,
  useCreateRecord,
  useUpdateField,
  pendingRowHasRequiredFields,
  pendingRowHasAnyData,
} from '@/hooks/usePageData'
import { useDrillDownFilters } from '@/hooks/useDrillDownFilters'
import DrillDownField from '@/components/dynamic/DrillDownField'
import DynamicField from '@/components/dynamic/DynamicField'
import SearchableRelationSelect from '@/components/dynamic/SearchableRelationSelect'
import RelationLookupModal from '@/components/dynamic/RelationLookupModal'
import ListPageRibbon from '@/components/dynamic/ListPageRibbon'
import { buildLookupDrillDownFilters } from '@/lib/relationLookupFilters'
import type { RelationMenuFooter } from '@/lib/relationMenuFooter'
import ErrorBanner from '@/components/ui/ErrorBanner'
import { buildCardActionUrl } from '@/lib/cardAction'
import { getRibbonActions, getRowMenuActions, supportsEditListToggle, isInlineEditingActive, canEditFieldInGrid, showDrillDownInList } from '@/lib/cardPage'
import { drillDownDefaultsForNewRow } from '@/lib/listInlineCreate'
import { listFieldValuesEqual, normalizeListFieldSaveValue } from '@/lib/listFieldValue'
import { extractErrorMessage } from '@/services/pagedata.service'
import { formatDisplayDateTime } from '@/lib/dateFormat'
import { todayIsoDate, yesterdayIsoDate } from '@/lib/listPageFilters'
import ListScopeFilterBar from '@/components/dynamic/ListScopeFilterBar'
import { findWorksheetLinesControl } from '@/lib/worksheetControls'
import { formatRelationDisplay, resolveRelationSelectValue } from '@/lib/relationDisplay'
import { getRecordFieldValue } from '@/lib/recordFieldValue'
import {
  buildRelationRecordValues,
  collectContextValuesFromRecords,
  contextRelationCacheKey,
  getDependentRelationFields,
  hasContextRelation,
} from '@/lib/contextRelations'
import { mapTableRelationValue, type RelationOption } from '@/hooks/useRelationOptions'
import { pageService } from '@/services/page.service'
import FinancialReportDateFilters from '@/components/dynamic/FinancialReportDateFilters'
import FinancialReportFormatModal from '@/components/dynamic/FinancialReportFormatModal'
import { extractApiErrorMessage } from '@/lib/apiError'
import {
  defaultFinancialReportDateRange,
  downloadBase64File,
  FINANCIAL_REPORT_END_DATE_FIELD,
  FINANCIAL_REPORT_PRINT_ACTION,
  FINANCIAL_REPORT_RECALCULATE_ACTION,
  FINANCIAL_REPORT_START_DATE_FIELD,
  isFinancialReportDateAction,
  isFinancialReportDownloadContent,
  isFinancialReportPrintContent,
  openFinancialReportPrintHtml,
  reportDatesFromRecord,
} from '@/lib/financialReport'
import { isDownloadActionResponse, isPreviewActionResponse } from '@/lib/pageActionResponse'
import { useListCues } from '@/hooks/useListCues'
import ListCueStrip from '@/components/dynamic/ListCueStrip'
import ListColumnHeaderMenu from '@/components/dynamic/ListColumnHeaderMenu'
import { useListColumnState } from '@/hooks/useListColumnState'
import { formatColumnFilterLabel, serializeFilterValue } from '@/lib/listColumnFilters'
import type { PageAction, PageControlField } from '@/types/page'
import type { DataRecord } from '@/types/pagedata'
import { colWidthPx, worksheetFrozenFieldProps } from '@/lib/worksheetColumns'
import { coaIndentStyle, coaRowTextClass, isChartOfAccountsList, isCoaNameField } from '@/lib/chartOfAccountsList'
import {
  isItemCategoryList,
  itemCategoryCodeClass,
  itemCategoryIndentStyle,
} from '@/lib/itemCategoryList'
import { getCardRecordPath, buildListReturnPath, getPageRouteId, listDashboardPath } from '@/lib/pageRoutes'
import { canPrintSalesInvoiceList } from '@/lib/salesInvoicePrint'
import { SalesInvoiceReceiptDialog } from '@/components/sales/SalesInvoiceReceiptDialog'
import PostedSalesHistoryPanel from '@/components/sales/PostedSalesHistoryPanel'
import ImportItemsDialog from '@/components/items/ImportItemsDialog'
import ExportItemsModal from '@/components/items/ExportItemsModal'
import JournalPreviewDialog, { type JournalPreviewContent } from '@/components/dynamic/JournalPreviewDialog'
import { ConfirmDialog } from '@/components/ui/ConfirmDialog'
import { POSTED_SALES_INVOICE_LIST_PAGE, salesInvoiceSystemIdFromRecord } from '@/lib/postedSalesHistory'
import {
  ITEM_LIST_DOWNLOAD_TEMPLATE,
  ITEM_LIST_EXPORT,
  ITEM_LIST_IMPORT,
  ITEM_LIST_PAGE,
  isItemListHashAction,
} from '@/lib/itemListActions'
import {
  POST_ITEM_JOURNAL,
  PREVIEW_ITEM_JOURNAL,
  isItemJournalListPage,
  isItemJournalServerAction,
  isSelectMoreAction,
  mergeJournalPreviews,
  recordIsOpen,
} from '@/lib/itemJournalListActions'
import { isPageActionVisible } from '@/lib/pageActionVisibility'
import {
  downloadItemImportTemplate,
  pollItemExportDownload,
  startItemExport,
  type ItemExportFormat,
} from '@/services/items.service'

/** Extra width inside the frozen primary column for the ⋮ menu button */
const PRIMARY_MENU_PX = 36
/** BC-style row selector gutter (arrow on selected row) */
const SELECTOR_GUTTER_PX = 32

function formatValue(value: unknown, field: PageControlField): string {
  if (value === null || value === undefined || value === '') return '—'
  if (field.FieldType === 'Boolean') return value ? 'Yes' : 'No'
  if (field.FieldType === 'Code') return String(value).toUpperCase()
  if (field.FieldType === 'Date' && value) {
    try { return new Date(String(value)).toLocaleDateString() } catch { return String(value) }
  }
  if (field.FieldType === 'DateTime' && value) {
    return formatDisplayDateTime(String(value))
  }
  if (field.FieldType === 'Decimal')
    return Number(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  if (field.FieldType === 'Integer') return Number(value).toLocaleString()
  const text = String(value)
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(text)) {
    return formatDisplayDateTime(text)
  }
  return text
}

function ListSkeleton() {
  return (
    <div className="flex flex-1 min-h-0 flex-col gap-4">
      <div className="h-8 w-48 bg-gray-100 rounded animate-pulse shrink-0" />
      <div className="h-9 w-64 bg-gray-100 rounded animate-pulse shrink-0" />
      <div className="flex-1 min-h-0 rounded-xl border border-gray-200 bg-white overflow-hidden">
        {[...Array(6)].map((_, i) => (
          <div key={i} className="h-12 border-b border-gray-100 px-4 flex items-center gap-4">
            {[...Array(4)].map((_, j) => (
              <div key={j} className="h-4 bg-gray-100 rounded animate-pulse flex-1" />
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}

interface RowMenu {
  systemId: string
  x: number
  y: number
}

interface Props {
  pageId: number
}

export default function DynamicListPage({ pageId }: Props) {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const { session } = useSession()
  const { data: page, isLoading: pageLoading } = usePage(pageId)
  const listReturnPath = useMemo(
    () =>
      buildListReturnPath(
        page ?? { PageId: pageId },
        searchParams,
        pathname,
      ),
    [page, pageId, searchParams, pathname],
  )
  const [search, setSearch] = useState('')
  const [listSearchOpen, setListSearchOpen] = useState(false)
  const listSearchInputRef = useRef<HTMLInputElement>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [pendingRows, setPendingRows] = useState<DataRecord[]>([])
  const pendingRowsRef = useRef<DataRecord[]>([])
  const creatingPendingRef = useRef<Set<string>>(new Set())
  const [pendingDeleteIds, setPendingDeleteIds] = useState<string[] | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)
  const [printSystemId, setPrintSystemId] = useState<string | null>(null)
  const [listActionLoading, setListActionLoading] = useState(false)
  const [listActionMessage, setListActionMessage] = useState<string | null>(null)
  const [financialReportModalAction, setFinancialReportModalAction] = useState<PageAction | null>(null)
  const [importItemsOpen, setImportItemsOpen] = useState(false)
  const [exportItemsOpen, setExportItemsOpen] = useState(false)
  const [itemExportLoading, setItemExportLoading] = useState(false)
  const [itemExportProgress, setItemExportProgress] = useState('')
  const [multiSelectMode, setMultiSelectMode] = useState(false)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set())
  const [postingPreview, setPostingPreview] = useState<JournalPreviewContent | null>(null)
  const [pendingPostAction, setPendingPostAction] = useState<PageAction | null>(null)
  const defaultReportDates = defaultFinancialReportDateRange()
  const [reportStartDate, setReportStartDate] = useState(defaultReportDates.startDate)
  const [reportEndDate, setReportEndDate] = useState(defaultReportDates.endDate)
  const [rowMenu, setRowMenu] = useState<RowMenu | null>(null)
  const [pendingImpersonate, setPendingImpersonate] = useState<DataRecord | null>(null)
  const [impersonateLoading, setImpersonateLoading] = useState(false)
  const [lookupModal, setLookupModal] = useState<{
    field: PageControlField
    record: DataRecord
    autoNew: boolean
  } | null>(null)
  const rowMenuRef = useRef<HTMLDivElement>(null)
  const scrollContainerRef = useRef<HTMLDivElement>(null)
  const sentinelRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (search.trim()) setListSearchOpen(true)
  }, [search])

  useEffect(() => {
    if (listSearchOpen) listSearchInputRef.current?.focus()
  }, [listSearchOpen])

  // Leaving / switching list pages must exit multi-select.
  useEffect(() => {
    setMultiSelectMode(false)
    setSelectedIds(new Set())
    setRowMenu(null)
  }, [pageId])

  const { data: allPages = [] } = usePages()
  const showPrintAction = canPrintSalesInvoiceList(page)
  const isPostedSalesHistory = page?.Name === POSTED_SALES_INVOICE_LIST_PAGE
  const { data: cardPage } = usePage(page?.CardPageId ?? undefined)
  const { data: listCues, isLoading: listCuesLoading } = useListCues(pageId)
  const { filters: drillDownFilters, isDrillDown, contextValue, contextLabel, filterLabel, picker, returnUrl } =
    useDrillDownFilters(page)

  const listControl = useMemo(
    () =>
      findWorksheetLinesControl(page)
      ?? page?.PageControls.find((c) => c.ControlType === 'Repeater')
      ?? page?.PageControls.find((c) => c.ControlType === 'Repeater' || c.ControlType === 'Group'),
    [page],
  )
  const listControlId = listControl?.PageControlId
  const updateField = useUpdateField(pageId, listControl?.PageControlId)
  const visibleFields = useMemo(
    () => listControl?.Fields.filter((f) => f.Visible) ?? [],
    [listControl?.Fields],
  )
  const displayFields = isDrillDown && page?.ContextFilterField
    ? visibleFields.filter((f) => f.Name !== page.ContextFilterField)
    : visibleFields

  const {
    columnFilters,
    sort: listSort,
    setSort,
    setColumnFilter,
    clearColumnFilter,
    clearAllColumnState,
    getFieldFilterValue,
    hasColumnState,
  } = useListColumnState(displayFields)

  const listApiFilters = useMemo(
    () => ({ ...drillDownFilters, ...columnFilters }),
    [drillDownFilters, columnFilters],
  )

  const [editListMode, setEditListMode] = useState(false)
  const [focusPendingId, setFocusPendingId] = useState<string | null>(null)
  const editListToggle = supportsEditListToggle(page, visibleFields)
  const inlineEditingActive = isInlineEditingActive(page, editListMode, visibleFields)

  const ribbonActions = useMemo(() => {
    const actions = getRibbonActions(page)
    if (page?.Name === POSTED_SALES_INVOICE_LIST_PAGE) {
      return actions.filter((a) => (a.RibbonTab || 'Home') !== 'Scope')
    }
    return actions
  }, [page])
  const showListRibbonBase = editListToggle || inlineEditingActive || ribbonActions.length > 0
  const ribbonHasNew = ribbonActions.some((a) => (a.ActionRelativeUrl || '').trim() === '#new')

  // First column: frozen, highlighted, with inline ⋮ menu (BC list pattern)
  const firstField = displayFields[0] ?? null
  const firstColWidth = firstField ? colWidthPx(firstField) : 192
  const stickyPrimaryWidth = firstColWidth + PRIMARY_MENU_PX
  const showRowSelector = inlineEditingActive || multiSelectMode
  const frozenColumnOffset = showRowSelector ? SELECTOR_GUTTER_PX + stickyPrimaryWidth : stickyPrimaryWidth
  const restFields = displayFields.slice(1)

  const {
    data,
    isLoading: dataLoading,
    isError: dataError,
    error: dataFetchError,
    isFetchingNextPage,
    hasNextPage,
    fetchNextPage,
    refetch,
  } = usePageDataInfinite(pageId, listControl?.PageControlId, search || undefined, listApiFilters, {
    sort: listSort,
  })

  const rawRecords = data?.pages.flatMap((p) => p) ?? []
  const serverRecords: DataRecord[] = useMemo(
    () => [
      ...new Map(
        rawRecords
          .filter((r): r is DataRecord => r != null && r.SystemId != null && r.SystemId !== '')
          .map((r) => [String(r.SystemId), r]),
      ).values(),
    ],
    [rawRecords],
  )
  const records: DataRecord[] = useMemo(() => {
    const merged = [...pendingRows, ...serverRecords]
    const seen = new Set<string>()
    return merged.filter((row) => {
      if (row?.SystemId == null || row.SystemId === '') return false
      const id = String(row.SystemId)
      if (seen.has(id)) return false
      seen.add(id)
      return true
    })
  }, [pendingRows, serverRecords])

  const selectedRecord = useMemo(
    () => records.find((r) => String(r.SystemId) === selectedId) ?? null,
    [records, selectedId],
  )

  const isUsersList = page?.Name === 'UsersList'
  const isDebugAdmin = session?.user?.username === 'debug_admin'
  const canImpersonateUsers = isUsersList && isDebugAdmin && !session?.impersonation?.active

  const handleConfirmImpersonate = useCallback(async () => {
    if (!pendingImpersonate) return
    const userId = Number(pendingImpersonate.id)
    if (!Number.isFinite(userId) || userId <= 0) {
      toast.error('Cannot determine user id for this row')
      setPendingImpersonate(null)
      return
    }
    setImpersonateLoading(true)
    try {
      const sessionData = await startImpersonation(userId)
      const access = localStorage.getItem('access_token') || ''
      writeStoredSession(sessionData)
      window.location.replace(resolvePostLoginPath(access))
    } catch (err) {
      toast.error(extractApiErrorMessage(err) || 'Failed to login as user')
      setImpersonateLoading(false)
      setPendingImpersonate(null)
    }
  }, [pendingImpersonate])

  const isItemJournalList = isItemJournalListPage(page)

  const displayRibbonActions = useMemo(() => {
    const withSelectCaption = ribbonActions.map((a) =>
      isSelectMoreAction(a)
        ? { ...a, Caption: multiSelectMode ? 'Select One' : 'Select More' }
        : a,
    )
    if (!isItemJournalList) return withSelectCaption
    return withSelectCaption.filter((a) => {
      if (isSelectMoreAction(a)) return true
      if (!isItemJournalServerAction(a)) return true
      if (multiSelectMode) {
        return [...selectedIds].some((id) => {
          const rec = records.find((r) => String(r.SystemId) === id)
          return recordIsOpen(rec)
        })
      }
      return isPageActionVisible(a, selectedRecord)
    })
  }, [
    isItemJournalList,
    ribbonActions,
    multiSelectMode,
    selectedIds,
    records,
    selectedRecord,
  ])

  const showListRibbon =
    (showListRibbonBase || displayRibbonActions.length > 0) && !isPostedSalesHistory

  const isFinancialReportList = page?.Name === 'FinancialReportList'
  const reportDatesSyncRef = useRef('')

  useEffect(() => {
    if (!isFinancialReportList || !selectedRecord?.SystemId) return
    const syncKey = String(selectedRecord.SystemId)
    if (reportDatesSyncRef.current === syncKey) return
    reportDatesSyncRef.current = syncKey
    const range = reportDatesFromRecord(selectedRecord)
    setReportStartDate(range.startDate)
    setReportEndDate(range.endDate)
  }, [isFinancialReportList, selectedRecord])

  const saveReportDateField = useCallback(
    async (fieldName: 'start_date' | 'end_date', value: string) => {
      if (!selectedRecord?.SystemId || !isFinancialReportList) return
      const field: PageControlField = {
        ...(fieldName === 'start_date'
          ? FINANCIAL_REPORT_START_DATE_FIELD
          : FINANCIAL_REPORT_END_DATE_FIELD),
        FieldId: 0,
        PageId: pageId,
        PageControlId: listControlId ?? 0,
        PageControlFieldId: fieldName === 'start_date' ? -9001 : -9002,
        Visible: false,
        Editable: true,
        PrimaryKey: false,
        Required: false,
        TabIndex: 0,
      }
      try {
        await updateField.mutateAsync({
          systemId: String(selectedRecord.SystemId),
          field,
          value,
        })
      } catch (err) {
        toast.error(extractErrorMessage(err))
      }
    },
    [isFinancialReportList, listControlId, pageId, selectedRecord?.SystemId, updateField],
  )

  const handleReportStartDateChange = useCallback(
    (value: string) => {
      setReportStartDate(value)
      reportDatesSyncRef.current = ''
      if (!selectedRecord) return
      const periodType = String(getRecordFieldValue(selectedRecord, 'period_type') || 'Month')
      if (periodType === 'Day') {
        setReportEndDate(value)
        void saveReportDateField('start_date', value)
        void saveReportDateField('end_date', value)
        return
      }
      void saveReportDateField('start_date', value)
    },
    [saveReportDateField, selectedRecord],
  )

  const handleReportEndDateChange = useCallback(
    (value: string) => {
      setReportEndDate(value)
      reportDatesSyncRef.current = ''
      if (!selectedRecord) return
      const periodType = String(getRecordFieldValue(selectedRecord, 'period_type') || 'Month')
      if (periodType === 'Day') {
        setReportStartDate(value)
        void saveReportDateField('start_date', value)
        void saveReportDateField('end_date', value)
        return
      }
      void saveReportDateField('end_date', value)
    },
    [saveReportDateField, selectedRecord],
  )

  const reportDatesValid = Boolean(
    reportStartDate && reportEndDate && reportStartDate <= reportEndDate,
  )

  const executeListServerAction = useCallback(
    async (action: PageAction, extraPayload: Record<string, unknown> = {}) => {
      if (!selectedRecord?.SystemId) {
        toast.error('Select a financial report first')
        return
      }
      if (isFinancialReportList && isFinancialReportDateAction(action.Name) && !reportDatesValid) {
        toast.error('Choose a valid date range first')
        return
      }
      setListActionLoading(true)
      setListActionMessage(`${action.Caption}…`)
      try {
        const result = await pageService.invokeAction(
          pageId,
          action.Name,
          String(selectedRecord.SystemId),
          isFinancialReportList && isFinancialReportDateAction(action.Name)
            ? {
                startDate: reportStartDate,
                endDate: reportEndDate,
                ...extraPayload,
              }
            : extraPayload,
        )
        if (isDownloadActionResponse(result)) {
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
        if (isPreviewActionResponse(result)) {
          const content = result.Content
          if (isFinancialReportPrintContent(content)) {
            openFinancialReportPrintHtml(content.Html)
            toast.success('Report generated')
            return
          }
          if (
            content
            && typeof content === 'object'
            && 'Entries' in content
          ) {
            setPostingPreview(content as JournalPreviewContent)
            return
          }
          toast.error('Preview returned no printable content')
          return
        }
        if (
          typeof result === 'object'
          && result !== null
          && 'Command' in result
          && (result.Command === 'REFRESH' || result.Command === 'MESSAGE')
        ) {
          const message =
            ('Message' in result && typeof result.Message === 'string' && result.Message)
            || `${action.Caption} completed`
          toast.success(message)
          setFinancialReportModalAction(null)
          return
        }
        if (typeof result === 'object' && result !== null && 'ok' in result && result.ok) {
          toast.success(`${action.Caption} completed`)
          refetch()
          setFinancialReportModalAction(null)
          setSelectedIds(new Set())
        }
      } catch (err) {
        toast.error(extractApiErrorMessage(err))
      } finally {
        setListActionLoading(false)
        setListActionMessage(null)
      }
    },
    [isFinancialReportList, pageId, refetch, reportDatesValid, reportEndDate, reportStartDate, selectedRecord?.SystemId],
  )

  const resolveOpenJournalIds = useCallback(() => {
    const targetIds = multiSelectMode && selectedIds.size > 0
      ? [...selectedIds]
      : selectedRecord?.SystemId
        ? [String(selectedRecord.SystemId)]
        : []
    return targetIds.filter((id) => {
      const rec = records.find((r) => String(r.SystemId) === id)
      return recordIsOpen(rec)
    })
  }, [multiSelectMode, records, selectedIds, selectedRecord?.SystemId])

  const previewItemJournals = useCallback(
    async (systemIds: string[]) => {
      setListActionLoading(true)
      setListActionMessage(
        systemIds.length > 1
          ? `Preparing preview for ${systemIds.length} journals…`
          : 'Preparing posting preview…',
      )
      const previews: JournalPreviewContent[] = []
      try {
        for (let i = 0; i < systemIds.length; i += 1) {
          const systemId = systemIds[i]
          setListActionMessage(
            systemIds.length > 1
              ? `Previewing journal ${i + 1} of ${systemIds.length}…`
              : 'Preparing posting preview…',
          )
          const result = await pageService.invokeAction(pageId, PREVIEW_ITEM_JOURNAL, systemId)
          if (isPreviewActionResponse(result)) {
            const content = result.Content
            if (content && typeof content === 'object' && 'Entries' in content) {
              previews.push(content as JournalPreviewContent)
              continue
            }
          }
          toast.error('Preview returned no entries')
          return
        }
        if (previews.length === 0) {
          toast.error('Preview returned no entries')
          return
        }
        setPostingPreview(mergeJournalPreviews(previews))
      } catch (err) {
        toast.error(extractApiErrorMessage(err))
      } finally {
        setListActionLoading(false)
        setListActionMessage(null)
      }
    },
    [pageId],
  )

  const postItemJournals = useCallback(
    async (action: PageAction, systemIds: string[]) => {
      setListActionLoading(true)
      setListActionMessage(
        systemIds.length > 1
          ? `Posting ${systemIds.length} journals…`
          : 'Posting journal…',
      )
      let ok = 0
      let fail = 0
      const postedIds: string[] = []
      try {
        for (let i = 0; i < systemIds.length; i += 1) {
          const systemId = systemIds[i]
          setListActionMessage(
            systemIds.length > 1
              ? `Posting journal ${i + 1} of ${systemIds.length}…`
              : 'Posting journal…',
          )
          try {
            const result = await pageService.invokeAction(pageId, action.Name, systemId)
            if (typeof result === 'object' && result !== null && 'ok' in result && result.ok) {
              ok += 1
              postedIds.push(systemId)
            } else {
              fail += 1
            }
          } catch (err) {
            fail += 1
            if (systemIds.length === 1) {
              toast.error(extractApiErrorMessage(err))
            }
          }
        }
        if (postedIds.length > 0) {
          setSelectedIds((prev) => {
            const next = new Set(prev)
            for (const id of postedIds) next.delete(id)
            return next
          })
          void refetch()
        }
        if (ok > 0 && fail === 0) {
          toast.success(ok === 1 ? `${action.Caption} completed` : `Posted ${ok} journals`)
        } else if (ok > 0 && fail > 0) {
          toast.warning(`Posted ${ok} journal(s); ${fail} failed`)
        } else if (fail > 0 && systemIds.length > 1) {
          toast.error(`${fail} journal(s) failed to post`)
        }
      } finally {
        setListActionLoading(false)
        setListActionMessage(null)
      }
    },
    [pageId, refetch],
  )

  const handleListServerAction = useCallback(
    (action: PageAction) => {
      if (isItemJournalList && isItemJournalServerAction(action)) {
        const openIds = resolveOpenJournalIds()
        if (openIds.length === 0) {
          toast.error('Select an open journal first')
          return
        }
        if (action.Name === PREVIEW_ITEM_JOURNAL) {
          void previewItemJournals(openIds)
          return
        }
        if (action.Name === POST_ITEM_JOURNAL) {
          if (action.RequiresConfirmation) {
            setPendingPostAction(action)
            return
          }
          void postItemJournals(action, openIds)
          return
        }
      }

      if (!selectedRecord?.SystemId) {
        toast.error(isFinancialReportList ? 'Select a financial report first' : 'Select a row first')
        return
      }
      if (isFinancialReportList && action.Name === FINANCIAL_REPORT_PRINT_ACTION) {
        if (!reportDatesValid) {
          toast.error('Choose a valid date range first')
          return
        }
        setFinancialReportModalAction(action)
        return
      }
      if (isFinancialReportList && action.Name === FINANCIAL_REPORT_RECALCULATE_ACTION) {
        void executeListServerAction(action)
        return
      }
      void executeListServerAction(action)
    },
    [
      executeListServerAction,
      isFinancialReportList,
      isItemJournalList,
      postItemJournals,
      previewItemJournals,
      reportDatesValid,
      resolveOpenJournalIds,
      selectedRecord?.SystemId,
    ],
  )

  const isItemList = page?.Name === ITEM_LIST_PAGE

  const handleToggleSelectMore = useCallback(() => {
    setMultiSelectMode((prev) => {
      if (prev) {
        setSelectedIds(new Set())
        return false
      }
      if (selectedId) setSelectedIds(new Set([selectedId]))
      return true
    })
  }, [selectedId])

  const handleItemExport = useCallback(
    async (format: ItemExportFormat) => {
      setItemExportLoading(true)
      setItemExportProgress(`Preparing ${format.toUpperCase()} file…`)
      try {
        const filters: Record<string, unknown> = {}
        if (search.trim()) filters.search = search.trim()
        Object.entries(listApiFilters).forEach(([key, value]) => {
          if (value !== '' && value !== null && value !== undefined) {
            filters[key] = value
          }
        })
        const { task_id } = await startItemExport(format, filters)
        await pollItemExportDownload(task_id, format, setItemExportProgress)
        toast.success(`${format.toUpperCase()} export completed`)
        setExportItemsOpen(false)
      } catch (err) {
        toast.error(extractApiErrorMessage(err) || 'Export failed')
      } finally {
        setItemExportLoading(false)
        setItemExportProgress('')
      }
    },
    [listApiFilters, search],
  )

  const handleListHashAction = useCallback(
    (action: PageAction) => {
      if (isSelectMoreAction(action)) {
        handleToggleSelectMore()
        return
      }
      if (!isItemList || !isItemListHashAction(action)) return
      const target = (action.ActionRelativeUrl || '').trim()
      if (target === ITEM_LIST_DOWNLOAD_TEMPLATE) {
        void (async () => {
          try {
            // Opening-balance template includes Quantity, Unit Price (selling),
            // and Unit Cost (purchase). Filled quantities create OB journals.
            await downloadItemImportTemplate('opening_balance')
            toast.success('Excel template downloaded (includes qty & cost columns)')
          } catch (err) {
            toast.error(extractApiErrorMessage(err) || 'Failed to download template')
          }
        })()
        return
      }
      if (target === ITEM_LIST_IMPORT) {
        setImportItemsOpen(true)
        return
      }
      if (target === ITEM_LIST_EXPORT) {
        setExportItemsOpen(true)
      }
    },
    [handleToggleSelectMore, isItemList],
  )

  useEffect(() => {
    if (records.length === 0) return
    setSelectedId((prev) => {
      if (prev && records.some((r) => String(r.SystemId) === prev)) return prev
      const firstId = records[0]?.SystemId
      return firstId != null ? String(firstId) : prev
    })
  }, [records])

  useEffect(() => {
    const el = sentinelRef.current
    const root = scrollContainerRef.current
    if (!el || !root) return
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasNextPage && !isFetchingNextPage) fetchNextPage()
      },
      { root, threshold: 0.1 },
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [hasNextPage, isFetchingNextPage, fetchNextPage])

  // Close row menu on outside click (ignore clicks inside the portaled menu)
  useEffect(() => {
    if (!rowMenu) return
    const handler = (e: MouseEvent) => {
      if (rowMenuRef.current?.contains(e.target as Node)) return
      setRowMenu(null)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [rowMenu])

  const deleteRecord = useDeleteRecord(pageId, listControl?.PageControlId ?? 0)
  const createRecord = useCreateRecord(pageId, listControl?.PageControlId ?? 0, listControl?.Fields ?? [])
  const listControlEditable = listControl?.Editable !== false

  const contextRelationFields = useMemo(
    () => visibleFields.filter((f) => hasContextRelation(f)),
    [visibleFields],
  )
  const relationFieldKey = useMemo(
    () =>
      visibleFields
        .filter((f) => f.Visible && f.HasTableRelation && !hasContextRelation(f))
        .map((f) => f.PageControlFieldId)
        .join(','),
    [visibleFields],
  )
  const [relationOptions, setRelationOptions] = useState<Record<number, RelationOption[]>>({})
  const [contextRelationOptions, setContextRelationOptions] = useState<Record<string, RelationOption[]>>({})
  const loadedContextOptions = useRef(new Set<string>())
  const loadedRelationKeyRef = useRef('')

  useEffect(() => {
    if (!pageId || !listControlId || !relationFieldKey) {
      loadedRelationKeyRef.current = ''
      setRelationOptions((prev) => (Object.keys(prev).length === 0 ? prev : {}))
      return
    }
    if (loadedRelationKeyRef.current === relationFieldKey) return
    loadedRelationKeyRef.current = relationFieldKey

    const relationFields = visibleFields.filter(
      (f) => f.Visible && f.HasTableRelation && !hasContextRelation(f),
    )
    let cancelled = false
    ;(async () => {
      const next: Record<number, RelationOption[]> = {}
      for (const field of relationFields) {
        try {
          const values = await pageService.fetchTableRelations(
            pageId,
            listControlId,
            field.PageControlFieldId,
          )
          if (cancelled) return
          next[field.PageControlFieldId] = values.map(mapTableRelationValue)
        } catch {
          if (cancelled) return
          next[field.PageControlFieldId] = []
        }
      }
      if (!cancelled) setRelationOptions(next)
    })()
    return () => {
      cancelled = true
    }
  }, [pageId, listControlId, relationFieldKey])

  const clearContextRelationCache = useCallback((field: PageControlField) => {
    const prefix = `${field.PageControlFieldId}:`
    for (const key of [...loadedContextOptions.current]) {
      if (key.startsWith(prefix)) loadedContextOptions.current.delete(key)
    }
    setContextRelationOptions((prev) => {
      const next = { ...prev }
      for (const key of Object.keys(next)) {
        if (key.startsWith(prefix)) delete next[key]
      }
      return next
    })
  }, [])

  const loadContextRelationOptions = useCallback(
    async (field: PageControlField, record: DataRecord | Record<string, unknown>, force = false) => {
      if (!listControlId) return
      const cacheKey = contextRelationCacheKey(field, record)
      if (!cacheKey) return
      if (!force && loadedContextOptions.current.has(cacheKey)) return
      try {
        const values = await pageService.fetchTableRelations(
          pageId,
          listControlId,
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
    },
    [listControlId, pageId],
  )

  useEffect(() => {
    for (const field of contextRelationFields) {
      for (const value of collectContextValuesFromRecords(field, records)) {
        void loadContextRelationOptions(field, { [field.RelationContextField!]: value })
      }
    }
  }, [records, contextRelationFields, loadContextRelationOptions])

  const getFieldOptions = useCallback(
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

  const getRelationMenuFooter = useCallback(
    (
      field: PageControlField,
      record: DataRecord,
      currentValue: unknown,
    ): RelationMenuFooter | undefined => {
      if (!field.RelationLookupFooter) return undefined

      const lookupPage =
        field.HasLookupPage && field.LookupPageId
          ? allPages.find((p) => p.PageId === field.LookupPageId)
          : undefined

      const drillFilters = lookupPage
        ? buildLookupDrillDownFilters(lookupPage, record, visibleFields, field)
        : {}
      const ctxKey = (lookupPage?.ContextFilterField || '').trim()
      const requiresParentContext = Boolean(ctxKey)
      const contextReady = !requiresParentContext || Boolean(drillFilters[ctxKey])
      const parentContextBlocked = requiresParentContext && !contextReady

      const openLookupModal = (autoNew: boolean) => {
        if (!lookupPage) return
        if (parentContextBlocked) {
          toast.error('Complete required fields before opening the full list.')
          return
        }
        setLookupModal({ field, record, autoNew })
      }

      const listReadOnly = page?.ModifyAllowed === false || listControl?.Editable === false

      return {
        onNew: lookupPage ? () => openLookupModal(true) : undefined,
        newDisabled: listReadOnly || parentContextBlocked,
        onSelectFromFullList: lookupPage ? () => openLookupModal(false) : undefined,
        fullListDisabled: listReadOnly || parentContextBlocked,
        onShowDetails: lookupPage ? () => openLookupModal(false) : undefined,
        showDetailsDisabled:
          currentValue === null || currentValue === undefined || currentValue === '',
      }
    },
    [allPages, visibleFields, page?.ModifyAllowed, listControl?.Editable],
  )

  const lookupModalPage = useMemo(
    () =>
      lookupModal?.field.HasLookupPage && lookupModal.field.LookupPageId
        ? allPages.find((p) => p.PageId === lookupModal.field.LookupPageId)
        : undefined,
    [lookupModal, allPages],
  )

  const lookupModalFilters = useMemo(
    () =>
      lookupModalPage && lookupModal?.record
        ? buildLookupDrillDownFilters(
            lookupModalPage,
            lookupModal.record,
            visibleFields,
            lookupModal.field,
          )
        : {},
    [lookupModalPage, lookupModal?.record, lookupModal?.field, visibleFields],
  )

  const renderInlineEditor = (record: DataRecord, field: PageControlField) => {
    if (record?.SystemId == null) return null
    const fieldValue = getRecordFieldValue(record, field.Name)
    if (field.HasTableRelation) {
      const options = getFieldOptions(field, record)
      return (
        <SearchableRelationSelect
          key={`${record.SystemId}-${field.Name}`}
          compact
          options={options}
          value={resolveRelationSelectValue(fieldValue, options)}
          placeholder={`Search ${field.Caption}…`}
          menuFooter={getRelationMenuFooter(field, record, fieldValue)}
          onMenuOpen={
            hasContextRelation(field)
              ? () => void loadContextRelationOptions(field, record, true)
              : undefined
          }
          onChange={(val) => {
            if (record?.SystemId == null) return
            syncPendingField(record, field, val)
            void handleFieldBlur(record, field, val)
          }}
        />
      )
    }
    return (
      <DynamicField
        field={field}
        singleLine
        compact
        listInlineEdit
        autoFocus={focusPendingId === String(record.SystemId)}
        value={fieldValue}
        onChange={(value) => {
          syncPendingField(record, field, value)
        }}
        onBlur={(value) => {
          if (focusPendingId === String(record.SystemId)) setFocusPendingId(null)
          void handleFieldBlur(record, field, value)
        }}
        onKeyDown={(e: React.KeyboardEvent<HTMLInputElement>) => {
          if (e.key === 'Enter') e.currentTarget.blur()
        }}
      />
    )
  }

  const renderReadOnlyValue = (record: DataRecord, field: PageControlField) => {
    const fieldValue = getRecordFieldValue(record, field.Name)
    const options = getFieldOptions(field, record)
    if (field.HasTableRelation && options.length > 0) {
      return formatRelationDisplay(fieldValue, field, options)
    }
    return formatValue(fieldValue, field)
  }

  const isPendingRow = (record: DataRecord | null | undefined) =>
    record?.SystemId != null
    && pendingRowsRef.current.some((r) => String(r.SystemId) === String(record.SystemId))

  const updatePendingRow = (systemId: string, patch: Partial<DataRecord>): DataRecord | null => {
    let updated: DataRecord | null = null
    setPendingRows((prev) => {
      const next = prev.map((r) => {
        if (String(r.SystemId) !== systemId) return r
        updated = { ...r, ...patch }
        return updated
      })
      pendingRowsRef.current = next
      return next
    })
    return updated
  }

  const tryCreatePending = async (record: DataRecord | null | undefined) => {
    if (!record?.SystemId) return
    const pendingId = String(record.SystemId)
    if (!pendingRowHasRequiredFields(record, visibleFields)) return
    if (creatingPendingRef.current.has(pendingId)) return

    const payload: Record<string, unknown> = {}
    for (const field of visibleFields) {
      if (!field.Visible) continue
      const val = getRecordFieldValue(record, field.Name)
      if (val !== undefined && val !== null && val !== '') {
        payload[field.Name] = normalizeListFieldSaveValue(field, val)
      }
    }
    for (const [key, value] of Object.entries(drillDownFilters)) {
      if (value !== undefined && value !== null && value !== '') {
        payload[key] = value
      }
    }

    creatingPendingRef.current.add(pendingId)
    try {
      const created = await createRecord.mutateAsync(payload)
      setPendingRows((prev) => {
        const next = prev.filter((r) => String(r.SystemId) !== pendingId)
        pendingRowsRef.current = next
        return next
      })
      if (created?.SystemId) setSelectedId(String(created.SystemId))
      if (created) {
        const label = getRecordFieldValue(created, 'name') ?? getRecordFieldValue(created, 'description')
        if (label) toast.success(`Saved ${String(label)}`)
      }
    } catch (err) {
      toast.error(extractErrorMessage(err))
    } finally {
      creatingPendingRef.current.delete(pendingId)
    }
  }

  const syncPendingField = (record: DataRecord, field: PageControlField, value: unknown): DataRecord => {
    if (!record?.SystemId || !isPendingRow(record)) return record
    const normalized = normalizeListFieldSaveValue(field, value)
    return updatePendingRow(String(record.SystemId), { [field.Name]: normalized }) ?? record
  }

  const flushPendingCreates = async () => {
    if (document.activeElement instanceof HTMLElement) {
      document.activeElement.blur()
      await new Promise((resolve) => setTimeout(resolve, 0))
    }
    for (const row of pendingRowsRef.current) {
      if (!pendingRowHasRequiredFields(row, visibleFields)) continue
      await tryCreatePending(row)
    }
  }

  const isFieldEditable = (field: PageControlField) =>
    canEditFieldInGrid(field, inlineEditingActive, listControlEditable, page)

  const handleToggleEditList = async () => {
    if (!editListMode) {
      setEditListMode(true)
      return
    }

    await flushPendingCreates()

    const remaining = pendingRowsRef.current
    const incompleteWithData = remaining.filter(
      (row) =>
        pendingRowHasAnyData(row, visibleFields)
        && !pendingRowHasRequiredFields(row, visibleFields),
    )
    if (incompleteWithData.length > 0) {
      toast.error('Enter a Name before leaving Edit List.')
      return
    }

    for (const row of remaining) {
      if (!pendingRowHasRequiredFields(row, visibleFields)) continue
      try {
        await tryCreatePending(row)
      } catch (err) {
        toast.error(extractErrorMessage(err))
        return
      }
    }

    setPendingRows([])
    pendingRowsRef.current = []
    setFocusPendingId(null)
    setEditListMode(false)
  }

  const recordValuesForPatch = useCallback(
    (record: DataRecord, patch?: Record<string, unknown>) => {
      const merged = patch ? { ...record, ...patch } : record
      const out: Record<string, unknown> = {}
      for (const f of visibleFields) {
        const v = getRecordFieldValue(merged as DataRecord, f.Name)
        if (v !== undefined && v !== null && v !== '') out[f.Name] = v
      }
      return out
    },
    [visibleFields],
  )

  const handleFieldBlur = async (record: DataRecord, field: PageControlField, value: unknown) => {
    if (record?.SystemId == null) return
    const normalized = normalizeListFieldSaveValue(field, value)

    try {
      if (isPendingRow(record)) {
        const updated: DataRecord = { ...record, [field.Name]: normalized }
        updatePendingRow(String(record.SystemId), { [field.Name]: normalized })
        const dependentFields = getDependentRelationFields(visibleFields, field.Name)
        for (const dep of dependentFields) {
          clearContextRelationCache(dep)
          void loadContextRelationOptions(dep, updated, true)
        }
        await tryCreatePending(updated)
        return
      }
      if (listFieldValuesEqual(normalized, getRecordFieldValue(record, field.Name), field)) return
      const recordValues = recordValuesForPatch(record, { [field.Name]: normalized })
      const dependentFields = getDependentRelationFields(visibleFields, field.Name)
      if (dependentFields.length > 0) {
        await updateField.mutateAsync({
          systemId: record.SystemId,
          field,
          value: normalized,
          recordValues,
        })
        for (const dep of dependentFields) {
          if (getRecordFieldValue(record, dep.Name)) {
            await updateField.mutateAsync({
              systemId: record.SystemId,
              field: dep,
              value: '',
              recordValues,
            })
          }
          clearContextRelationCache(dep)
          void loadContextRelationOptions(
            dep,
            { ...record, [field.Name]: normalized },
            true,
          )
        }
        return
      }
      await updateField.mutateAsync({
        systemId: record.SystemId,
        field,
        value: normalized,
        recordValues,
      })
    } catch (err) {
      toast.error(extractErrorMessage(err))
    }
  }

  const resolveCardPageType = () =>
    cardPage?.PageType ?? allPages.find((p) => p.PageId === page?.CardPageId)?.PageType

  const isDocumentCardList = resolveCardPageType() === 'Document'

  const openCardFromList = (systemId: string) => {
    if (!page?.CardPageId) return
    router.push(
      getCardRecordPath(page.CardPageId, systemId, resolveCardPageType(), {
        fromList: String(getPageRouteId(page)),
        return: listReturnPath,
      }),
    )
  }

  const handleAddNew = () => {
    if (!page || !page.InsertAllowed) return

    // Document lists (Purchase/Sales invoices, etc.) always open the document page on New.
    if (isDocumentCardList && page.CardPageId) {
      openCardFromList('new')
      return
    }

    // Edit List mode: add a row inline. View mode with a linked card opens the card.
    if (inlineEditingActive) {
      const id = crypto.randomUUID()
      const defaults: DataRecord = {
        SystemId: id,
        ...(page.SourceTable === 'ItemUnitOfMeasure' ? { quantity_per_unit: 1 } : {}),
        ...drillDownDefaultsForNewRow(visibleFields, drillDownFilters),
      }
      setPendingRows((prev) => {
        const next = [defaults, ...prev]
        pendingRowsRef.current = next
        return next
      })
      setSelectedId(id)
      setFocusPendingId(id)
      return
    }

    if (page.CardPageId) {
      const query: Record<string, string> = {
        fromList: String(getPageRouteId(page)),
        return: listReturnPath,
      }
      // Only forward drill-down ctx when this list is context-scoped (not Item Categories).
      if (page.ContextFilterField) {
        const ctx = searchParams.get('ctx')
        const ctxLabel = searchParams.get('ctxLabel')
        if (ctx) query.ctx = ctx
        if (ctxLabel) query.ctxLabel = ctxLabel
      }
      router.push(
        getCardRecordPath(page.CardPageId, 'new', resolveCardPageType(), query),
      )
      return
    }

    const id = crypto.randomUUID()
    const defaults: DataRecord = {
      SystemId: id,
      ...(page.SourceTable === 'ItemUnitOfMeasure' ? { quantity_per_unit: 1 } : {}),
      ...drillDownDefaultsForNewRow(visibleFields, drillDownFilters),
    }
    setPendingRows((prev) => {
      const next = [defaults, ...prev]
      pendingRowsRef.current = next
      return next
    })
    setSelectedId(id)
    setFocusPendingId(id)
  }

  const handleRowClick = (record: DataRecord) => {
    const recordId = String(record.SystemId)
    if (multiSelectMode) {
      setSelectedIds((prev) => {
        const next = new Set(prev)
        if (next.has(recordId)) next.delete(recordId)
        else next.add(recordId)
        return next
      })
      setSelectedId(recordId)
      return
    }
    setSelectedId(recordId)
  }

  const handleOpenCardFromPrimary = (e: React.SyntheticEvent, record: DataRecord) => {
    e.stopPropagation()
    if (!page?.CardPageId) return
    if (inlineEditingActive && !isDocumentCardList) return
    setSelectedId(String(record.SystemId))
    openCardFromList(String(record.SystemId))
  }

  const handleRequestDelete = (systemId?: string) => {
    setDeleteError(null)
    setRowMenu(null)
    if (multiSelectMode && selectedIds.size > 0) {
      setPendingDeleteIds([...selectedIds])
      return
    }
    const id = systemId ?? selectedId
    if (!id) return
    setPendingDeleteIds([id])
  }

  const handleDeleteRow = async (systemId: string) => {
    const record = records.find((r) => String(r.SystemId) === systemId)
    if (!record) return
    if (isPendingRow(record)) {
      setPendingRows((prev) => {
        const next = prev.filter((r) => String(r.SystemId) !== systemId)
        pendingRowsRef.current = next
        return next
      })
      return
    }
    await deleteRecord.mutateAsync(systemId)
  }

  const handleOpenMenu = (e: React.MouseEvent, record: DataRecord) => {
    e.stopPropagation()
    setSelectedId(String(record.SystemId))
    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
    setRowMenu({ systemId: record.SystemId, x: rect.left, y: rect.bottom + 4 })
  }

  const handleDeleteConfirm = async () => {
    if (!pendingDeleteIds?.length || isDeleting) return
    setIsDeleting(true)
    setDeleteError(null)
    try {
      for (const id of pendingDeleteIds) {
        await handleDeleteRow(id)
      }
      setSelectedIds((prev) => {
        const next = new Set(prev)
        pendingDeleteIds.forEach((id) => next.delete(id))
        return next
      })
      if (selectedId && pendingDeleteIds.includes(selectedId)) {
        setSelectedId(null)
      }
      setPendingDeleteIds(null)
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : 'Failed to delete record')
    } finally {
      setIsDeleting(false)
    }
  }

  const visibleRecordIds = useMemo(
    () => records.map((r) => String(r.SystemId)),
    [records],
  )
  const allVisibleSelected =
    multiSelectMode
    && visibleRecordIds.length > 0
    && visibleRecordIds.every((id) => selectedIds.has(id))
  const someVisibleSelected =
    multiSelectMode && visibleRecordIds.some((id) => selectedIds.has(id))

  const toggleSelectAllVisible = () => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (allVisibleSelected) {
        visibleRecordIds.forEach((id) => next.delete(id))
      } else {
        visibleRecordIds.forEach((id) => next.add(id))
      }
      return next
    })
    if (!allVisibleSelected && visibleRecordIds[0]) {
      setSelectedId(visibleRecordIds[0])
    }
  }

  if (pageLoading) return <ListSkeleton />

  const coaList = isChartOfAccountsList(page?.SourceTable)
  const itemCategoryList = isItemCategoryList(page?.SourceTable)
  const rowMenuActions = getRowMenuActions(page)
  // Row ⋮ always offered — Select More is available on every list page.
  const hasRowMenuItems = true
  const scopeActions = (page?.PageActions ?? []).filter(
    (a) => a.Visible && a.RibbonTab === 'Scope' && (a.ActionRelativeUrl || '').trim(),
  )
  const hasAmountColumn = visibleFields.some((f) => f.Name === 'total_amount')
  const scopedTotal = hasAmountColumn
    ? records.reduce((sum, r) => sum + (Number(r.total_amount) || 0), 0)
    : null
  const showScopedTotal = scopedTotal !== null && isDrillDown
  const activeFilterLabel =
    filterLabel ||
    (drillDownFilters.posting_date === todayIsoDate() ? "Today's sales" : null) ||
    (drillDownFilters.posting_date === yesterdayIsoDate() ? "Yesterday's sales" : null) ||
    (drillDownFilters.posting_date_from && drillDownFilters.posting_date_to ? filterLabel || 'Date range' : null) ||
    (contextLabel && drillDownFilters.ledger_user_id ? `Sales by ${contextLabel}` : null)

  const handleFilterCellToValue = (record: DataRecord, field: PageControlField) => {
    const val = getRecordFieldValue(record, field.Name)
    if (val === null || val === undefined || val === '') return
    setColumnFilter(field, val)
  }

  const filterToValueLabel = (field: PageControlField, record: DataRecord | null) => {
    if (!record) return null
    const raw = getRecordFieldValue(record, field.Name)
    const serialized = serializeFilterValue(field, raw)
    if (!serialized) return null
    return formatColumnFilterLabel(field, serialized)
  }

  const renderColumnHeader = (
    field: PageControlField,
    extraClassName?: string,
    extraStyle?: React.CSSProperties,
  ) => (
    <ListColumnHeaderMenu
      field={field}
      sort={listSort}
      filterValue={getFieldFilterValue(field.Name)}
      filterToValue={filterToValueLabel(field, selectedRecord)}
      onSort={(order) => setSort(field.Name, order)}
      onFilterToValue={() => {
        if (selectedRecord) handleFilterCellToValue(selectedRecord, field)
      }}
      onClearFilter={() => clearColumnFilter(field.Name)}
      className={extraClassName}
      style={extraStyle}
    />
  )

  const handleClearFilters = () => {
    if (page) router.push(listDashboardPath(page))
    else router.push(`/dashboard?page=${pageId}`)
  }

  const handleClearColumnState = () => {
    clearAllColumnState()
  }

  const dataErrorMessage =
    dataFetchError instanceof Error ? dataFetchError.message : 'Failed to load records'

  const stickyPrimaryStyle = showRowSelector
    ? {
        left: SELECTOR_GUTTER_PX,
        width: stickyPrimaryWidth,
        minWidth: stickyPrimaryWidth,
        maxWidth: stickyPrimaryWidth,
      }
    : {
        left: 0,
        width: stickyPrimaryWidth,
        minWidth: stickyPrimaryWidth,
        maxWidth: stickyPrimaryWidth,
      }
  const stickyGutterStyle = {
    left: 0,
    width: SELECTOR_GUTTER_PX,
    minWidth: SELECTOR_GUTTER_PX,
    maxWidth: SELECTOR_GUTTER_PX,
  }
  const selectorGutterHeaderClass =
    'sticky left-0 z-30 border-r border-gray-200 bg-gray-50 p-0'
  const selectorGutterBodyClass = (selected: boolean) =>
    cn(
      'sticky left-0 z-20 border-r border-gray-100 p-0 transition-colors',
      selected ? 'bg-[#e8f4f4] group-hover:bg-[#e8f4f4]' : 'bg-white group-hover:bg-gray-50',
    )
  const firstColHeaderClass =
    'sticky z-30 bg-gray-50 px-4 py-3 text-left text-xs font-medium text-bodyText uppercase tracking-wide whitespace-nowrap shadow-[2px_0_4px_-1px_rgba(0,0,0,0.08)]'
  const firstColBodyClass = (selected: boolean) =>
    cn(
      'sticky z-20 py-2 pl-4 pr-1 transition-colors shadow-[2px_0_4px_-1px_rgba(0,0,0,0.08)]',
      selected ? 'bg-[#e8f4f4] group-hover:bg-[#e8f4f4]' : 'bg-white group-hover:bg-gray-50',
    )
  const selectedRowClass = (selected: boolean) =>
    selected ? 'bg-[#e8f4f4] group-hover:bg-[#e8f4f4]' : undefined

  const renderSelectCircle = ({
    selected,
    partial = false,
    title,
    onToggle,
  }: {
    selected: boolean
    partial?: boolean
    title: string
    onToggle: () => void
  }) => (
    <button
      type="button"
      title={title}
      aria-label={title}
      onClick={(e) => {
        e.stopPropagation()
        onToggle()
      }}
      className={cn(
        'flex h-5 w-5 items-center justify-center rounded-full border-2 transition',
        selected
          ? 'border-s1 bg-s1 text-white'
          : partial
            ? 'border-s1 bg-s1/25 text-s1'
            : 'border-gray-300 bg-white text-transparent hover:border-s1/60',
      )}
    >
      <Check size={12} strokeWidth={3} />
    </button>
  )

  return (
    <div className={cn('flex flex-1 min-h-0 flex-col', isPostedSalesHistory ? 'gap-2' : 'gap-4')}>
      {dataError && (
        <ErrorBanner message={dataErrorMessage} onRetry={() => refetch()} />
      )}

      {/* Header bar */}
      <div className="flex shrink-0 items-center justify-between">
        <div className="flex items-center gap-3 min-w-0">
          {returnUrl && (
            <button
              type="button"
              onClick={() => router.push(returnUrl)}
              className="p-2 rounded-lg hover:bg-gray-100 text-bodyText transition shrink-0"
              title="Back"
            >
              <ArrowLeft size={16} />
            </button>
          )}
          <div className="min-w-0">
            <h2 className="text-xl font-semibold text-mainTextColor">
              {page?.Caption ?? '—'}
            </h2>
            {isDrillDown && activeFilterLabel && !isPostedSalesHistory && (
              <p className="text-sm text-bodyText mt-0.5">
                <span className="font-medium">{activeFilterLabel}</span>
                {contextLabel && !filterLabel && contextValue && !drillDownFilters.ledger_user_id ? (
                  <>
                    {' — '}
                    <span className="font-mono text-s1">{contextValue}</span>
                  </>
                ) : null}
              </p>
            )}
            {picker === 'sales' && page?.Name === 'UsersList' && (
              <p className="text-sm text-bodyText mt-0.5">
                Click a user&apos;s <span className="font-medium">name</span> to view their posted sales.
              </p>
            )}
            {!isDrillDown && page?.ListFilterField && page?.ListFilterValue && (
              <p className="text-sm text-bodyText mt-0.5">
                Showing{' '}
                <span className="font-medium">{page.ListFilterField}</span>
                {' = '}
                <span className="font-mono text-s1">
                  {page.ListFilterValue.split(',').map((v) => v.trim()).filter(Boolean).join(', ')}
                </span>
              </p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {canImpersonateUsers && selectedRecord && String(selectedRecord.username ?? '') !== 'debug_admin' && (
            <button
              type="button"
              onClick={() => setPendingImpersonate(selectedRecord)}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm border border-amber-300 bg-amber-50 rounded-lg hover:bg-amber-100 text-amber-950 transition"
              title="View the system as this user"
            >
              <UserRound size={14} />
              Login as
            </button>
          )}
          {hasColumnState && (
            <button
              type="button"
              onClick={handleClearColumnState}
              className="flex items-center gap-1 px-3 py-1.5 text-sm border border-strokeColor rounded-lg hover:bg-gray-50 text-bodyText transition"
              title="Clear column filters and sort"
            >
              <X size={14} />
              Clear column filters
            </button>
          )}
          {isDrillDown && (
            <button
              type="button"
              onClick={handleClearFilters}
              className="flex items-center gap-1 px-3 py-1.5 text-sm border border-strokeColor rounded-lg hover:bg-gray-50 text-bodyText transition"
              title="Clear filters"
            >
              <X size={14} />
              Clear filters
            </button>
          )}
          <button
            onClick={() => refetch()}
            className="p-2 rounded-lg hover:bg-gray-100 text-bodyText transition"
            title="Refresh"
          >
            <RefreshCw size={15} />
          </button>
          {page?.InsertAllowed && !ribbonHasNew && !showListRibbon && (
            <button
              onClick={handleAddNew}
              disabled={createRecord.isPending}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-s1 text-white text-sm rounded-lg hover:opacity-90 disabled:opacity-60 transition"
            >
              <Plus size={15} /> New
            </button>
          )}
        </div>
      </div>

      {isFinancialReportList && selectedRecord ? (
        <section className="rounded-xl border border-gray-200 bg-white px-4 py-3">
          <div className="flex flex-wrap items-end gap-4">
            <div>
              <p className="text-sm font-semibold text-mainTextColor">Report dates</p>
              <p className="text-xs text-bodyText">
                Used for recalculate and export on{' '}
                {(selectedRecord.description as string | undefined) ?? (selectedRecord.name as string | undefined) ?? 'selected report'}
              </p>
            </div>
            <FinancialReportDateFilters
              compact
              startDate={reportStartDate}
              endDate={reportEndDate}
              onStartDateChange={handleReportStartDateChange}
              onEndDateChange={handleReportEndDateChange}
            />
          </div>
        </section>
      ) : null}

      {scopeActions.length > 0 && !isPostedSalesHistory ? (
        <ListScopeFilterBar page={page!} actions={scopeActions} allPages={allPages} />
      ) : (
        !isPostedSalesHistory && (
          <ListCueStrip
            groups={listCues?.CueGroups ?? []}
            isLoading={listCuesLoading && !listCues}
          />
        )
      )}

      {isPostedSalesHistory && page && (
        <PostedSalesHistoryPanel
          pageId={pageId}
          filters={drillDownFilters}
          returnUrl={returnUrl}
          search={search}
          onSearchChange={setSearch}
        />
      )}

      {/* Search (hidden when ribbon or sales history panel provides search) */}
      {!showListRibbon && !isPostedSalesHistory && (
        listSearchOpen || search.trim() ? (
          <div className="relative min-w-[200px] max-w-sm w-64">
            <Search
              size={15}
              className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-s1"
            />
            <input
              ref={listSearchInputRef}
              type="search"
              className="h-8 w-full rounded border border-gray-200 bg-white py-1 pl-8 pr-2 text-sm text-mainTextColor focus:border-s1 focus:outline-none focus:ring-1 focus:ring-s1/30"
              placeholder="Search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onBlur={() => {
                if (!search.trim()) setListSearchOpen(false)
              }}
            />
          </div>
        ) : (
          <button
            type="button"
            onClick={() => setListSearchOpen(true)}
            className="inline-flex items-center gap-2 rounded px-2 py-1.5 text-sm text-bodyText transition hover:bg-[#eef6f7] hover:text-s1"
          >
            <Search size={16} className="text-s1" strokeWidth={1.75} />
            <span>Search</span>
          </button>
        )
      )}

      {/* Table */}
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-gray-200 bg-white">
        {showListRibbon && page && (
          <ListPageRibbon
            page={page}
            actions={displayRibbonActions}
            selectedRecord={selectedRecord}
            sourceFields={visibleFields}
            listPageId={pageId}
            search={search}
            onSearchChange={setSearch}
            onNew={page.InsertAllowed ? handleAddNew : undefined}
            onDelete={
              page.DeleteAllowed
              && (multiSelectMode ? selectedIds.size > 0 : Boolean(selectedId))
                ? () => handleRequestDelete()
                : undefined
            }
            onServerAction={handleListServerAction}
            onHashAction={handleListHashAction}
            insertAllowed={page.InsertAllowed}
            deleteAllowed={
              page.DeleteAllowed
              && (multiSelectMode ? selectedIds.size > 0 : Boolean(selectedId))
            }
            disabled={createRecord.isPending || isDeleting || listActionLoading}
            showEditList={editListToggle}
            editListMode={editListMode}
            onToggleEditList={handleToggleEditList}
          />
        )}
        <div ref={scrollContainerRef} className="min-h-0 flex-1 overflow-auto">
          <table className="min-w-max w-full text-sm">

            {/* ── Header ─────────────────────────────────────────────── */}
            <thead className="sticky top-0 z-30">
              <tr className="bg-gray-50 border-b border-gray-200">
                {showRowSelector && (
                  <th className={selectorGutterHeaderClass} style={stickyGutterStyle}>
                    {multiSelectMode ? (
                      <div className="flex h-full min-h-10 items-center justify-center">
                        {renderSelectCircle({
                          selected: allVisibleSelected,
                          partial: someVisibleSelected && !allVisibleSelected,
                          title: allVisibleSelected ? 'Clear selection' : 'Select all',
                          onToggle: toggleSelectAllVisible,
                        })}
                      </div>
                    ) : null}
                  </th>
                )}
                {/* Primary col — frozen, highlight + ⋮ menu inside */}
                {firstField && (
                  <th className={firstColHeaderClass} style={stickyPrimaryStyle}>
                    {renderColumnHeader(firstField)}
                  </th>
                )}
                {/* Remaining cols */}
                {restFields.map((f, i) => {
                  const frozen = worksheetFrozenFieldProps(restFields, i, 'header', {
                    selectorColPx: frozenColumnOffset,
                  })
                  return (
                    <th key={f.PageControlFieldId} className={frozen.className} style={frozen.style}>
                      {renderColumnHeader(f)}
                    </th>
                  )
                })}
              </tr>
            </thead>

            {/* ── Body ───────────────────────────────────────────────── */}
            <tbody className="divide-y divide-gray-100 [&_td]:overflow-visible">
              {dataLoading ? (
                [...Array(5)].map((_, i) => (
                  <tr key={i}>
                    {showRowSelector && (
                      <td className={selectorGutterBodyClass(false)} style={stickyGutterStyle} />
                    )}
                    {firstField && (
                      <td className={firstColBodyClass(false)} style={stickyPrimaryStyle}>
                        <div className="flex items-center gap-1">
                          <div className="h-4 flex-1 bg-gray-100 rounded animate-pulse" />
                          <div className="h-4 w-4 bg-gray-100 rounded animate-pulse shrink-0" />
                        </div>
                      </td>
                    )}
                    {restFields.map((f, i) => {
                      const frozen = worksheetFrozenFieldProps(restFields, i, 'skeleton', {
                        selectorColPx: frozenColumnOffset,
                      })
                      return (
                        <td key={f.PageControlFieldId} className={frozen.className} style={frozen.style}>
                          <div className="h-4 bg-gray-100 rounded animate-pulse" />
                        </td>
                      )
                    })}
                  </tr>
                ))
              ) : !dataError && records.length === 0 ? (
                <tr>
                  <td
                    colSpan={Math.max(displayFields.length, 1) + (showRowSelector ? 1 : 0)}
                    className="px-4 py-12 text-center text-bodyText text-sm"
                  >
                    No records found
                  </td>
                </tr>
              ) : (
                records.map((record) => {
                  const recordId = String(record.SystemId)
                  const isChecked = multiSelectMode && selectedIds.has(recordId)
                  const isSelected = multiSelectMode
                    ? isChecked
                    : selectedId === recordId
                  return (
                  <tr
                    key={record.SystemId}
                    className={cn(
                      'group transition',
                      (inlineEditingActive || showListRibbon || multiSelectMode) && 'cursor-pointer',
                      selectedRowClass(isSelected),
                    )}
                    onClick={() => handleRowClick(record)}
                  >
                    {showRowSelector && (
                      <td className={selectorGutterBodyClass(isSelected)} style={stickyGutterStyle}>
                        <div
                          className={cn(
                            'flex h-full min-h-10 items-center justify-center',
                            isSelected && !multiSelectMode && 'border-l-[3px] border-l-s1',
                          )}
                        >
                          {multiSelectMode ? (
                            renderSelectCircle({
                              selected: isChecked,
                              title: isChecked ? 'Deselect row' : 'Select row',
                              onToggle: () => {
                                setSelectedIds((prev) => {
                                  const next = new Set(prev)
                                  if (next.has(recordId)) next.delete(recordId)
                                  else next.add(recordId)
                                  return next
                                })
                                setSelectedId(recordId)
                              },
                            })
                          ) : isSelected ? (
                            <ChevronRight size={14} className="text-s1" strokeWidth={2.5} />
                          ) : null}
                        </div>
                      </td>
                    )}
                    {/* ── Primary col: frozen, highlighted, ⋮ inside ─── */}
                    {firstField && (
                      <td
                        className={showRowSelector ? firstColBodyClass(isSelected) : firstColBodyClass(false)}
                        style={stickyPrimaryStyle}
                        onClick={(e) => {
                          if (
                            isFieldEditable(firstField) ||
                            showDrillDownInList(firstField, inlineEditingActive)
                          ) e.stopPropagation()
                        }}
                        onContextMenu={(e) => {
                          e.preventDefault()
                          e.stopPropagation()
                          handleFilterCellToValue(record, firstField)
                        }}
                      >
                        <div className="relative flex min-w-0 items-center">
                          <div
                            className={cn(
                              'min-w-0 flex-1',
                              isFieldEditable(firstField) ? 'pr-7' : 'truncate',
                            )}
                          >
                            {(() => {
                              if (isFieldEditable(firstField)) {
                                return renderInlineEditor(record, firstField)
                              }
                              if (showDrillDownInList(firstField, inlineEditingActive)) {
                                return (
                                  <DrillDownField
                                    field={firstField}
                                    value={record[firstField.Name]}
                                    record={record}
                                    sourcePage={page}
                                    sourceFields={visibleFields}
                                    returnPath={listReturnPath}
                                  />
                                )
                              }
                              return (
                                <span
                                  role={page?.CardPageId && !inlineEditingActive ? 'link' : undefined}
                                  tabIndex={page?.CardPageId && !inlineEditingActive ? 0 : undefined}
                                  onClick={(e) => {
                                    if (multiSelectMode) return
                                    if (page?.CardPageId && !inlineEditingActive) {
                                      handleOpenCardFromPrimary(e, record)
                                    }
                                  }}
                                  onKeyDown={(e) => {
                                    if (multiSelectMode) return
                                    if (
                                      page?.CardPageId
                                      && !inlineEditingActive
                                      && (e.key === 'Enter' || e.key === ' ')
                                    ) {
                                      e.preventDefault()
                                      handleOpenCardFromPrimary(e, record)
                                    }
                                  }}
                                  className={cn(
                                    'truncate',
                                    itemCategoryList && firstField.Name === 'code'
                                      ? itemCategoryCodeClass(record)
                                      : 'font-medium font-mono',
                                    !(itemCategoryList && firstField.Name === 'code') && (
                                      multiSelectMode
                                        ? 'text-mainTextColor'
                                        : page?.CardPageId && !inlineEditingActive
                                          ? 'cursor-pointer text-s1 underline decoration-s1/40 underline-offset-2'
                                          : 'text-mainTextColor'
                                    ),
                                  )}
                                  style={
                                    itemCategoryList && firstField.Name === 'code'
                                      ? itemCategoryIndentStyle(record)
                                      : undefined
                                  }
                                >
                                  {formatValue(record[firstField.Name], firstField)}
                                </span>
                              )
                            })()}
                          </div>
                          {hasRowMenuItems ? (
                          <button
                            type="button"
                            onClick={(e) => handleOpenMenu(e, record)}
                            className={cn(
                              'absolute right-0 top-1/2 flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded text-bodyText transition hover:bg-white/80 focus:outline-none focus:ring-2 focus:ring-s1/30',
                              rowMenuActions.length > 0
                                ? 'opacity-100'
                                : 'opacity-0 group-hover:opacity-100 focus:opacity-100',
                            )}
                            title="Actions"
                          >
                            <MoreVertical size={14} />
                          </button>
                          ) : null}
                        </div>
                      </td>
                    )}

                    {/* ── Rest of fields ─────────────────────────────── */}
                    {restFields.map((f, i) => {
                      const frozen = worksheetFrozenFieldProps(restFields, i, 'body', {
                        selectorColPx: frozenColumnOffset,
                        extraClass: 'text-mainTextColor',
                      })
                      return (
                        <td
                          key={f.PageControlFieldId}
                          className={frozen.className}
                          style={frozen.style}
                          onClick={(e) => {
                            if (
                              isFieldEditable(f) ||
                              showDrillDownInList(f, inlineEditingActive)
                            ) e.stopPropagation()
                          }}
                          onContextMenu={(e) => {
                            e.preventDefault()
                            e.stopPropagation()
                            handleFilterCellToValue(record, f)
                          }}
                        >
                          {(() => {
                            if (isFieldEditable(f)) {
                              return renderInlineEditor(record, f)
                            }
                            if (f.FieldType === 'Boolean' && f.Name === 'blocked') {
                              return (
                                <span className={cn(
                                  'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium',
                                  record[f.Name] ? 'bg-red-100 text-red-700' : 'bg-softBg2 text-s1',
                                )}>
                                  {record[f.Name] ? 'Blocked' : 'Active'}
                                </span>
                              )
                            }
                            if (showDrillDownInList(f, inlineEditingActive)) {
                              return (
                                <DrillDownField
                                  field={f}
                                  value={record[f.Name]}
                                  record={record}
                                  sourcePage={page}
                                  sourceFields={visibleFields}
                                  returnPath={listReturnPath}
                                />
                              )
                            }
                            return (
                              <span
                                className={cn(
                                  f.PrimaryKey && 'font-mono text-s1',
                                  coaList && isCoaNameField(f.Name) && coaRowTextClass(record),
                                )}
                                style={
                                  coaList && isCoaNameField(f.Name)
                                    ? coaIndentStyle(record)
                                    : undefined
                                }
                              >
                                {renderReadOnlyValue(record, f)}
                              </span>
                            )
                          })()}
                        </td>
                      )
                    })}
                  </tr>
                  )
                })
              )}
            </tbody>
          </table>

          <div ref={sentinelRef} className="h-4" />
          {isFetchingNextPage && (
            <div className="flex justify-center py-3">
              <Loader2 size={16} className="animate-spin text-bodyText" />
            </div>
          )}
        </div>

        <div className="shrink-0 border-t border-gray-100 bg-gray-50/80 px-4 py-2 text-xs text-bodyText flex items-center justify-between gap-4">
          <span>
            {records.length} record{records.length !== 1 ? 's' : ''}
            {hasNextPage && ' · scroll for more'}
          </span>
          {showScopedTotal && (
            <span className="font-medium text-mainTextColor tabular-nums">
              Total (loaded): UGX {scopedTotal.toLocaleString(undefined, {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}
              {hasNextPage ? ' · partial' : ''}
            </span>
          )}
        </div>
      </div>

      {/* ── Row context menu (portaled so sticky table cells don't block Print) ── */}
      {rowMenu &&
        createPortal(
          <div
            ref={rowMenuRef}
            className="fixed z-200 min-w-[140px] rounded-lg border border-gray-200 bg-white shadow-lg py-1 text-sm pointer-events-auto"
            style={{ top: rowMenu.y, left: rowMenu.x }}
            onMouseDown={(e) => e.stopPropagation()}
          >
            {isItemJournalList ? (
              <>
                {page?.CardPageId && (
                  <>
                    <button
                      type="button"
                      onMouseDown={(e) => {
                        e.preventDefault()
                        e.stopPropagation()
                        const rec = records.find((r) => r.SystemId === rowMenu.systemId)
                        if (rec) {
                          router.push(
                            getCardRecordPath(
                              page.CardPageId!,
                              String(rec.SystemId),
                              resolveCardPageType(),
                              { fromList: String(getPageRouteId(page)) },
                            ),
                          )
                        }
                        setRowMenu(null)
                      }}
                      className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-gray-50 text-mainTextColor"
                    >
                      <Eye size={13} className="text-s1" />
                      View
                    </button>
                    <button
                      type="button"
                      onMouseDown={(e) => {
                        e.preventDefault()
                        e.stopPropagation()
                        const rec = records.find((r) => r.SystemId === rowMenu.systemId)
                        if (rec) {
                          router.push(
                            getCardRecordPath(
                              page.CardPageId!,
                              String(rec.SystemId),
                              resolveCardPageType(),
                              { fromList: String(getPageRouteId(page)) },
                            ),
                          )
                        }
                        setRowMenu(null)
                      }}
                      className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-gray-50 text-mainTextColor"
                    >
                      <Pencil size={13} className="text-s1" />
                      Edit
                    </button>
                  </>
                )}
                {page?.DeleteAllowed && (
                  <button
                    type="button"
                    onMouseDown={(e) => {
                      e.preventDefault()
                      e.stopPropagation()
                      handleRequestDelete(rowMenu.systemId)
                    }}
                    className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-red-50 text-red-600"
                  >
                    <Trash2 size={13} />
                    Delete
                  </button>
                )}
                <button
                  type="button"
                  onMouseDown={(e) => {
                    e.preventDefault()
                    e.stopPropagation()
                    setSelectedId(rowMenu.systemId)
                    if (!multiSelectMode) {
                      setSelectedIds(new Set([rowMenu.systemId]))
                      setMultiSelectMode(true)
                    } else {
                      setMultiSelectMode(false)
                      setSelectedIds(new Set())
                    }
                    setRowMenu(null)
                  }}
                  className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-gray-50 text-mainTextColor"
                >
                  <ListChecks size={13} className="text-s1" />
                  {multiSelectMode ? 'Select One' : 'Select More'}
                </button>
              </>
            ) : (
              <>
                {canImpersonateUsers && (() => {
                  const rec = records.find((r) => r.SystemId === rowMenu.systemId)
                  if (!rec || String(rec.username ?? '') === 'debug_admin') return null
                  return (
                    <button
                      type="button"
                      onMouseDown={(e) => {
                        e.preventDefault()
                        e.stopPropagation()
                        setPendingImpersonate(rec)
                        setRowMenu(null)
                      }}
                      className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-amber-50 text-amber-950"
                    >
                      <UserRound size={13} />
                      Login as
                    </button>
                  )
                })()}
                {page?.CardPageId && (
                  <button
                    type="button"
                    onMouseDown={(e) => {
                      e.preventDefault()
                      e.stopPropagation()
                      const rec = records.find((r) => r.SystemId === rowMenu.systemId)
                      if (rec) {
                        router.push(
                          getCardRecordPath(page.CardPageId!, String(rec.SystemId), resolveCardPageType(), {
                            fromList: String(getPageRouteId(page)),
                          }),
                        )
                      }
                      setRowMenu(null)
                    }}
                    className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-gray-50 text-mainTextColor"
                  >
                    <ExternalLink size={13} className="text-bodyText" />
                    Open
                  </button>
                )}
                {showPrintAction && (
                  <button
                    type="button"
                    onMouseDown={(e) => {
                      e.preventDefault()
                      e.stopPropagation()
                      const rec = records.find((r) => r.SystemId === rowMenu.systemId)
                      const printId = rec && isPostedSalesHistory
                        ? salesInvoiceSystemIdFromRecord(rec as Record<string, unknown>)
                        : rowMenu.systemId
                      setPrintSystemId(printId)
                      setRowMenu(null)
                    }}
                    className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-gray-50 text-mainTextColor"
                  >
                    <Printer size={13} className="text-bodyText" />
                    Print
                  </button>
                )}
                {rowMenuActions.map((action) => (
                  <button
                    key={action.ActionId}
                    type="button"
                    onMouseDown={(e) => {
                      e.preventDefault()
                      e.stopPropagation()
                      const rec = records.find((r) => r.SystemId === rowMenu.systemId)
                      if (!rec) return
                      const href = buildCardActionUrl(
                        '/dashboard',
                        action.ActionRelativeUrl!,
                        allPages,
                        rec,
                        visibleFields,
                        listReturnPath,
                      )
                      if (href) router.push(href)
                      setRowMenu(null)
                    }}
                    className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-gray-50 text-mainTextColor"
                  >
                    <ExternalLink size={13} className="text-bodyText" />
                    {action.Caption}
                  </button>
                ))}
                {page?.DeleteAllowed && (
                  <button
                    type="button"
                    onMouseDown={(e) => {
                      e.preventDefault()
                      e.stopPropagation()
                      handleRequestDelete(rowMenu.systemId)
                    }}
                    className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-red-50 text-red-600"
                  >
                    <Trash2 size={13} />
                    Delete
                  </button>
                )}
                <button
                  type="button"
                  onMouseDown={(e) => {
                    e.preventDefault()
                    e.stopPropagation()
                    setSelectedId(rowMenu.systemId)
                    if (!multiSelectMode) {
                      setSelectedIds(new Set([rowMenu.systemId]))
                      setMultiSelectMode(true)
                    } else {
                      setMultiSelectMode(false)
                      setSelectedIds(new Set())
                    }
                    setRowMenu(null)
                  }}
                  className="flex w-full items-center gap-2 px-3 py-1.5 hover:bg-gray-50 text-mainTextColor"
                >
                  <ListChecks size={13} className="text-s1" />
                  {multiSelectMode ? 'Select One' : 'Select More'}
                </button>
              </>
            )}
          </div>,
          document.body,
        )}

      <SalesInvoiceReceiptDialog
        open={printSystemId != null}
        systemId={printSystemId}
        onClose={() => setPrintSystemId(null)}
      />

      <FinancialReportFormatModal
        open={financialReportModalAction?.Name === FINANCIAL_REPORT_PRINT_ACTION}
        title={financialReportModalAction?.Caption ?? 'Print'}
        reportLabel={
          (selectedRecord?.description as string | undefined)
          ?? (selectedRecord?.name as string | undefined)
        }
        loading={listActionLoading}
        onClose={() => setFinancialReportModalAction(null)}
        onExportPdf={() => {
          if (!financialReportModalAction) return
          void executeListServerAction(financialReportModalAction, { format: 'pdf' })
        }}
        onExportExcel={() => {
          if (!financialReportModalAction) return
          void executeListServerAction(financialReportModalAction, { format: 'excel' })
        }}
      />

      {isItemList ? (
        <>
          <ImportItemsDialog
            open={importItemsOpen}
            onClose={() => setImportItemsOpen(false)}
            onSuccess={() => {
              void refetch()
            }}
          />
          <ExportItemsModal
            open={exportItemsOpen}
            loading={itemExportLoading}
            progressMessage={itemExportProgress}
            onClose={() => {
              if (itemExportLoading) return
              setExportItemsOpen(false)
            }}
            onExportExcel={() => void handleItemExport('excel')}
            onExportPdf={() => void handleItemExport('pdf')}
          />
        </>
      ) : null}

      <JournalPreviewDialog
        open={postingPreview !== null}
        preview={postingPreview}
        onClose={() => setPostingPreview(null)}
      />

      {listActionLoading && financialReportModalAction == null ? (
        <div className="fixed inset-0 z-60 flex items-center justify-center bg-black/30">
          <div className="flex items-center gap-3 rounded-xl bg-white px-5 py-4 shadow-xl border border-gray-100">
            <Loader2 size={20} className="animate-spin text-s1 shrink-0" />
            <span className="text-sm font-medium text-mainTextColor">
              {listActionMessage || 'Working…'}
            </span>
          </div>
        </div>
      ) : null}

      <ConfirmDialog
        open={pendingPostAction != null}
        title={pendingPostAction?.Caption ?? 'Post'}
        message={(() => {
          if (pendingPostAction?.ConfirmationMessage && resolveOpenJournalIds().length <= 1) {
            return pendingPostAction.ConfirmationMessage
          }
          const openCount = resolveOpenJournalIds().length
          if (openCount > 1) {
            return `Post ${openCount} selected journals to the ledger?`
          }
          return pendingPostAction?.ConfirmationMessage || 'Post this journal to the ledger?'
        })()}
        confirmLabel="Post"
        onCancel={() => setPendingPostAction(null)}
        onConfirm={() => {
          const action = pendingPostAction
          setPendingPostAction(null)
          if (!action) return
          const openIds = resolveOpenJournalIds()
          if (openIds.length === 0) {
            toast.error('Select an open journal first')
            return
          }
          void postItemJournals(action, openIds)
        }}
      />

      <ConfirmDialog
        open={pendingImpersonate != null}
        title="Login as user"
        message={
          pendingImpersonate
            ? `View the system as ${String(pendingImpersonate.full_name || pendingImpersonate.username || 'this user')}? Your debug_admin session will be paused until you exit.`
            : ''
        }
        confirmLabel={impersonateLoading ? 'Starting…' : 'Login as'}
        onCancel={() => {
          if (impersonateLoading) return
          setPendingImpersonate(null)
        }}
        onConfirm={() => {
          void handleConfirmImpersonate()
        }}
      />

      {lookupModal && lookupModalPage ? (
        <RelationLookupModal
          open
          lookupPage={lookupModalPage}
          targetField={lookupModal.field}
          drillDownFilters={lookupModalFilters}
          autoNew={lookupModal.autoNew}
          onClose={() => setLookupModal(null)}
          onConfirm={(value) => {
            void handleFieldBlur(lookupModal.record, lookupModal.field, value)
            setLookupModal(null)
          }}
        />
      ) : null}

      {/* ── Delete confirm dialog ───────────────────────────────────────── */}
      {pendingDeleteIds && pendingDeleteIds.length > 0 && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="rounded-xl bg-white p-6 shadow-xl max-w-sm w-full mx-4">
            <h3 className="text-base font-semibold text-mainTextColor">
              {pendingDeleteIds.length > 1
                ? `Delete ${pendingDeleteIds.length} records?`
                : 'Delete record?'}
            </h3>
            <p className="mt-1 text-sm text-bodyText">This action cannot be undone.</p>
            {deleteError && (
              <p className="mt-2 text-sm text-red-600">{deleteError}</p>
            )}
            <div className="mt-5 flex justify-end gap-3">
              <button
                onClick={() => {
                  setPendingDeleteIds(null)
                  setDeleteError(null)
                }}
                disabled={isDeleting}
                className="rounded-lg border border-strokeColor px-4 py-2 text-sm font-medium text-bodyText hover:bg-softBg transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={() => void handleDeleteConfirm()}
                disabled={isDeleting}
                className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 transition-colors disabled:opacity-50"
              >
                {isDeleting
                  ? 'Deleting…'
                  : pendingDeleteIds.length > 1
                    ? `Delete ${pendingDeleteIds.length}`
                    : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
