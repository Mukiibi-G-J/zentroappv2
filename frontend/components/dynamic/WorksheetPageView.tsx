'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { getFieldCaption } from '@/lib/fieldCaption'
import { formatDecimalDisplay } from '@/lib/formatNumber'
import { getRecordFieldValue } from '@/lib/recordFieldValue'
import type { ApplyPaymentContext } from '@/lib/applyEntriesContext'
import type { PurchaseTrackingContext } from '@/types/tracking'
import {
  buildContextLineFilters,
  buildAmountToApplySignError,
  amountToApplySignIsValid,
  findHeaderGroupControl,
  findWorksheetFooterControl,
  findWorksheetLinesControl,
  getAmountToApplyForRow,
  getLedgerEntryId,
  isDialogApplyWorksheet,
  isEditableContextWorksheet,
  isSetAppliesToIdAction,
  isShowSelectedOnlyAction,
  isRowMarkedForPayment,
  parseAmountInput,
  appliesToIdDisplay,
  rowRemainingAmount,
  visibleLineFields,
  worksheetShowsSearch,
} from '@/lib/worksheetControls'
import { usePage } from '@/hooks/usePage'
import { usePageDataInfinite } from '@/hooks/usePageData'
import {
  applyCustomerEntry,
  applyVendorEntry,
  clearAppliesToStamps,
  clearLedgerAppliesToId,
  setLedgerAppliesToId,
  unapplyCustomerEntry,
  unapplyVendorEntry,
} from '@/services/payments.service'
import WorksheetLinesGrid, { type WorksheetApplySession } from './WorksheetLinesGrid'
import ItemTrackingWorksheetBody from './ItemTrackingWorksheetBody'
import PostedItemTrackingWorksheetBody from './PostedItemTrackingWorksheetBody'
import WorksheetRibbon from './WorksheetRibbon'
import type { Page, PageAction, PageControlField } from '@/types/page'
import type { DataRecord } from '@/types/pagedata'

