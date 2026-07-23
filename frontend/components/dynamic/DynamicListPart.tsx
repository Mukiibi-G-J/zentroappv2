'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useRouter, useSearchParams, usePathname } from 'next/navigation'
import { Check, ChevronRight, Barcode } from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import { usePage, usePages } from '@/hooks/usePage'
import { useSalesSetup, normalizeSalesSetup } from '@/hooks/useSalesSetup'
import { filterDiscountFieldsBySetup } from '@/lib/salesDiscountFields'
import type { UseDocumentLinesReturn } from '@/hooks/useDocumentLines'
import { mapTableRelationValue, type RelationOption } from '@/hooks/useRelationOptions'
import { formatRelationDisplay, resolveRelationSelectValue } from '@/lib/relationDisplay'
import { useWorksheetGridKeyboard } from '@/hooks/useWorksheetGridKeyboard'
import {
  isLineFieldEditable,
  moveGridActiveCell,
  readActiveCellCommitValue,
  type GridActiveCell,
} from '@/lib/worksheetGridKeyboard'
import { listFieldValuesEqual, normalizeListFieldSaveValue } from '@/lib/listFieldValue'
import { pageService } from '@/services/page.service'
import {
  buildRelationRecordValues,
  collectContextValuesFromRecords,
  contextRelationCacheKey,
  getDependentRelationFields,
  hasContextRelation,
} from '@/lib/contextRelations'
import { getItemByNo, itemRequiresTracking, fetchAllItemLedgerEntries, pickAvailableLots } from '@/services/items.service'
import type { PurchaseTrackingContext } from '@/types/tracking'
import type { POSTrackingOption } from '@/types/pos'
import DynamicTrackingModal from './DynamicTrackingModal'
import { POSTrackingDialog } from '@/components/pos/POSTrackingDialog'
import DynamicField from './DynamicField'
import YesNoSelect from '@/components/ui/YesNoSelect'
import SearchableRelationSelect from './SearchableRelationSelect'
import WorksheetRowMenu from './WorksheetRowMenu'
import DocumentLinesRibbon from './DocumentLinesRibbon'
import DynamicWorksheetModal from './DynamicWorksheetModal'
import ErrorBanner from '@/components/ui/ErrorBanner'
import { ConfirmDialog } from '@/components/ui/ConfirmDialog'
import { worksheetFrozenFieldProps, colWidthPx } from '@/lib/worksheetColumns'
import { buildLineNavigateHref } from '@/lib/cardAction'
import { resolveRibbonIcon } from '@/lib/ribbonIcon'
import {
  applyEntriesPartyKind,
  ITEM_TRACKING_LINES_WORKSHEET_PAGE_NAME,
  POSTED_ITEM_TRACKING_LINES_PAGE_NAME,
  buildApplyEntriesContext,
  isItemTrackingLinesAction,
  isPostedItemTrackingLinesAction,
  purchaseLineItemNo,
  visibleItemTrackingLinePageActions,
  visibleLinePageActions,
  visibleNavigateLinePageActions,
} from '@/lib/documentLineActions'
import type { ApplyPaymentContext } from '@/lib/applyEntriesContext'
import { isControlFieldVisible } from '@/lib/pageActionVisibility'
import type { Page, PageAction, PageControl, PageControlField, PartSummary } from '@/types/page'
import type { DataRecord } from '@/types/pagedata'

