'use client'

import { useEffect, useRef } from 'react'
import type { ApplyPaymentContext } from '@/lib/applyEntriesContext'
import type { Page } from '@/types/page'
import DynamicDialogModal from './DynamicDialogModal'
import WorksheetPageView from './WorksheetPageView'

interface Props {
  open: boolean
  worksheetPage: Page | null | undefined
  applyPayment: ApplyPaymentContext | null
  onClose: () => void
}

/** Page-engine dialog host for Worksheet pages (e.g. BC Page 233 Apply Vendor Entries). */
export default function DynamicWorksheetModal({
  open,
  worksheetPage,
  applyPayment,
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

  if (!open || !applyPayment || !worksheetPage?.PageId) return null

  const title = worksheetPage.Caption
  const subtitle = `${applyPayment.partyNo}${applyPayment.partyName ? ` · ${applyPayment.partyName}` : ''}`

  return (
    <DynamicDialogModal
      open={open}
      title={`${title} — ${subtitle}`}
      onClose={requestClose}
      titleId="dynamic-worksheet-modal-title"
    >
      <WorksheetPageView
        key={`${worksheetPage.PageId}-${applyPayment.paymentSystemId}`}
        pageId={worksheetPage.PageId}
        variant="modal"
        contextFilterValue={applyPayment.partyNo}
        applyPayment={applyPayment}
        onClose={onClose}
        modalDismissRef={dismissRef}
      />
    </DynamicDialogModal>
  )
}
