'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { cn } from '@/lib/utils'
import { getFieldCaption } from '@/lib/fieldCaption'
import { getRecordFieldValue } from '@/lib/recordFieldValue'
import { useUpdateField } from '@/hooks/usePageData'
import { checkLotNumber } from '@/services/tracking.service'
import {
  findWorksheetFooterControl,
  findWorksheetLinesControl,
  visibleLineFields,
} from '@/lib/worksheetControls'
import type { PurchaseTrackingContext } from '@/types/tracking'
import type { Page, PageControlField } from '@/types/page'
import type { DataRecord } from '@/types/pagedata'
import { isDeleteTrackingLineAction } from '@/lib/documentLineActions'
import { listFieldValuesEqual, normalizeListFieldSaveValue } from '@/lib/listFieldValue'
import { toast } from 'sonner'
import WorksheetEditableGrid from './WorksheetEditableGrid'

function fieldVisibleForTracking(
  field: PageControlField,
  tracking: PurchaseTrackingContext['trackingCode'],
): boolean {
  if (field.Name === 'serial_no') return tracking.require_serial_no
  if (field.Name === 'lot_no') return tracking.require_lot_no
  if (field.Name === 'expiry_date') return tracking.require_expiry_date
  return true
}

interface Props {
  pageId: number
  page: Page
  context: PurchaseTrackingContext
  /** View-only when opened from a posted purchase invoice line. */
  readOnly?: boolean
  onClose?: () => void
  modalDismissRef?: React.MutableRefObject<(() => void) | null>
}

