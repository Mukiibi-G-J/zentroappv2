'use client'

import { formatDecimalDisplay } from '@/lib/formatNumber'
import type { POSDraftSale } from '@/types/pos'

interface POSDraftDialogProps {
  open: boolean
  drafts: POSDraftSale[]
  loading?: boolean
  onClose: () => void
  onResume: (draft: POSDraftSale) => void
  onDelete: (draft: POSDraftSale) => void
}

export function POSDraftDialog({
  open,
  drafts,
  loading,
  onClose,
  onResume,
  onDelete,
}: POSDraftDialogProps) {
  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-4 sm:items-center">
      <div className="w-full max-w-md rounded-2xl bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-strokeColor px-5 py-4">
          <h2 className="text-lg font-semibold text-mainTextColor">Saved drafts</h2>
          <button type="button" onClick={onClose} className="text-sm text-bodyText hover:text-mainTextColor">
            Close
          </button>
        </div>

        <div className="max-h-[50vh] overflow-y-auto p-5">
          {loading ? (
            <p className="text-sm text-bodyText">Loading drafts…</p>
          ) : drafts.length === 0 ? (
            <p className="text-sm text-bodyText">No saved POS drafts.</p>
          ) : (
            <ul className="space-y-3">
              {drafts.map((draft) => (
                <li
                  key={draft.id}
                  className="rounded-xl border border-strokeColor p-4"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="font-medium text-mainTextColor">
                        {draft.invoice_no || `Draft #${draft.id}`}
                      </p>
                      <p className="text-sm text-bodyText">{draft.customer_name}</p>
                      <p className="mt-1 text-sm font-semibold text-s1">
                        {formatDecimalDisplay(draft.total_amount)}
                      </p>
                      <p className="text-xs text-bodyText">
                        {draft.lines.length} item{draft.lines.length !== 1 ? 's' : ''}
                      </p>
                    </div>
                    <div className="flex shrink-0 flex-col gap-2">
                      <button
                        type="button"
                        onClick={() => onResume(draft)}
                        className="rounded-lg bg-s1 px-3 py-1.5 text-xs font-medium text-white"
                      >
                        Resume
                      </button>
                      <button
                        type="button"
                        onClick={() => onDelete(draft)}
                        className="text-xs text-red-600 hover:underline"
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  )
}
