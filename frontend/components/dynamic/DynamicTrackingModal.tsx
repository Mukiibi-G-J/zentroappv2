'use client'

import { useRef } from 'react'
import type { PurchaseTrackingContext } from '@/types/tracking'
import type { Page } from '@/types/page'
import DynamicDialogModal from './DynamicDialogModal'
import WorksheetPageView from './WorksheetPageView'

interface Props {
  open: boolean
  context: PurchaseTrackingContext | null
  worksheetPage?: Page | null
  /** View-only mode for posted purchase invoice lines (BC Posted Item Tracking Lines). */
  readOnly?: boolean
  onClose: () => void
}

/** Page-engine dialog host for Item Tracking Lines (BC Page 6510). */
export default function DynamicTrackingModal({
  open,
  context,
  worksheetPage,
  readOnly = false,
  onClose,
}: Props) {
  const dismissRef = useRef<(() => void) | null>(null)

  const requestClose = () => {
    if (dismissRef.current) {
      dismissRef.current()
      return
    }
    onClose()
  }

  if (!open || !context || !worksheetPage?.PageId) return null

  const title = worksheetPage.Caption
  const subtitle = `${context.itemNo} · ${context.itemName}`

  const trackingModalKey =
    context.mode === 'posted'
      ? `${worksheetPage.PageId}-${context.vendorInvoiceNo}-${context.itemNo}`
      : `${worksheetPage.PageId}-${context.purchaseInvoiceLineId}`

  return (
    <DynamicDialogModal
      open={open}
      title={`${title} — ${subtitle}`}
      onClose={requestClose}
      titleId="dynamic-tracking-modal-title"
    >
      <WorksheetPageView
        key={trackingModalKey}
        pageId={worksheetPage.PageId}
        variant="modal"
        trackingContext={context}
        trackingReadOnly={readOnly}
        onClose={onClose}
        modalDismissRef={dismissRef}
      />
    </DynamicDialogModal>
  )
}
