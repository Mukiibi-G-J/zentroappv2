'use client'

import { FileSpreadsheet, FileText } from 'lucide-react'

type Props = {
  open: boolean
  loading?: boolean
  progressMessage?: string
  onClose: () => void
  onExportExcel: () => void
  onExportPdf: () => void
}

export default function ExportItemsModal({
  open,
  loading = false,
  progressMessage,
  onClose,
  onExportExcel,
  onExportPdf,
}: Props) {
  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        type="button"
        aria-label="Close dialog"
        className="absolute inset-0 bg-black/40"
        onClick={loading ? undefined : onClose}
        disabled={loading}
      />
      <div
        role="dialog"
        aria-modal="true"
        className="relative w-full max-w-sm rounded-2xl bg-white p-6 shadow-xl"
      >
        <h3 className="text-base font-semibold text-mainTextColor">Export Items</h3>
        <p className="mt-2 text-sm text-bodyText">
          {loading
            ? progressMessage || 'Preparing export…'
            : 'Choose a format to export the current item list.'}
        </p>

        <div className="mt-5 flex flex-wrap justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            disabled={loading}
            className="rounded-xl border border-strokeColor px-4 py-2.5 text-sm font-medium text-bodyText transition hover:bg-softBg disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onExportPdf}
            disabled={loading}
            className="inline-flex items-center gap-2 rounded-xl border border-strokeColor px-4 py-2.5 text-sm font-semibold text-mainTextColor transition hover:bg-softBg disabled:opacity-50"
          >
            <FileText size={16} />
            {loading ? 'Exporting…' : 'PDF'}
          </button>
          <button
            type="button"
            onClick={onExportExcel}
            disabled={loading}
            className="inline-flex items-center gap-2 rounded-xl bg-s1 px-4 py-2.5 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
          >
            <FileSpreadsheet size={16} />
            {loading ? 'Exporting…' : 'Excel'}
          </button>
        </div>
      </div>
    </div>
  )
}
