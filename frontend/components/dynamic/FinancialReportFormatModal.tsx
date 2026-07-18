'use client'

import { FileSpreadsheet, FileText } from 'lucide-react'

interface Props {
  open: boolean
  title: string
  reportLabel?: string
  loading?: boolean
  onClose: () => void
  onExportPdf: () => void
  onExportExcel: () => void
}

export default function FinancialReportFormatModal({
  open,
  title,
  reportLabel,
  loading = false,
  onClose,
  onExportPdf,
  onExportExcel,
}: Props) {
  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        type="button"
        aria-label="Close dialog"
        className="absolute inset-0 bg-black/40"
        onClick={onClose}
      />
      <div
        role="dialog"
        aria-modal="true"
        className="relative w-full max-w-sm rounded-2xl bg-white p-6 shadow-xl"
      >
        <h3 className="text-base font-semibold text-mainTextColor">{title}</h3>
        {reportLabel ? (
          <p className="mt-1 text-sm text-bodyText">{reportLabel}</p>
        ) : null}
        <p className="mt-2 text-sm text-bodyText">
          Choose a format to export using the date range in Options.
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
