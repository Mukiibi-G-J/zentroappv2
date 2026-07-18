'use client'

import { useMemo } from 'react'
import type { PurchaseTrackingContext } from '@/types/tracking'
import type { Page } from '@/types/page'
import WorksheetEditableGrid from './WorksheetEditableGrid'

interface Props {
  pageId: number
  page: Page
  context: PurchaseTrackingContext
  onClose?: () => void
}

/** BC Page 6511 — read-only item ledger tracking for posted purchase lines. */
export default function PostedItemTrackingWorksheetBody({
  pageId,
  page,
  context,
  onClose,
}: Props) {
  const lineFilters = useMemo(
    () => ({
      vendor_invoice_no: String(context.vendorInvoiceNo ?? '').trim(),
      item: context.itemNo,
    }),
    [context.itemNo, context.vendorInvoiceNo],
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
            <p className="text-xs text-bodyText">Quantity</p>
            <p className="text-sm font-medium text-mainTextColor tabular-nums">{context.expectedQuantity}</p>
          </div>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-auto px-5 py-2">
        <WorksheetEditableGrid
          pageId={pageId}
          page={page}
          lineFilters={lineFilters}
          gridReadOnly
          gridClassName="border-0 max-h-none"
        />
      </div>

      <div className="border-t border-gray-200 bg-gray-50 px-5 py-3">
        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={() => onClose?.()}
            className="rounded-lg border border-gray-200 px-4 py-2 text-sm font-medium text-mainTextColor hover:bg-white"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}