/** Tracking-specific header/footer around the shared editable worksheet grid. */
export default function ItemTrackingWorksheetBody({
  pageId,
  page,
  context,
  readOnly = false,
  onClose,
  modalDismissRef,
}: Props) {
  const tracking = context.trackingCode
  const [lotExpiryLocked, setLotExpiryLocked] = useState<Record<string, boolean>>({})
  const [records, setRecords] = useState<DataRecord[]>([])
  const checkedLotsRef = useRef<Record<string, string>>({})

  const linesControl = findWorksheetLinesControl(page)
  const footerControl = findWorksheetFooterControl(page)
  const footerFields = footerControl?.Fields.filter((f) => f.Visible) ?? []

  const expiryField = useMemo(
    () => visibleLineFields(linesControl?.Fields, page.ContextFilterField)
      .find((f) => f.Name === 'expiry_date'),
    [linesControl?.Fields, page.ContextFilterField],
  )

  const lineFilters = useMemo(
    () => ({ purchase_invoice_line: String(context.purchaseInvoiceLineId ?? '') }),
    [context.purchaseInvoiceLineId],
  )

  const updateField = useUpdateField(pageId, linesControl?.PageControlId)

  const summary = useMemo(() => {
    const totalQuantity = records.reduce(
      (sum, row) => sum + (Number(getRecordFieldValue(row, 'quantity_base')) || 0),
      0,
    )
    const expected = context.expectedQuantity
    return {
      expected_quantity: expected,
      total_quantity: totalQuantity,
      remaining_quantity: expected - totalQuantity,
      specifications_count: records.length,
    }
  }, [records, context.expectedQuantity])

  const footerValues: Record<string, string> = {
    expected_quantity: String(summary.expected_quantity),
    total_quantity: String(summary.total_quantity),
    remaining_quantity: String(summary.remaining_quantity),
    specifications_count: String(summary.specifications_count),
  }

  const ribbonPageActions = useMemo(
    () =>
      (page.PageActions ?? [])
        .filter((a) => a.Visible && (!readOnly || !isDeleteTrackingLineAction(a))),
    [page.PageActions, readOnly],
  )

  const dismissModal = useCallback(() => {
    onClose?.()
  }, [onClose])

  useEffect(() => {
    if (!modalDismissRef) return
    modalDismissRef.current = dismissModal
    return () => {
      modalDismissRef.current = null
    }
  }, [dismissModal, modalDismissRef])

  const applyExistingLot = useCallback(
    async (record: DataRecord, lotNo: string, opts?: { notify?: boolean }) => {
      const trimmed = lotNo.trim()
      const rowKey = record.SystemId

      if (!trimmed || !tracking.require_lot_no) {
        setLotExpiryLocked((prev) => ({ ...prev, [rowKey]: false }))
        delete checkedLotsRef.current[rowKey]
        return
      }

      if (checkedLotsRef.current[rowKey] === trimmed) return
      checkedLotsRef.current[rowKey] = trimmed

      try {
        const result = await checkLotNumber(trimmed, context.itemNo)
        if (result.exists) {
          setLotExpiryLocked((prev) => ({ ...prev, [rowKey]: true }))
          if (result.expiry_date && expiryField) {
            const normalizedExpiry = normalizeListFieldSaveValue(expiryField, result.expiry_date)
            const currentExpiry = getRecordFieldValue(record, 'expiry_date')
            if (!listFieldValuesEqual(normalizedExpiry, currentExpiry, expiryField)) {
              updateField.mutate({
                systemId: record.SystemId,
                field: expiryField,
                value: normalizedExpiry,
              })
            }
          }
          if (opts?.notify && result.expiry_date) {
            toast.info(
              `Existing lot found — expiry date set to ${new Date(result.expiry_date).toLocaleDateString()} and locked.`,
            )
          }
        } else {
          setLotExpiryLocked((prev) => ({ ...prev, [rowKey]: false }))
        }
      } catch {
        delete checkedLotsRef.current[rowKey]
      }
    },
    [context.itemNo, expiryField, tracking.require_lot_no, updateField],
  )

  useEffect(() => {
    for (const record of records) {
      const lotNo = String(getRecordFieldValue(record, 'lot_no') ?? '').trim()
      const rowKey = record.SystemId
      if (!lotNo) {
        setLotExpiryLocked((prev) => {
          if (!prev[rowKey]) return prev
          const next = { ...prev }
          delete next[rowKey]
          return next
        })
        delete checkedLotsRef.current[rowKey]
        continue
      }
      if (checkedLotsRef.current[rowKey] === lotNo) continue
      void applyExistingLot(record, lotNo)
    }
  }, [applyExistingLot, records])

  const isFieldEditable = useCallback(
    (field: PageControlField, record: DataRecord) => {
      if (readOnly) return false
      if (field.Name === 'expiry_date' && lotExpiryLocked[record.SystemId]) return false
      return true
    },
    [lotExpiryLocked, readOnly],
  )

  const handleFieldSaved = useCallback(
    (record: DataRecord, field: PageControlField, value: unknown) => {
      if (field.Name === 'lot_no') {
        delete checkedLotsRef.current[record.SystemId]
        void applyExistingLot(record, String(value ?? ''), { notify: true })
      }
    },
    [applyExistingLot],
  )

  const getCreatePayload = useCallback(
    () => ({
      purchase_invoice_line: context.purchaseInvoiceLineId,
      purchase_invoice: context.purchaseInvoiceId,
      quantity_base: summary.remaining_quantity > 0 ? summary.remaining_quantity : 1,
      description: '',
    }),
    [context.purchaseInvoiceId, context.purchaseInvoiceLineId, summary.remaining_quantity],
  )

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="border-b border-gray-100 bg-gray-50/80 px-5 py-4">
        <p className="mb-3 text-xs font-medium uppercase tracking-wide text-bodyText">General</p>
        <div className="grid grid-cols-2 gap-x-8 gap-y-3 md:grid-cols-4">
          <div>
            <p className="text-xs text-bodyText">Item No.</p>
            <p className="text-sm font-medium text-mainTextColor">{context.itemNo}</p>
          </div>
          <div className="md:col-span-2">
            <p className="text-xs text-bodyText">Description</p>
            <p className="text-sm font-medium text-mainTextColor">{context.itemName}</p>
          </div>
          <div>
            <p className="text-xs text-bodyText">Item Tracking Code</p>
            <p className="text-sm font-medium text-mainTextColor">{tracking.code}</p>
          </div>
        </div>
        <div className="mt-4 overflow-x-auto">
          <table className="text-sm">
            <thead>
              <tr className="text-bodyText">
                <th className="w-28 pb-1 text-left font-normal" />
                <th className="min-w-[88px] px-4 pb-1 text-left font-normal">Source</th>
                <th className="min-w-[88px] px-4 pb-1 text-left font-normal">Item Tracking</th>
                <th className="min-w-[88px] px-4 pb-1 text-left font-normal">Undefined</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td className="py-0.5 font-medium text-mainTextColor">Quantity</td>
                <td className="px-4 py-0.5 tabular-nums text-mainTextColor">{summary.expected_quantity}</td>
                <td className="px-4 py-0.5 tabular-nums text-mainTextColor">{summary.total_quantity}</td>
                <td
                  className={cn(
                    'px-4 py-0.5 tabular-nums',
                    summary.remaining_quantity !== 0 ? 'font-medium text-amber-700' : 'text-mainTextColor',
                  )}
                >
                  {summary.remaining_quantity}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        {tracking.description ? (
          <p className="mt-2 text-xs text-bodyText">{tracking.description}</p>
        ) : null}
      </div>

      <div className="min-h-0 flex-1 overflow-auto px-5 py-2">
        <WorksheetEditableGrid
          pageId={pageId}
          page={page}
          lineFilters={lineFilters}
          onRecordsChange={setRecords}
          fieldFilter={(field) => fieldVisibleForTracking(field, tracking)}
          isFieldEditable={isFieldEditable}
          onFieldSaved={handleFieldSaved}
          getCreatePayload={readOnly ? undefined : getCreatePayload}
          pageActions={ribbonPageActions}
          gridReadOnly={readOnly}
          gridClassName="border-0 max-h-none"
        />
      </div>

      {footerFields.length > 0 ? (
        <div className="border-t border-gray-200 bg-gray-50 px-5 py-3">
          <div className="mb-3 flex flex-wrap gap-6 text-sm">
            {footerFields.map((field) => (
              <div key={field.PageControlFieldId}>
                <span className="text-bodyText">{getFieldCaption(field, page)}: </span>
                <span
                  className={cn(
                    'font-medium tabular-nums',
                    field.Name === 'remaining_quantity' && summary.remaining_quantity !== 0
                      ? 'text-amber-700'
                      : 'text-mainTextColor',
                  )}
                >
                  {footerValues[field.Name] ?? '0'}
                </span>
              </div>
            ))}
          </div>
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => dismissModal()}
              className="rounded-lg border border-gray-200 px-4 py-2 text-sm font-medium text-mainTextColor hover:bg-white"
            >
              Close
            </button>
          </div>
        </div>
      ) : null}
    </div>
  )
}
