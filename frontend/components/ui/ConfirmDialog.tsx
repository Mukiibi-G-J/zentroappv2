'use client'

interface ConfirmDialogProps {
  open: boolean
  title?: string
  message: string
  confirmLabel?: string
  cancelLabel?: string
  /** When true, only the primary OK button is shown (BC-style info/error alerts). */
  alertOnly?: boolean
  variant?: 'default' | 'danger'
  onConfirm: () => void
  onCancel: () => void
}

export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  alertOnly = false,
  variant = 'default',
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        type="button"
        aria-label="Close dialog"
        className="absolute inset-0 bg-black/40"
        onClick={onCancel}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? 'confirm-dialog-title' : undefined}
        className="relative w-full max-w-sm rounded-2xl bg-white p-6 shadow-xl"
      >
        {title ? (
          <h3 id="confirm-dialog-title" className="text-base font-semibold text-mainTextColor">
            {title}
          </h3>
        ) : null}
        <p className={`text-sm text-bodyText whitespace-pre-line ${title ? 'mt-2' : ''}`}>{message}</p>
        <div className="mt-5 flex justify-end gap-2">
          {!alertOnly ? (
            <button
              type="button"
              onClick={onCancel}
              className="rounded-xl border border-strokeColor px-4 py-2.5 text-sm font-medium text-bodyText transition hover:bg-softBg"
            >
              {cancelLabel}
            </button>
          ) : null}
          <button
            type="button"
            onClick={onConfirm}
            className={
              variant === 'danger'
                ? 'rounded-xl bg-red-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-red-700'
                : 'rounded-xl bg-s1 px-4 py-2.5 text-sm font-semibold text-white transition hover:opacity-90'
            }
          >
            {alertOnly ? (confirmLabel === 'Confirm' ? 'OK' : confirmLabel) : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