function formatLineValue(value: unknown, field: PageControlField): string {
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

/** Width of the row-indicator (→ / checkmark) column in px */
const ROW_INDICATOR_PX = 28
/** Width of the three-dot menu column in px */
const MENU_COL_PX = 32
/** Total sticky prefix width passed as selectorColPx to worksheetFrozenFieldProps */
const LINES_PREFIX_PX = ROW_INDICATOR_PX + MENU_COL_PX

const stickyPrefix = (isSelected: boolean, extra = '') =>
  cn(
    'sticky shrink-0 overflow-visible py-2 bg-white',
    isSelected ? 'bg-[#eef5f5]' : 'group-hover:bg-gray-50',
    extra,
  )

export interface DynamicListPartProps {
  caption?: string
  partPage: PartSummary
  repeaterControl: PageControl
  lines: UseDocumentLinesReturn
  recordReady: boolean
  linesReadOnly: boolean
  saveFirstHint: string
  applyEntriesEnabled?: boolean
  applyVendorEntriesPage?: Page
  applyCustomerEntriesPage?: Page
  paymentHeader?: DataRecord
  documentHeader?: DataRecord
  onHeaderRefresh?: () => void
}

export function DynamicListPart({
    partPage,
  repeaterControl,
  lines,
  recordReady,
  linesReadOnly,
  saveFirstHint,
  applyEntriesEnabled = false,
  applyVendorEntriesPage,
  applyCustomerEntriesPage,
  paymentHeader,
  documentHeader,
  onHeaderRefresh,
}: DynamicListPartProps) {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const queryClient = useQueryClient()
  const { data: allPages = [] } = usePages()
  const { data: salesSetupRaw } = useSalesSetup()
  const salesSetup = useMemo(() => normalizeSalesSetup(salesSetupRaw), [salesSetupRaw])
  const trackingWorksheetPageFromCatalog = useMemo(
    () => allPages.find((p) => p.Name === ITEM_TRACKING_LINES_WORKSHEET_PAGE_NAME),
    [allPages],
  )
  const [trackingWorksheetPageOverride, setTrackingWorksheetPageOverride] = useState<Page | undefined>(
    undefined,
  )
  const trackingWorksheetPage = trackingWorksheetPageOverride ?? trackingWorksheetPageFromCatalog
  const returnUrl = useMemo(() => {
    const qs = searchParams.toString()
    return qs ? `${pathname}?${qs}` : pathname
  }, [pathname, searchParams])

  const [selectedRowId, setSelectedRowId] = useState<string | null>(null)
  const [selectedRowIds, setSelectedRowIds] = useState<Set<string>>(() => new Set())
  const [pendingBulkDelete, setPendingBulkDelete] = useState(false)
  const [applyModalOpen, setApplyModalOpen] = useState(false)
  const [applyModalContextOverride, setApplyModalContextOverride] =
    useState<ApplyPaymentContext | null>(null)
  const [applyWorksheetPage, setApplyWorksheetPage] = useState<Page | undefined>(undefined)
  const [editingCell, setEditingCell] = useState<GridActiveCell | null>(null)
  const [typeahead, setTypeahead] = useState<{ cell: GridActiveCell; char: string } | null>(null)
  const linesGridRef = useRef<HTMLDivElement>(null)
  const [multiSelectMode, setMultiSelectMode] = useState(false)
  const [relationOptions, setRelationOptions] = useState<Record<number, RelationOption[]>>({})
  const [contextRelationOptions, setContextRelationOptions] = useState<
    Record<string, RelationOption[]>
  >({})
  const [contextRelationLoading, setContextRelationLoading] = useState<Set<string>>(new Set())
  const loadedContextOptions = useRef(new Set<string>())
  const [trackingOpen, setTrackingOpen] = useState(false)
  const [trackingContext, setTrackingContext] = useState<PurchaseTrackingContext | null>(null)
  const [salesLotOpen, setSalesLotOpen] = useState(false)
  const [salesLotLineId, setSalesLotLineId] = useState<string | null>(null)
  const [salesLotItemName, setSalesLotItemName] = useState('')
  const [salesLotOptions, setSalesLotOptions] = useState<POSTrackingOption[]>([])
  const [salesLotLoading, setSalesLotLoading] = useState(false)
  const [salesLotSelected, setSalesLotSelected] = useState<string | undefined>(undefined)

  const { data: partPageFull } = usePage(partPage.PageId)
  const linePageActions = partPageFull?.PageActions ?? partPage.PageActions ?? []

  const isPostedPurchaseSubform = partPage.Name === 'PostedPurchaseInvoiceSubform'
  const isSalesInvoiceSubform = partPage.Name === 'SalesInvoiceSubform'

  const itemTrackingEnabled = useMemo(
    () => {
      if (isSalesInvoiceSubform) return true
      const hasTrackingAction = linePageActions.some(
        (a) => isItemTrackingLinesAction(a) || isPostedItemTrackingLinesAction(a),
      )
      return Boolean(documentHeader && hasTrackingAction)
    },
    [documentHeader, isSalesInvoiceSubform, linePageActions],
  )

  const visibleFieldKey = useMemo(
    () =>
      repeaterControl.Fields.filter((f) => f.Visible)
        .map((f) => f.PageControlFieldId)
        .join(','),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [
      repeaterControl.PageControlId,
      repeaterControl.Fields.map((f) => `${f.PageControlFieldId}:${f.Visible}`).join('|'),
    ],
  )

  const visibleFields = useMemo(
    () => filterDiscountFieldsBySetup(
      repeaterControl.Fields.filter((f) => f.Visible),
      salesSetup,
    ),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [visibleFieldKey, salesSetup.enable_line_discounts, salesSetup.enable_invoice_discounts],
  )

  const contextRelationFields = useMemo(
    () => visibleFields.filter((f) => hasContextRelation(f)),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [visibleFieldKey],
  )

  const relationFieldKey = useMemo(
    () =>
      visibleFields
        .filter((f) => f.HasTableRelation && !hasContextRelation(f))
        .map((f) => f.PageControlFieldId)
        .join(','),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [visibleFieldKey],
  )

  useEffect(() => {
    if (!partPage.PageId || !relationFieldKey) return
    const staticFields = repeaterControl.Fields.filter(
      (f) => f.Visible && f.HasTableRelation && !hasContextRelation(f),
    )
    let cancelled = false
    ;(async () => {
      const next: Record<number, RelationOption[]> = {}
      for (const field of staticFields) {
        try {
          const values = await pageService.fetchTableRelations(
            partPage.PageId,
            repeaterControl.PageControlId,
            field.PageControlFieldId,
          )
          if (cancelled) return
          next[field.PageControlFieldId] = values.map(mapTableRelationValue)
        } catch {
          if (cancelled) return
          next[field.PageControlFieldId] = []
        }
      }
      if (!cancelled) {
        setRelationOptions((prev) => {
          const keys = Object.keys(next)
          if (
            keys.length === Object.keys(prev).length &&
            keys.every((k) => {
              const id = Number(k)
              const a = prev[id]
              const b = next[id]
              return (
                a?.length === b?.length &&
                a?.every((opt, i) => opt.value === b[i]?.value)
              )
            })
          ) {
            return prev
          }
          return next
        })
      }
    })()
    return () => { cancelled = true }
  }, [partPage.PageId, repeaterControl.PageControlId, relationFieldKey])

  const loadContextRelationOptions = useCallback(
    async (field: PageControlField, record: DataRecord | Record<string, unknown>) => {
      const cacheKey = contextRelationCacheKey(field, record)
      if (!cacheKey) return
      if (loadedContextOptions.current.has(cacheKey)) return
      setContextRelationLoading((prev) => new Set(prev).add(cacheKey))
      try {
        const values = await pageService.fetchTableRelations(
          partPage.PageId,
          repeaterControl.PageControlId,
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
      } finally {
        setContextRelationLoading((prev) => {
          const next = new Set(prev)
          next.delete(cacheKey)
          return next
        })
      }
    },
    [partPage.PageId, repeaterControl.PageControlId],
  )

  const contextValuesKey = useMemo(() => {
    if (contextRelationFields.length === 0) return ''
    const parts: string[] = []
    for (const field of contextRelationFields) {
      parts.push(
        `${field.PageControlFieldId}:${[...collectContextValuesFromRecords(field, lines.lines)].sort().join(',')}`,
      )
    }
    return parts.join('|')
  }, [contextRelationFields, lines.lines])

  useEffect(() => {
    if (!contextValuesKey) return
    for (const field of contextRelationFields) {
      for (const value of collectContextValuesFromRecords(field, lines.lines)) {
        void loadContextRelationOptions(field, { [field.RelationContextField!]: value })
      }
    }
  }, [contextValuesKey, contextRelationFields, loadContextRelationOptions])

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

  const isFieldRelationLoading = useCallback(
    (field: PageControlField, record: DataRecord) => {
      if (!hasContextRelation(field)) return false
      const cacheKey = contextRelationCacheKey(field, record)
      return cacheKey ? contextRelationLoading.has(cacheKey) : false
    },
    [contextRelationLoading],
  )

  const lineFieldVisible = useCallback(
    (field: PageControlField, line: DataRecord) => isControlFieldVisible(field, line),
    [],
  )

  const lineFieldEditable = useCallback(
    (field: PageControlField, line?: DataRecord) =>
      (!line || lineFieldVisible(field, line))
      && isLineFieldEditable(
        field,
        partPage.ModifyAllowed && !linesReadOnly,
        repeaterControl.Editable !== false,
      ),
    [lineFieldVisible, linesReadOnly, partPage.ModifyAllowed, repeaterControl.Editable],
  )

  const focusLineCell = useCallback(
    (line: DataRecord, field: PageControlField, opts?: { typeahead?: string }) => {
      setSelectedRowId(line.SystemId)
      const cell: GridActiveCell = { systemId: line.SystemId, field: field.Name }
      setEditingCell(cell)
      setTypeahead(
        opts?.typeahead != null && opts.typeahead !== ''
          ? { cell, char: opts.typeahead }
          : null,
      )
      if (hasContextRelation(field)) void loadContextRelationOptions(field, line)
      if (!lineFieldEditable(field, line)) {
        requestAnimationFrame(() => {
          linesGridRef.current?.focus({ preventScroll: true })
        })
      }
    },
    [loadContextRelationOptions, lineFieldEditable],
  )

  const resolveTrackingWorksheetPage = useCallback(async (): Promise<Page | undefined> => {
    if (trackingWorksheetPageFromCatalog?.PageId) return trackingWorksheetPageFromCatalog
    const freshPages = await queryClient.fetchQuery({
      queryKey: ['pages'],
      queryFn: pageService.getPages,
      staleTime: 0,
    })
    return freshPages.find((p) => p.Name === ITEM_TRACKING_LINES_WORKSHEET_PAGE_NAME)
  }, [queryClient, trackingWorksheetPageFromCatalog])

  const resolvePostedTrackingWorksheetPage = useCallback(async (): Promise<Page | undefined> => {
    const freshPages = await queryClient.fetchQuery({
      queryKey: ['pages'],
      queryFn: pageService.getPages,
      staleTime: 0,
    })
    return freshPages.find((p) => p.Name === POSTED_ITEM_TRACKING_LINES_PAGE_NAME)
  }, [queryClient])

  const openTrackingForLine = useCallback(
    async (line: DataRecord, opts?: { auto?: boolean }) => {
      if (!itemTrackingEnabled) return
      if (!isSalesInvoiceSubform && !documentHeader) return
      const itemNo = purchaseLineItemNo(line)
      if (!itemNo) {
        if (!opts?.auto) toast.error('Select a line with an item first')
        return
      }
      const item = await getItemByNo(itemNo)
      if (!item?.tracking_code || !itemRequiresTracking(item.tracking_code)) {
        if (!opts?.auto) toast.error('This item does not use item tracking')
        return
      }

      const expectedQuantity = (Number(line.quantity) || 0)
        * (Number(line.item_unit_of_measure__quantity_per_unit ?? 1) || 1)

      // Sales invoice: serial (or lot+serial) → Item Tracking Lines worksheet.
      // Lot-only → POS-style lot picker into line.tracking_code.
      if (isSalesInvoiceSubform) {
        if (linesReadOnly) return
        if (!documentHeader) {
          if (!opts?.auto) toast.error('Save the invoice before entering tracking details')
          return
        }
        const requiresSerial = Boolean(item.tracking_code.require_serial_no)
        if (requiresSerial) {
          const worksheetPage = await resolveTrackingWorksheetPage()
          if (!worksheetPage?.PageId) {
            if (!opts?.auto) {
              toast.error('Run seed_pages to configure Item Tracking Lines worksheet')
            }
            return
          }
          const lineId = Number(line.id)
          const invoiceId = Number(documentHeader.id)
          if (!lineId || !invoiceId) {
            if (!opts?.auto) {
              toast.error('Save the line with an item before entering tracking details')
            }
            return
          }
          setTrackingWorksheetPageOverride(worksheetPage)
          setSelectedRowId(line.SystemId)
          setTrackingContext({
            mode: 'open',
            salesInvoiceId: invoiceId,
            salesInvoiceLineId: lineId,
            itemNo: item.no,
            itemName: item.item_name,
            trackingCode: item.tracking_code,
            expectedQuantity,
          })
          setTrackingOpen(true)
          return
        }

        setSelectedRowId(line.SystemId)
        setSalesLotLineId(line.SystemId)
        setSalesLotItemName(item.item_name)
        setSalesLotSelected(
          String(line.tracking_code ?? '').trim() || undefined,
        )
        setSalesLotOptions([])
        setSalesLotLoading(true)
        setSalesLotOpen(true)
        try {
          const entries = await fetchAllItemLedgerEntries(item.no)
          setSalesLotOptions(pickAvailableLots(entries))
        } catch {
          toast.error('Failed to load available lots')
          setSalesLotOptions([])
        } finally {
          setSalesLotLoading(false)
        }
        return
      }

      if (!documentHeader) return

      if (isPostedPurchaseSubform) {
        const worksheetPage = await resolvePostedTrackingWorksheetPage()
        if (!worksheetPage?.PageId) {
          if (!opts?.auto) {
            toast.error('Run seed_pages to configure Posted Item Tracking Lines (BC 6511)')
          }
          return
        }
        const vendorInvoiceNo = String(documentHeader.vendor_invoice_no ?? '').trim()
        if (!vendorInvoiceNo) {
          if (!opts?.auto) toast.error('Posted invoice is missing vendor invoice number')
          return
        }
        setTrackingWorksheetPageOverride(worksheetPage)
        setSelectedRowId(line.SystemId)
        setTrackingContext({
          mode: 'posted',
          vendorInvoiceNo,
          itemNo: item.no,
          itemName: item.item_name,
          trackingCode: item.tracking_code,
          expectedQuantity,
        })
        setTrackingOpen(true)
        return
      }

      if (linesReadOnly) return
      const worksheetPage = await resolveTrackingWorksheetPage()
      if (!worksheetPage?.PageId) {
        if (!opts?.auto) {
          toast.error('Run seed_pages to configure Item Tracking Lines worksheet')
        }
        return
      }
      setTrackingWorksheetPageOverride(worksheetPage)
      const lineId = Number(line.id)
      const invoiceId = Number(documentHeader.id)
      if (!lineId || !invoiceId) {
        if (!opts?.auto) {
          toast.error('Save the line with an item before entering tracking details')
        }
        return
      }
      setSelectedRowId(line.SystemId)
      setTrackingContext({
        mode: 'open',
        purchaseInvoiceId: invoiceId,
        purchaseInvoiceLineId: lineId,
        itemNo: item.no,
        itemName: item.item_name,
        trackingCode: item.tracking_code,
        expectedQuantity,
      })
      setTrackingOpen(true)
    },
    [
      documentHeader,
      isPostedPurchaseSubform,
      isSalesInvoiceSubform,
      itemTrackingEnabled,
      linesReadOnly,
      resolvePostedTrackingWorksheetPage,
      resolveTrackingWorksheetPage,
    ],
  )

  const selectSalesLot = useCallback(
    (lotNo: string) => {
      if (!salesLotLineId) return
      void lines.updateLineField(salesLotLineId, 'tracking_code', lotNo)
      setSalesLotOpen(false)
      setSalesLotLineId(null)
      setSalesLotOptions([])
      setSalesLotSelected(undefined)
      toast.success(`Lot ${lotNo} selected`)
    },
    [lines, salesLotLineId],
  )

  const itemTrackingActionLabel = useCallback(
    (action: PageAction) => {
      if (isPostedItemTrackingLinesAction(action)) return 'Item Tracking Entries'
      return linesReadOnly ? 'Item Tracking Entries' : action.Caption
    },
    [linesReadOnly],
  )

  const trackingActionsForLine = useCallback(
    (line: DataRecord) =>
      visibleItemTrackingLinePageActions(linePageActions, line, {
        posted: isPostedPurchaseSubform,
      }),
    [isPostedPurchaseSubform, linePageActions],
  )

  const handleCellBlur = useCallback(
    (line: DataRecord, field: PageControlField, val: unknown) => {
      const normalized = normalizeListFieldSaveValue(field, val)
      if (listFieldValuesEqual(normalized, line[field.Name], field)) return
      if (
        field.HasTableRelation
        && (normalized == null || normalized === '')
        && line[field.Name] != null
        && line[field.Name] !== ''
      ) {
        return
      }

      const dependentFields = getDependentRelationFields(repeaterControl.Fields, field.Name)
      const autoRepopulatedFields = new Set([
        'description',
        'item_unit_of_measure',
        'quantity',
        'unit_cost',
      ])
      if (field.Name === 'type') {
        // Blank "Select Type" must not PATCH null (NOT NULL on create) or wipe the line.
        if (normalized == null || normalized === '') return
        const previousType = normalizeListFieldSaveValue(field, line[field.Name])
        void lines.updateLineField(line.SystemId, field.Name, normalized)
        // Only when switching between real types (item → resource). Re-selecting the same
        // type, or setting type for the first time, must not wipe No. / UOM / Location.
        const typeSwitched =
          previousType != null
          && previousType !== normalized
        if (typeSwitched && line.no != null && line.no !== '') {
          void lines.updateLineField(line.SystemId, 'no', '')
        }
        return
      }
      if (dependentFields.length > 0) {
        void lines.updateLineField(line.SystemId, field.Name, normalized)
        for (const dep of dependentFields) {
          void loadContextRelationOptions(dep, { ...line, [field.Name]: normalized })
          if (line[dep.Name] && !autoRepopulatedFields.has(dep.Name)) {
            void lines.updateLineField(line.SystemId, dep.Name, '')
          }
        }
        return
      }
      void lines.updateLineField(line.SystemId, field.Name, normalized)
    },
    [
      lines,
      loadContextRelationOptions,
      repeaterControl.Fields,
    ],
  )

  const commitActiveLineCell = useCallback(() => {
    if (!editingCell) return
    const line = lines.lines.find((row) => row.SystemId === editingCell.systemId)
    const field = visibleFields.find((f) => f.Name === editingCell.field)
    if (!line || !field || !lineFieldEditable(field, line)) return

    // Relation fields save on dropdown selection (onChange), not from the search input.
    if (field.HasTableRelation) return

    const commitValue = readActiveCellCommitValue(
      document.activeElement as HTMLElement | null,
      field,
    )
    if (commitValue !== undefined) {
      handleCellBlur(line, field, commitValue)
    }
  }, [editingCell, handleCellBlur, lineFieldEditable, lines.lines, visibleFields])

  const navigateLineCell = useCallback(
    (direction: 'left' | 'right' | 'up' | 'down') => {
      commitActiveLineCell()
      if (!editingCell || lines.lines.length === 0) return
      const next = moveGridActiveCell(editingCell, direction, visibleFields, lines.lines)
      if (!next) return
      const line = lines.lines.find((row) => row.SystemId === next.systemId)
      const field = visibleFields.find((f) => f.Name === next.field)
      if (!line || !field) return
      focusLineCell(line, field)
    },
    [commitActiveLineCell, editingCell, focusLineCell, lines.lines, visibleFields],
  )

  useWorksheetGridKeyboard({
    enabled: !linesReadOnly && partPage.ModifyAllowed && lines.lines.length > 0,
    gridRef: linesGridRef,
    records: lines.lines,
    visibleFields,
    editingCell,
    selectedRowId,
    fieldEditable: lineFieldEditable,
    focusCell: focusLineCell,
    commitActiveCell: commitActiveLineCell,
    navigateCell: navigateLineCell,
    onEscape: () => setTypeahead(null),
  })

  useEffect(() => {
    if (!typeahead) return
    const timer = window.setTimeout(() => setTypeahead(null), 0)
    return () => window.clearTimeout(timer)
  }, [typeahead])

  const firstField = visibleFields[0]
  const restFields = visibleFields.slice(1)
  const firstColPad = firstField?.Name === 'type' ? 'px-2' : 'px-4'
  // Pixel width of the first frozen field (for sticky offset calculations)
  const firstFieldPx = firstField ? colWidthPx(firstField) : 0
  // Total left offset for remaining frozen fields: indicator + firstField + menu
  const restSelectorPx = ROW_INDICATOR_PX + firstFieldPx + MENU_COL_PX

  const toggleRowSelection = useCallback((systemId: string) => {
    setSelectedRowIds((prev) => {
      const next = new Set(prev)
      if (next.has(systemId)) next.delete(systemId)
      else next.add(systemId)
      return next
    })
  }, [])

  const handleSelectMore = useCallback((systemId: string) => {
    if (multiSelectMode) {
      setMultiSelectMode(false)
      setSelectedRowIds(new Set())
      setSelectedRowId(systemId)
      return
    }
    setEditingCell(null)
    setTypeahead(null)
    setMultiSelectMode(true)
    setSelectedRowId(null)
    setSelectedRowIds(new Set([systemId]))
  }, [multiSelectMode])

  const isRowSelected = useCallback(
    (systemId: string) =>
      multiSelectMode ? selectedRowIds.has(systemId) : selectedRowId === systemId,
    [multiSelectMode, selectedRowIds, selectedRowId],
  )

  const handleToggleSelectMoreFromRibbon = useCallback(() => {
    if (multiSelectMode) {
      const first = selectedRowIds.size > 0 ? [...selectedRowIds][0] : selectedRowId
      setMultiSelectMode(false)
      setSelectedRowIds(new Set())
      if (first) setSelectedRowId(first)
      return
    }
    if (selectedRowId) {
      setEditingCell(null)
      setTypeahead(null)
      setMultiSelectMode(true)
      setSelectedRowIds(new Set([selectedRowId]))
      setSelectedRowId(null)
    }
  }, [multiSelectMode, selectedRowIds, selectedRowId])

  useEffect(() => {
    setSelectedRowIds((prev) => {
      const lineIds = new Set(lines.lines.map((l) => l.SystemId))
      const next = new Set([...prev].filter((id) => lineIds.has(id)))
      return next.size === prev.size ? prev : next
    })
  }, [lines.lines])

  const handleBulkDelete = useCallback(async () => {
    if (lines.isDeleting) return
    const ids = [...selectedRowIds]
    setPendingBulkDelete(false)
    for (const id of ids) {
      try {
        await lines.deleteLine(id)
      } catch {
        break
      }
    }
    setSelectedRowIds(new Set())
    setMultiSelectMode(false)
  }, [lines, selectedRowIds])

  const handleRowClick = useCallback(
    (line: DataRecord) => {
      if (multiSelectMode) {
        toggleRowSelection(line.SystemId)
        return
      }
      setSelectedRowId(line.SystemId)
      const field = visibleFields.find((f) => lineFieldEditable(f, line)) ?? visibleFields[0]
      if (field) focusLineCell(line, field)
    },
    [focusLineCell, lineFieldEditable, multiSelectMode, toggleRowSelection, visibleFields],
  )

  const handleCellClick = (line: DataRecord, field: PageControlField) => {
    if (multiSelectMode) {
      toggleRowSelection(line.SystemId)
      return
    }
    setSelectedRowId(line.SystemId)
    if (
      isSalesInvoiceSubform
      && itemTrackingEnabled
      && !linesReadOnly
      && field.Name === 'tracking_code'
    ) {
      void openTrackingForLine(line)
      return
    }
    commitActiveLineCell()
    focusLineCell(line, field)
  }

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement
      if (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.tagName === 'SELECT') return
      if (t.closest('[class*="relation-select"]')) return
      if (e.key !== 'Delete' || linesReadOnly || !partPage.DeleteAllowed) return
      e.preventDefault()
      if (multiSelectMode && selectedRowIds.size > 0) setPendingBulkDelete(true)
      else if (selectedRowId) void lines.deleteLine(selectedRowId)
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [
    lines,
    linesReadOnly,
    multiSelectMode,
    partPage.DeleteAllowed,
    selectedRowId,
    selectedRowIds,
  ])

  // colSpanTotal = indicator + firstField + menu + restFields
  const colSpanTotal = visibleFields.length + 2

  const selectedLine = useMemo(
    () => lines.lines.find((line) => line.SystemId === selectedRowId) ?? null,
    [lines.lines, selectedRowId],
  )

  const editingLine = useMemo(
    () =>
      editingCell
        ? lines.lines.find((line) => line.SystemId === editingCell.systemId) ?? null
        : null,
    [editingCell, lines.lines],
  )

  const effectiveSelectedLine =
    selectedLine ?? editingLine ?? (lines.lines.length === 1 ? lines.lines[0] : null)

  const resolveApplyWorksheetPage = useCallback(
    (line: DataRecord) => {
      const actions = visibleLinePageActions(linePageActions, line)
      const action = actions[0]
      if (!action) return undefined
      const kind = applyEntriesPartyKind(action)
      if (kind === 'customer') return applyCustomerEntriesPage
      return applyVendorEntriesPage
    },
    [applyCustomerEntriesPage, applyVendorEntriesPage, linePageActions],
  )

  const canApplyEntries =
    applyEntriesEnabled &&
    !linesReadOnly &&
    recordReady &&
    !!paymentHeader &&
    !!effectiveSelectedLine &&
    visibleLinePageActions(linePageActions, effectiveSelectedLine).length > 0 &&
    !!resolveApplyWorksheetPage(effectiveSelectedLine)

  const openApplyForLine = useCallback(
    (line: DataRecord) => {
      if (!applyEntriesEnabled || !paymentHeader) {
        toast.error('Apply Entries is not available on this document')
        return
      }
      const worksheetPage = resolveApplyWorksheetPage(line)
      if (!worksheetPage) {
        toast.error('Run seed_pages to configure Apply Entries worksheets')
        return
      }
      const ctx = buildApplyEntriesContext(line, paymentHeader)
      if (!ctx) {
        toast.error('Set Account Type to Customer or Vendor and choose an Account No.')
        return
      }
      setSelectedRowId(line.SystemId)
      setApplyWorksheetPage(worksheetPage)
      setApplyModalContextOverride(ctx)
      setApplyModalOpen(true)
    },
    [applyEntriesEnabled, paymentHeader, resolveApplyWorksheetPage],
  )

  const applyModalContext =
    applyModalContextOverride
    ?? (effectiveSelectedLine && paymentHeader
      ? buildApplyEntriesContext(effectiveSelectedLine, paymentHeader)
      : null)

  const openApplyModal = useCallback(() => {
    if (!effectiveSelectedLine) {
      toast.error('Select a payment line first')
      return
    }
    openApplyForLine(effectiveSelectedLine)
  }, [openApplyForLine, effectiveSelectedLine])

  const openNavigateForLine = useCallback(
    (line: DataRecord, action: PageAction) => {
      const href = buildLineNavigateHref(
        action,
        line,
        allPages,
        visibleFields,
        returnUrl,
      )
      if (!href) {
        toast.error('Could not open the linked page.')
        return
      }
      router.push(href)
    },
    [allPages, returnUrl, router, visibleFields],
  )

  const pageFunctionItems = useMemo(() => {
    if (!effectiveSelectedLine || !recordReady) return []

    const items: Array<{
      id: string
      label: string
      icon: React.ComponentType<{ size?: number; className?: string }>
      disabled?: boolean
      onClick: () => void
    }> = []

    for (const action of visibleNavigateLinePageActions(linePageActions, effectiveSelectedLine)) {
      const Icon = resolveRibbonIcon(action.ImageUrl)
      items.push({
        id: `nav-${action.ActionId}`,
        label: action.Caption,
        icon: Icon,
        onClick: () => openNavigateForLine(effectiveSelectedLine, action),
      })
    }

    if (applyEntriesEnabled && !linesReadOnly) {
      for (const action of visibleLinePageActions(linePageActions, effectiveSelectedLine)) {
        const Icon = resolveRibbonIcon(action.ImageUrl)
        const worksheetPage = applyEntriesPartyKind(action) === 'customer'
          ? applyCustomerEntriesPage
          : applyVendorEntriesPage
        items.push({
          id: `action-${action.ActionId}`,
          label: action.Caption,
          icon: Icon,
          disabled: !worksheetPage,
          onClick: () => openApplyForLine(effectiveSelectedLine),
        })
      }
    }
    if (itemTrackingEnabled) {
      const trackingActions = trackingActionsForLine(effectiveSelectedLine)
      if (trackingActions.length > 0) {
        for (const action of trackingActions) {
          const Icon = resolveRibbonIcon(action.ImageUrl)
          items.push({
            id: `action-${action.ActionId}`,
            label: itemTrackingActionLabel(action),
            icon: Icon,
            onClick: () => void openTrackingForLine(effectiveSelectedLine),
          })
        }
      } else if (isSalesInvoiceSubform && !linesReadOnly) {
        items.push({
          id: 'action-sales-item-tracking',
          label: 'Item Tracking Lines',
          icon: Barcode,
          onClick: () => void openTrackingForLine(effectiveSelectedLine),
        })
      }
    }

    return items
  }, [
    applyCustomerEntriesPage,
    applyEntriesEnabled,
    applyVendorEntriesPage,
    effectiveSelectedLine,
    isSalesInvoiceSubform,
    itemTrackingEnabled,
    linePageActions,
    linesReadOnly,
    openApplyForLine,
    openNavigateForLine,
    itemTrackingActionLabel,
    trackingActionsForLine,
    openTrackingForLine,
    recordReady,
  ])

  const rowApplyExtraItems = useCallback(
    (line: DataRecord) => {
      const items: Array<{
        id: string
        label: string
        icon: React.ComponentType<{ size?: number; className?: string }>
        disabled?: boolean
        onClick: () => void
      }> = []

      for (const action of visibleNavigateLinePageActions(linePageActions, line)) {
        const Icon = resolveRibbonIcon(action.ImageUrl)
        items.push({
          id: `nav-${action.ActionId}`,
          label: action.Caption,
          icon: Icon,
          onClick: () => openNavigateForLine(line, action),
        })
      }

      if (applyEntriesEnabled && !linesReadOnly) {
        for (const action of visibleLinePageActions(linePageActions, line)) {
          const Icon = resolveRibbonIcon(action.ImageUrl)
          const worksheetPage = applyEntriesPartyKind(action) === 'customer'
            ? applyCustomerEntriesPage
            : applyVendorEntriesPage
          items.push({
            id: `action-${action.ActionId}`,
            label: action.Caption,
            icon: Icon,
            disabled: !worksheetPage,
            onClick: () => openApplyForLine(line),
          })
        }
      }

      if (itemTrackingEnabled) {
        const trackingActions = trackingActionsForLine(line)
        if (trackingActions.length > 0) {
          for (const action of trackingActions) {
            const Icon = resolveRibbonIcon(action.ImageUrl)
            items.push({
              id: `action-${action.ActionId}`,
              label: itemTrackingActionLabel(action),
              icon: Icon,
              onClick: () => void openTrackingForLine(line),
            })
          }
        } else if (isSalesInvoiceSubform && !linesReadOnly) {
          items.push({
            id: 'action-sales-item-tracking',
            label: 'Item Tracking Lines',
            icon: Barcode,
            onClick: () => void openTrackingForLine(line),
          })
        }
      }

      return items
    },
    [
      applyCustomerEntriesPage,
      applyEntriesEnabled,
      applyVendorEntriesPage,
      isSalesInvoiceSubform,
      itemTrackingEnabled,
      linePageActions,
      itemTrackingActionLabel,
      linesReadOnly,
      trackingActionsForLine,
      openApplyForLine,
      openNavigateForLine,
      openTrackingForLine,
    ],
  )

  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
      <DocumentLinesRibbon
        recordReady={recordReady}
        linesReadOnly={linesReadOnly}
        insertAllowed={!!partPage.InsertAllowed}
        deleteAllowed={!!partPage.DeleteAllowed}
        hasSelection={multiSelectMode ? selectedRowIds.size > 0 : selectedRowId != null}
        multiSelectMode={multiSelectMode}
        selectedCount={selectedRowIds.size}
        isAdding={lines.isAdding}
        isDeleting={lines.isDeleting}
        lineCount={lines.lines.length}
        onRefresh={() => lines.refetch()}
        onAddLine={() => void lines.addLine()}
        onDeleteLine={() => {
          if (lines.isDeleting) return
          if (multiSelectMode && selectedRowIds.size > 0) {
            setPendingBulkDelete(true)
            return
          }
          if (!selectedRowId) return
          void lines.deleteLine(selectedRowId)
        }}
        onToggleSelectMore={handleToggleSelectMoreFromRibbon}
        canApplyEntries={canApplyEntries}
        onApplyEntries={openApplyModal}
        pageFunctionItems={pageFunctionItems}
      />

      <ConfirmDialog
        open={pendingBulkDelete}
        title="Delete lines"
        message={`Delete ${selectedRowIds.size} selected line${selectedRowIds.size !== 1 ? 's' : ''}?`}
        confirmLabel="Delete"
        variant="danger"
        onConfirm={() => void handleBulkDelete()}
        onCancel={() => setPendingBulkDelete(false)}
      />

      <DynamicWorksheetModal
        open={applyModalOpen}
        worksheetPage={applyWorksheetPage ?? applyVendorEntriesPage ?? applyCustomerEntriesPage}
        applyPayment={
          applyModalContext
            ? {
              ...applyModalContext,
              onApplied: () => onHeaderRefresh?.(),
            }
            : null
        }
        onClose={() => {
          setApplyModalOpen(false)
          setApplyModalContextOverride(null)
          setApplyWorksheetPage(undefined)
        }}
      />

      <DynamicTrackingModal
        open={trackingOpen}
        context={trackingContext}
        worksheetPage={trackingWorksheetPage}
        readOnly={linesReadOnly}
        onClose={() => {
          setTrackingOpen(false)
          setTrackingContext(null)
          setTrackingWorksheetPageOverride(undefined)
        }}
      />

      <POSTrackingDialog
        open={salesLotOpen}
        itemName={salesLotItemName}
        options={salesLotOptions}
        loading={salesLotLoading}
        mode="lot"
        selectedLotNo={salesLotSelected}
        onClose={() => {
          setSalesLotOpen(false)
          setSalesLotLineId(null)
          setSalesLotOptions([])
          setSalesLotSelected(undefined)
        }}
        onSelectLot={selectSalesLot}
        onConfirmSerials={() => {}}
      />

      {!recordReady ? (
        <div className="px-6 py-10 text-center text-sm text-bodyText">{saveFirstHint}</div>
      ) : lines.isError ? (
        <div className="p-4">
          <ErrorBanner message={lines.errorMessage} onRetry={() => lines.refetch()} />
        </div>
      ) : (
        <div
          ref={linesGridRef}
          tabIndex={0}
          className="overflow-x-auto max-h-105 overflow-y-auto outline-none focus:ring-2 focus:ring-s1/20 rounded-b-xl"
        >
          <table className="w-full min-w-max text-sm border-collapse">
            <thead className="sticky top-0 z-30">
              <tr className="bg-gray-50 border-b border-gray-200">
                {/* row-indicator */}
                <th className="sticky left-0 z-50 bg-gray-50 py-3"
                    style={{ width: ROW_INDICATOR_PX, minWidth: ROW_INDICATOR_PX }} />
                {/* first data column header — always sticky */}
                {firstField && (
                  <th
                    className={cn(
                      'sticky z-40 bg-gray-50 py-3 text-left text-xs font-medium text-bodyText uppercase tracking-wide whitespace-nowrap',
                      firstColPad,
                    )}
                    style={{ left: ROW_INDICATOR_PX, width: firstFieldPx, minWidth: firstFieldPx, maxWidth: firstFieldPx }}
                  >
                    {firstField.Caption}
                  </th>
                )}
                {/* menu column header */}
                <th
                  className="sticky z-40 bg-gray-50 py-3 shadow-[2px_0_4px_-1px_rgba(0,0,0,0.08)]"
                  style={{ left: ROW_INDICATOR_PX + firstFieldPx, width: MENU_COL_PX, minWidth: MENU_COL_PX }}
                />
                {/* remaining data column headers */}
                {restFields.map((f, fi) => {
                  const frozen = worksheetFrozenFieldProps(restFields, fi, 'header', { selectorColPx: restSelectorPx })
                  return (
                    <th key={f.PageControlFieldId} className={frozen.className} style={frozen.style}>
                      {f.Caption}
                    </th>
                  )
                })}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 [&_td]:overflow-visible">
              {lines.isLoading ? (
                [...Array(3)].map((_, i) => (
                  <tr key={i} className="bg-white">
                    <td className="sticky left-0 bg-gray-50 py-3"
                        style={{ width: ROW_INDICATOR_PX, minWidth: ROW_INDICATOR_PX }} />
                    {firstField && (
                      <td
                        className={cn('sticky bg-gray-50 py-3', firstColPad)}
                        style={{ left: ROW_INDICATOR_PX, width: firstFieldPx, minWidth: firstFieldPx, maxWidth: firstFieldPx }}
                      >
                        <div className="h-4 bg-gray-100 rounded animate-pulse" />
                      </td>
                    )}
                    <td className="sticky bg-gray-50 py-3 shadow-[2px_0_4px_-1px_rgba(0,0,0,0.08)]"
                        style={{ left: ROW_INDICATOR_PX + firstFieldPx, width: MENU_COL_PX, minWidth: MENU_COL_PX }} />
                    {restFields.map((f, fi) => {
                      const frozen = worksheetFrozenFieldProps(restFields, fi, 'skeleton', { selectorColPx: restSelectorPx })
                      return (
                        <td key={f.PageControlFieldId} className={frozen.className} style={frozen.style}>
                          <div className="h-4 bg-gray-100 rounded animate-pulse" />
                        </td>
                      )
                    })}
                  </tr>
                ))
              ) : lines.lines.length === 0 ? (
                <tr>
                  <td colSpan={colSpanTotal} className="px-4 py-8 text-center text-bodyText">
                    {linesReadOnly
                      ? 'No lines on this posted document.'
                      : 'No lines yet. Click Add Line to get started.'}
                  </td>
                </tr>
              ) : (
                lines.lines.map((line) => (
                  <LineRow
                    key={line.SystemId}
                    line={line}
                    firstField={firstField ?? null}
                    restFields={restFields}
                    firstFieldPx={firstFieldPx}
                    firstColPad={firstColPad}
                    restSelectorPx={restSelectorPx}
                    modifyAllowed={partPage.ModifyAllowed && !linesReadOnly}
                    deleteAllowed={partPage.DeleteAllowed && !linesReadOnly}
                    insertAllowed={partPage.InsertAllowed && !linesReadOnly}
                    controlEditable={repeaterControl.Editable !== false}
                    rowSelected={isRowSelected(line.SystemId)}
                    editingCell={editingCell}
                    typeahead={typeahead}
                    multiSelectMode={multiSelectMode}
                    getFieldRelationOptions={getFieldRelationOptions}
                    isFieldRelationLoading={isFieldRelationLoading}
                    onCellClick={handleCellClick}
                    onCellBlur={handleCellBlur}
                    onDelete={lines.deleteLine}
                    onAddLine={lines.addLine}
                    onRowClick={() => handleRowClick(line)}
                    onToggleRowSelect={() => toggleRowSelection(line.SystemId)}
                    onSelectMore={handleSelectMore}
                    isDeleting={lines.isDeleting}
                    applyExtraItems={rowApplyExtraItems(line)}
                  />
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function LineRow({
  line,
  firstField,
  restFields,
  firstFieldPx,
  firstColPad,
  restSelectorPx,
  modifyAllowed,
  deleteAllowed,
  insertAllowed,
  controlEditable,
  rowSelected,
  editingCell,
  typeahead,
  multiSelectMode,
  getFieldRelationOptions,
  isFieldRelationLoading,
  onCellClick,
  onCellBlur,
  onDelete,
  onAddLine,
  onRowClick,
  onToggleRowSelect,
  onSelectMore,
  isDeleting,
  applyExtraItems = [],
}: {
  line: DataRecord
  firstField: PageControlField | null
  restFields: PageControlField[]
  firstFieldPx: number
  firstColPad: string
  restSelectorPx: number
  modifyAllowed: boolean
  deleteAllowed: boolean
  insertAllowed: boolean
  controlEditable: boolean
  rowSelected: boolean
  editingCell: GridActiveCell | null
  typeahead: { cell: GridActiveCell; char: string } | null
  multiSelectMode: boolean
  getFieldRelationOptions: (field: PageControlField, record: DataRecord) => RelationOption[]
  isFieldRelationLoading: (field: PageControlField, record: DataRecord) => boolean
  onCellClick: (line: DataRecord, field: PageControlField) => void
  onCellBlur: (line: DataRecord, field: PageControlField, val: unknown) => void
  onDelete: (systemId: string) => Promise<void>
  onAddLine: () => void
  onRowClick: () => void
  onToggleRowSelect: () => void
  onSelectMore: (id: string) => void
  isDeleting: boolean
  applyExtraItems?: Array<{
    id: string
    label: string
    icon: React.ComponentType<{ size?: number; className?: string }>
    disabled?: boolean
    onClick: () => void
  }>
}) {
  const renderCell = (field: PageControlField) => {
    if (!isControlFieldVisible(field, line)) {
      return {
        canEdit: false,
        isActive: false,
        isEditing: false,
        content: <span className="text-gray-300">—</span>,
      }
    }
    const canEdit = controlEditable && !!field.Editable && modifyAllowed && !field.NoSeriesCode
    const isActive = editingCell?.systemId === line.SystemId && editingCell?.field === field.Name
    const isEditing = isActive && canEdit
    const opts = field.HasTableRelation ? getFieldRelationOptions(field, line) : null
    const relationLoading = field.HasTableRelation ? isFieldRelationLoading(field, line) : false
    const typeaheadChar =
      typeahead?.cell.systemId === line.SystemId && typeahead?.cell.field === field.Name
        ? typeahead.char
        : undefined

    if (field.FieldType === 'Boolean' && canEdit) {
      return {
        canEdit,
        isActive,
        isEditing: false,
        content: (
          <YesNoSelect
            value={line[field.Name]}
            ariaLabel={field.Caption}
            onClick={(e) => e.stopPropagation()}
            onChange={(val) => onCellBlur(line, field, val)}
          />
        ),
      }
    }

    return {
      canEdit,
      isActive,
      isEditing,
      content: isEditing ? (
        opts !== null ? (
          <SearchableRelationSelect
            autoFocus
            initialInput={typeaheadChar}
            options={opts}
            value={resolveRelationSelectValue(line[field.Name], opts)}
            placeholder="Search…"
            isLoading={relationLoading}
            onChange={(val) => onCellBlur(line, field, val)}
          />
        ) : (
          <DynamicField
            field={field}
            value={line[field.Name]}
            singleLine
            compact={field.Name === 'type'}
            listInlineEdit
            autoFocus
            initialInput={typeaheadChar}
            onBlur={(val) => onCellBlur(line, field, val)}
          />
        )
      ) : (
        <span className={cn(
          'truncate',
          !line[field.Name] && line[field.Name] !== 0 ? 'text-gray-400' : 'text-mainTextColor',
        )}>
          {field.HasTableRelation && opts && opts.length > 0
            ? formatRelationDisplay(line[field.Name], field, opts)
            : formatLineValue(line[field.Name], field)}
        </span>
      ),
    }
  }

  return (
    <tr
      className={cn('group transition cursor-default', rowSelected ? 'bg-s1/5' : 'hover:bg-gray-50')}
      onClick={onRowClick}
    >
      {/* Row indicator: checkmark (multi-select) or → (single active row) */}
      <td
        className={cn('sticky left-0 z-20 text-center', stickyPrefix(rowSelected))}
        style={{ width: ROW_INDICATOR_PX, minWidth: ROW_INDICATOR_PX }}
      >
        {multiSelectMode ? (
          <button
            type="button"
            title={rowSelected ? 'Deselect line' : 'Select line'}
            aria-label={rowSelected ? 'Deselect line' : 'Select line'}
            onClick={(e) => {
              e.stopPropagation()
              onToggleRowSelect()
            }}
            className={cn(
              'mx-auto flex h-5 w-5 items-center justify-center rounded-full border-2 transition',
              rowSelected
                ? 'border-s1 bg-s1 text-white'
                : 'border-gray-300 bg-white text-transparent hover:border-s1/60',
            )}
          >
            <Check size={12} strokeWidth={3} />
          </button>
        ) : (
          rowSelected && <ChevronRight size={12} className="text-s1 mx-auto" />
        )}
      </td>

      {/* First data column — sticky, before the ⋮ menu */}
      {firstField && (() => {
        const { canEdit, isActive, isEditing, content } = renderCell(firstField)
        return (
          <td
            className={cn(
              'sticky z-20',
              firstColPad,
              stickyPrefix(rowSelected),
              canEdit && 'cursor-text',
              isActive && !isEditing && 'ring-2 ring-s1/30 ring-inset',
            )}
            style={{ left: ROW_INDICATOR_PX, width: firstFieldPx, minWidth: firstFieldPx, maxWidth: firstFieldPx }}
            onClick={(e) => { e.stopPropagation(); onCellClick(line, firstField) }}
          >
            {content}
          </td>
        )
      })()}

      {/* Three-dot menu column */}
      <td
        className={cn('sticky z-20 text-center shadow-[2px_0_4px_-1px_rgba(0,0,0,0.08)]', stickyPrefix(rowSelected))}
        style={{ left: ROW_INDICATOR_PX + firstFieldPx, width: MENU_COL_PX, minWidth: MENU_COL_PX }}
        onClick={(e) => e.stopPropagation()}
      >
        <WorksheetRowMenu
          insertAllowed={insertAllowed}
          deleteAllowed={deleteAllowed}
          multiSelectActive={multiSelectMode}
          rowSelected={rowSelected}
          onNewLine={onAddLine}
          onDeleteLine={() => { if (!isDeleting) void onDelete(line.SystemId) }}
          onSelectMore={() => onSelectMore(line.SystemId)}
          extraItems={applyExtraItems}
        />
      </td>

      {/* Remaining data columns */}
      {restFields.map((field, fi) => {
        const { canEdit, isActive, isEditing, content } = renderCell(field)
        const frozen = worksheetFrozenFieldProps(restFields, fi, 'body', {
          isSelected: rowSelected,
          selectorColPx: restSelectorPx,
          extraClass: cn(canEdit && 'cursor-text', isActive && !isEditing && 'ring-2 ring-s1/30 ring-inset'),
        })
        return (
          <td
            key={field.PageControlFieldId}
            className={frozen.className}
            style={frozen.style}
            onClick={(e) => { e.stopPropagation(); onCellClick(line, field) }}
          >
            {content}
          </td>
        )
      })}
    </tr>
  )
}

/** @deprecated Use DynamicListPart — kept for existing imports */
export const DocumentLinesSection = DynamicListPart

export default DynamicListPart