function formatFooterValue(value: number): string {
  return value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function formatHeaderValue(value: unknown, field: PageControlField): string {
  if (value === null || value === undefined || value === '') return ''
  if (field.FieldType === 'Decimal' || field.FieldType === 'Integer') {
    const n = Number(value)
    if (!Number.isNaN(n)) return formatFooterValue(n)
  }
  if (field.FieldType === 'Date' && value) {
    try {
      return new Date(String(value)).toLocaleDateString()
    } catch {
      return String(value)
    }
  }
  return String(value)
}

export interface WorksheetPageViewProps {
  pageId: number
  variant?: 'page' | 'modal'
  /** Party / context filter value (e.g. vendor no from payment line). */
  contextFilterValue?: string
  /** Applying document shown in header card General group (e.g. payment journal). */
  applyingRecord?: ApplyPaymentContext['paymentHeader'] | null
  applyPayment?: ApplyPaymentContext | null
  /** Item Tracking Lines (BC 6510) opened from purchase invoice subform. */
  trackingContext?: PurchaseTrackingContext | null
  /** View-only tracking worksheet when opened from a posted purchase invoice. */
  trackingReadOnly?: boolean
  onClose?: () => void
  /** When variant is modal, parent can wire X/backdrop to the same dismiss handler as Cancel. */
  modalDismissRef?: React.MutableRefObject<(() => void) | null>
}

export default function WorksheetPageView({
  pageId,
  variant = 'modal',
  contextFilterValue,
  applyingRecord,
  applyPayment,
  trackingContext,
  trackingReadOnly = false,
  onClose,
  modalDismissRef,
}: WorksheetPageViewProps) {
  const [selectedSystemId, setSelectedSystemId] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [showSelectedOnly, setShowSelectedOnly] = useState(false)
  const [appliesToOverrides, setAppliesToOverrides] = useState<Record<string, string>>({})
  const [amountToApplyBySystemId, setAmountToApplyBySystemId] = useState<Record<string, string>>({})
  const [amountToApplyErrors, setAmountToApplyErrors] = useState<Record<string, string>>({})

  const { data: page, isLoading: pageLoading } = usePage(pageId)
  const { data: headerPage } = usePage(page?.HeaderPageId ?? undefined)

  const linesControl = findWorksheetLinesControl(page)
  const footerControl = findWorksheetFooterControl(page)
  const headerControl = findHeaderGroupControl(headerPage)

  const headerFields = useMemo(
    () => headerControl?.Fields.filter((f) => f.Visible) ?? [],
    [headerControl?.Fields],
  )

  const lineFields = useMemo(
    () => visibleLineFields(linesControl?.Fields, page?.ContextFilterField),
    [linesControl?.Fields, page?.ContextFilterField],
  )

  const partyNo = contextFilterValue ?? applyPayment?.partyNo ?? ''
  const applyingHeader = applyingRecord ?? applyPayment?.paymentHeader ?? null

  const paymentAppliesToId = useMemo(() => {
    if (!applyingHeader) return ''
    return String(getRecordFieldValue(applyingHeader, 'document_no') || '').trim()
  }, [applyingHeader])

  const lineFilters = useMemo(
    () => buildContextLineFilters(page, partyNo),
    [page, partyNo],
  )

  const {
    data,
    isLoading,
    isError,
    error,
    refetch,
    isFetching,
  } = usePageDataInfinite(
    pageId,
    linesControl?.PageControlId,
    undefined,
    lineFilters,
    { enabled: !!page && !!linesControl && !!partyNo },
  )

  const records = useMemo(() => {
    const raw = data?.pages.flatMap((p) => p) ?? []
    return [...new Map(raw.map((r) => [r.SystemId, r])).values()]
  }, [data])

  const ribbonActions = useMemo(
    () => (page?.PageActions ?? []).filter(
      (action) => action.Visible && (
        isSetAppliesToIdAction(action) || isShowSelectedOnlyAction(action)
      ),
    ),
    [page?.PageActions],
  )

  const ribbonActionsWithToggleLabel = useMemo(
    () => ribbonActions.map((action) => {
      if (!isShowSelectedOnlyAction(action)) return action
      return {
        ...action,
        Caption: showSelectedOnly ? 'Show All Entries' : action.Caption,
      }
    }),
    [ribbonActions, showSelectedOnly],
  )

  useEffect(() => {
    if (!applyPayment) return
    if (applyPayment.appliedLedgerId != null) {
      const match = records.find(
        (row) => getLedgerEntryId(row) === applyPayment.appliedLedgerId,
      )
      if (match) setSelectedSystemId(match.SystemId)
    } else if (records.length === 1) {
      setSelectedSystemId(records[0].SystemId)
    }
  }, [applyPayment, records])

  const visibleRecords = useMemo(() => {
    if (!showSelectedOnly || !selectedSystemId) return records
    return records.filter((row) => row.SystemId === selectedSystemId)
  }, [records, showSelectedOnly, selectedSystemId])

  const selectedRecord = records.find((row) => row.SystemId === selectedSystemId) ?? null
  const footerFields = footerControl?.Fields.filter((f) => f.Visible) ?? []

  const appliedTotal = useMemo(() => {
    if (!applyPayment) return 0
    return records.reduce((sum, row) => {
      const remaining = rowRemainingAmount(row)
      const amount = getAmountToApplyForRow(
        row,
        appliesToOverrides,
        paymentAppliesToId,
        amountToApplyBySystemId,
      )
      if (!amountToApplySignIsValid(remaining, amount)) return sum
      return sum + amount
    }, 0)
  }, [records, appliesToOverrides, paymentAppliesToId, amountToApplyBySystemId, applyPayment])

  const selectedAmountToApply = selectedRecord && applyPayment
    ? getAmountToApplyForRow(
      selectedRecord,
      appliesToOverrides,
      paymentAppliesToId,
      amountToApplyBySystemId,
    )
    : 0

  const availableAmount = applyingHeader
    ? Number(getRecordFieldValue(applyingHeader, 'amount')) || 0
    : 0

  const footerValues: Record<string, string> = {
    amount_to_apply: formatFooterValue(selectedAmountToApply),
    applied_amount: formatFooterValue(appliedTotal),
    available_amount: formatFooterValue(availableAmount),
    // BC Page 233: Balance = Applied Amount + Available Amount (+ rounding/discount when added)
    balance: formatFooterValue(appliedTotal + availableAmount),
  }

  const clearRowApplication = useCallback((systemId: string) => {
    setAppliesToOverrides((prev) => ({ ...prev, [systemId]: '' }))
    setAmountToApplyBySystemId((prev) => {
      const next = { ...prev }
      delete next[systemId]
      return next
    })
    setAmountToApplyErrors((prev) => {
      const next = { ...prev }
      delete next[systemId]
      return next
    })
  }, [])

  const persistClearAppliesToId = useCallback(async (row: DataRecord) => {
    if (!applyPayment) return
    const ledgerId = getLedgerEntryId(row)
    if (!ledgerId) return
    setSaving(true)
    try {
      await clearLedgerAppliesToId(
        applyPayment.paymentSystemId,
        ledgerId,
        applyPayment.partyKind,
        applyPayment.journalSource,
      )
      clearRowApplication(row.SystemId)
      toast.success('Applies-to ID cleared')
      void refetch()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to clear Applies-to ID')
    } finally {
      setSaving(false)
    }
  }, [applyPayment, clearRowApplication, refetch])

  const handleSetAppliesToId = async () => {
    if (!applyPayment || !selectedRecord) {
      toast.error('Select a ledger entry first')
      return
    }
    if (!paymentAppliesToId) {
      toast.error('Save the payment document number before setting Applies-to ID')
      return
    }
    const ledgerId = getLedgerEntryId(selectedRecord)
    if (!ledgerId) {
      toast.error('Selected entry has no entry number')
      return
    }

    setSaving(true)
    try {
      const result = await setLedgerAppliesToId(
        applyPayment.paymentSystemId,
        ledgerId,
        applyPayment.partyKind,
        applyPayment.journalSource,
      )
      if (result.cleared || !result.applies_to_id) {
        clearRowApplication(selectedRecord.SystemId)
        toast.success('Applies-to ID cleared')
      } else {
        setAppliesToOverrides((prev) => ({
          ...prev,
          [selectedRecord.SystemId]: result.applies_to_id,
        }))
        setAmountToApplyBySystemId((prev) => ({
          ...prev,
          [selectedRecord.SystemId]: formatDecimalDisplay(rowRemainingAmount(selectedRecord)),
        }))
        setAmountToApplyErrors((prev) => {
          const next = { ...prev }
          delete next[selectedRecord.SystemId]
          return next
        })
        toast.success(`Applies-to ID set to ${result.applies_to_id}`)
      }
      void refetch()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update Applies-to ID')
    } finally {
      setSaving(false)
    }
  }

  const handleAppliesToIdChange = useCallback((systemId: string, value: string) => {
    setAppliesToOverrides((prev) => ({ ...prev, [systemId]: value }))
  }, [])

  const handleAppliesToIdBlur = useCallback(async (row: DataRecord, raw: string) => {
    if (!applyPayment) return
    const trimmed = raw.trim()
    const ledgerId = getLedgerEntryId(row)
    const persistedId = String(getRecordFieldValue(row, 'applies_to_id') || '').trim()
    const displayBeforeEdit = persistedId || appliesToOverrides[row.SystemId] || ''

    if (!trimmed) {
      if (persistedId || row.SystemId in appliesToOverrides) {
        await persistClearAppliesToId(row)
      }
      return
    }

    if (trimmed === displayBeforeEdit) return

    if (trimmed !== paymentAppliesToId) {
      toast.error(`Applies-to ID must be ${paymentAppliesToId} or blank`)
      setAppliesToOverrides((prev) => {
        const next = { ...prev }
        if (persistedId) delete next[row.SystemId]
        else next[row.SystemId] = displayBeforeEdit
        return next
      })
      return
    }

    if (!ledgerId) {
      toast.error('Selected entry has no entry number')
      return
    }

    setSaving(true)
    try {
      const result = await setLedgerAppliesToId(
        applyPayment.paymentSystemId,
        ledgerId,
        applyPayment.partyKind,
        applyPayment.journalSource,
      )
      if (result.cleared || !result.applies_to_id) {
        clearRowApplication(row.SystemId)
        toast.success('Applies-to ID cleared')
      } else {
        setAppliesToOverrides((prev) => ({
          ...prev,
          [row.SystemId]: result.applies_to_id,
        }))
        setAmountToApplyBySystemId((prev) => ({
          ...prev,
          [row.SystemId]: formatDecimalDisplay(rowRemainingAmount(row)),
        }))
        toast.success(`Applies-to ID set to ${result.applies_to_id}`)
      }
      void refetch()
    } catch (err) {
      setAppliesToOverrides((prev) => {
        const next = { ...prev }
        if (persistedId) delete next[row.SystemId]
        else next[row.SystemId] = displayBeforeEdit
        return next
      })
      toast.error(err instanceof Error ? err.message : 'Failed to update Applies-to ID')
    } finally {
      setSaving(false)
    }
  }, [
    applyPayment,
    appliesToOverrides,
    clearRowApplication,
    paymentAppliesToId,
    persistClearAppliesToId,
    refetch,
  ])

  const handleRibbonAction = (action: PageAction) => {
    if (isSetAppliesToIdAction(action)) {
      void handleSetAppliesToId()
      return
    }
    if (isShowSelectedOnlyAction(action)) {
      setShowSelectedOnly((v) => !v)
    }
  }

  const handleAmountBlur = useCallback((systemId: string, raw: string) => {
    const row = records.find((r) => r.SystemId === systemId)
    if (!row || !applyPayment) return
    const remaining = rowRemainingAmount(row)
    const parsed = parseAmountInput(raw)
    if (parsed === null) {
      setAmountToApplyBySystemId((prev) => ({
        ...prev,
        [systemId]: formatDecimalDisplay(remaining),
      }))
      setAmountToApplyErrors((prev) => {
        const next = { ...prev }
        delete next[systemId]
        return next
      })
      return
    }
    if (parsed === 0) {
      if (isRowMarkedForPayment(row, appliesToOverrides, paymentAppliesToId)) {
        void persistClearAppliesToId(row)
      } else {
        setAmountToApplyBySystemId((prev) => {
          const next = { ...prev }
          delete next[systemId]
          return next
        })
      }
      return
    }
    if (!amountToApplySignIsValid(remaining, parsed)) {
      const entryNo = getLedgerEntryId(row)
      const message = buildAmountToApplySignError(applyPayment.partyKind, entryNo)
      toast.error(message)
      setAmountToApplyErrors((prev) => ({ ...prev, [systemId]: message }))
      setAmountToApplyBySystemId((prev) => ({
        ...prev,
        [systemId]: formatDecimalDisplay(remaining),
      }))
      return
    }
    setAmountToApplyErrors((prev) => {
      const next = { ...prev }
      delete next[systemId]
      return next
    })
    setAmountToApplyBySystemId((prev) => ({
      ...prev,
      [systemId]: formatDecimalDisplay(parsed),
    }))
  }, [applyPayment, appliesToOverrides, paymentAppliesToId, persistClearAppliesToId, records])

  const validateMarkedAmounts = useCallback((): boolean => {
    if (!applyPayment) return true
    let valid = true
    const nextErrors: Record<string, string> = {}
    for (const row of records) {
      if (!isRowMarkedForPayment(row, appliesToOverrides, paymentAppliesToId)) continue
      const remaining = rowRemainingAmount(row)
      const amount = getAmountToApplyForRow(
        row,
        appliesToOverrides,
        paymentAppliesToId,
        amountToApplyBySystemId,
      )
      if (!amountToApplySignIsValid(remaining, amount)) {
        const entryNo = getLedgerEntryId(row)
        nextErrors[row.SystemId] = buildAmountToApplySignError(applyPayment.partyKind, entryNo)
        valid = false
      }
    }
    if (!valid) {
      setAmountToApplyErrors(nextErrors)
      const firstMessage = Object.values(nextErrors)[0]
      if (firstMessage) toast.error(firstMessage)
    }
    return valid
  }, [
    applyPayment,
    records,
    appliesToOverrides,
    paymentAppliesToId,
    amountToApplyBySystemId,
  ])

  const dismissModal = useCallback(
    async (opts?: { skipStampClear?: boolean }) => {
      if (
        applyPayment
        && !opts?.skipStampClear
        && !applyPayment.appliedLedgerId
      ) {
        try {
          await clearAppliesToStamps(
            applyPayment.paymentSystemId,
            applyPayment.partyKind,
            applyPayment.journalSource,
          )
        } catch {
          // Closing the dialog should not be blocked by stamp cleanup.
        }
      }
      onClose?.()
    },
    [applyPayment, onClose],
  )

  useEffect(() => {
    if (variant !== 'modal' || !modalDismissRef) return
    modalDismissRef.current = () => {
      void dismissModal()
    }
    return () => {
      modalDismissRef.current = null
    }
  }, [dismissModal, modalDismissRef, variant])

  const handleOk = async () => {
    if (!applyPayment || !selectedRecord) {
      toast.error('Select an entry to apply')
      return
    }
    if (!validateMarkedAmounts()) return
    const ledgerId = getLedgerEntryId(selectedRecord)
    if (!ledgerId) {
      toast.error('Selected entry has no entry number')
      return
    }
    setSaving(true)
    try {
      const journalSource = applyPayment.journalSource
      const result = applyPayment.partyKind === 'customer'
        ? await applyCustomerEntry(applyPayment.paymentSystemId, ledgerId, journalSource)
        : await applyVendorEntry(applyPayment.paymentSystemId, ledgerId, journalSource)
      const docNo = 'customer_ledger_document_no' in result
        ? result.customer_ledger_document_no
        : result.vendor_ledger_document_no
      toast.success(`Applied to ${docNo}`)
      applyPayment.onApplied?.()
      await dismissModal({ skipStampClear: true })
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to apply entry')
    } finally {
      setSaving(false)
    }
  }

  const handleUnapply = async () => {
    if (!applyPayment) return
    setSaving(true)
    try {
      const journalSource = applyPayment.journalSource
      if (applyPayment.partyKind === 'customer') {
        await unapplyCustomerEntry(applyPayment.paymentSystemId, journalSource)
      } else {
        await unapplyVendorEntry(applyPayment.paymentSystemId, journalSource)
      }
      toast.success('Application cleared')
      applyPayment.onApplied?.()
      await dismissModal({ skipStampClear: true })
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to unapply')
    } finally {
      setSaving(false)
    }
  }

  const applySession: WorksheetApplySession | null = applyPayment
    ? {
      paymentAppliesToId,
      appliesToOverrides,
      amountToApplyBySystemId,
      amountToApplyErrors,
      onAppliesToIdChange: handleAppliesToIdChange,
      onAppliesToIdBlur: handleAppliesToIdBlur,
      onAmountChange: (systemId, value) => {
        setAmountToApplyBySystemId((prev) => ({ ...prev, [systemId]: value }))
        setAmountToApplyErrors((prev) => {
          if (!prev[systemId]) return prev
          const next = { ...prev }
          delete next[systemId]
          return next
        })
      },
      onAmountBlur: handleAmountBlur,
      saving,
    }
    : null

  if (pageLoading || !page) {
    return (
      <div className="flex items-center justify-center gap-2 py-16 text-sm text-bodyText">
        <Loader2 size={16} className="animate-spin" />
        Loading worksheet…
      </div>
    )
  }

  if (trackingContext && isEditableContextWorksheet(page)) {
    if (trackingContext.mode === 'posted') {
      return (
        <PostedItemTrackingWorksheetBody
          pageId={pageId}
          page={page}
          context={trackingContext}
          onClose={onClose}
        />
      )
    }
    return (
      <ItemTrackingWorksheetBody
        pageId={pageId}
        page={page}
        context={trackingContext}
        readOnly={trackingReadOnly}
        onClose={onClose}
        modalDismissRef={modalDismissRef}
      />
    )
  }

  if (!isDialogApplyWorksheet(page)) {
    return (
      <p className="px-5 py-10 text-center text-sm text-bodyText">
        Page {page.Caption} is not configured as a dialog apply worksheet.
      </p>
    )
  }

  const partyLabel = applyPayment?.partyKind === 'customer' ? 'customer' : 'vendor'

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {headerFields.length > 0 && applyingHeader ? (
        <div className="border-b border-gray-100 bg-gray-50/80 px-5 py-4">
          <p className="mb-3 text-xs font-medium uppercase tracking-wide text-bodyText">
            {headerControl?.Caption ?? 'General'}
          </p>
          <div className="grid grid-cols-2 gap-x-8 gap-y-3 md:grid-cols-4">
            {headerFields.map((field) => {
              const value = getRecordFieldValue(applyingHeader, field.Name)
              if (value === null || value === undefined || value === '') return null
              return (
                <div key={field.PageControlFieldId}>
                  <p className="text-xs text-bodyText">{getFieldCaption(field, headerPage)}</p>
                  <p className="text-sm font-medium text-mainTextColor">
                    {formatHeaderValue(value, field)}
                  </p>
                </div>
              )
            })}
          </div>
        </div>
      ) : null}

      <div className="border-b border-gray-100 px-5 py-2">
        <WorksheetRibbon
          pageActions={ribbonActionsWithToggleLabel}
          insertAllowed={false}
          search=""
          onSearch={() => {}}
          onRefresh={() => void refetch()}
          onAddNew={() => {}}
          onAction={handleRibbonAction}
          isRefreshing={isFetching}
          actionLoading={saving}
          showSearch={worksheetShowsSearch(page, variant)}
        />
        {applyPayment?.appliedLedgerId ? (
          <div className="mt-2 flex justify-end">
            <button
              type="button"
              disabled={saving}
              onClick={() => void handleUnapply()}
              className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-1.5 text-sm text-amber-900 hover:bg-amber-100 disabled:opacity-40"
            >
              Clear Application
            </button>
          </div>
        ) : null}
      </div>

      <div className="min-h-0 flex-1 overflow-auto">
        {isLoading ? (
          <div className="flex items-center justify-center gap-2 py-16 text-sm text-bodyText">
            <Loader2 size={16} className="animate-spin" />
            Loading open {partyLabel} entries…
          </div>
        ) : isError ? (
          <div className="px-5 py-10 text-center text-sm text-red-600">
            {error instanceof Error ? error.message : 'Failed to load entries'}
          </div>
        ) : visibleRecords.length === 0 ? (
          <div className="px-5 py-10 text-center text-sm text-bodyText">
            No open entries for {partyLabel} {partyNo}.
          </div>
        ) : (
          <WorksheetLinesGrid
            page={page}
            fields={lineFields}
            records={visibleRecords}
            selectedSystemId={selectedSystemId}
            onSelectRow={setSelectedSystemId}
            applySession={applySession}
          />
        )}
      </div>

      {footerFields.length > 0 ? (
        <div className="border-t border-gray-200 bg-gray-50 px-5 py-3">
          <div className="mb-3 flex flex-wrap gap-6 text-sm">
            {footerFields.map((field) => (
              <div key={field.PageControlFieldId}>
                <span className="text-bodyText">{getFieldCaption(field, page)}: </span>
                <span className="font-medium tabular-nums text-mainTextColor">
                  {footerValues[field.Name] ?? '0.00'}
                </span>
              </div>
            ))}
          </div>
          {variant === 'modal' ? (
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => void dismissModal()}
                disabled={saving}
                className="rounded-lg border border-gray-200 px-4 py-2 text-sm font-medium text-mainTextColor hover:bg-white disabled:opacity-40"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => void handleOk()}
                disabled={saving || !selectedRecord || isLoading}
                className="inline-flex items-center gap-2 rounded-lg bg-s1 px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-40"
              >
                {saving ? <Loader2 size={14} className="animate-spin" /> : null}
                OK
              </button>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
