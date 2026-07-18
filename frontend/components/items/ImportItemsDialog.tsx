'use client'

import { useEffect, useRef, useState } from 'react'
import { Download, Upload } from 'lucide-react'
import { toast } from 'sonner'
import { extractApiErrorMessage } from '@/lib/apiError'
import {
  checkItemImportStatus,
  downloadItemImportTemplate,
  startItemImport,
  type ItemImportMode,
} from '@/services/items.service'

type Props = {
  open: boolean
  onClose: () => void
  onSuccess?: () => void
}

export default function ImportItemsDialog({ open, onClose, onSuccess }: Props) {
  const [importMode, setImportMode] = useState<ItemImportMode>('opening_balance')
  const [file, setFile] = useState<File | null>(null)
  const [taskId, setTaskId] = useState<string | null>(null)
  const [progress, setProgress] = useState(0)
  const [statusMessage, setStatusMessage] = useState('')
  const [loading, setLoading] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const [importResult, setImportResult] = useState<{
    created_count?: number
    updated_count?: number
    failed_count?: number
    total_rows?: number
    errors?: string[]
    journals_created?: number
  } | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    if (!taskId) return
    intervalRef.current = setInterval(async () => {
      try {
        const data = await checkItemImportStatus(taskId)
        setProgress(data.progress || 0)
        setStatusMessage(data.message || '')

        if (data.status === 'success') {
          if (intervalRef.current) clearInterval(intervalRef.current)
          intervalRef.current = null
          setTaskId(null)
          setImportResult({
            created_count: data.created_count,
            updated_count: data.updated_count,
            failed_count: data.failed_count,
            total_rows: data.total_rows,
            errors: data.errors,
            journals_created: data.journals_created,
          })
          setLoading(false)
          const hasErrors = (data.failed_count || 0) > 0
          toast[hasErrors ? 'warning' : 'success'](
            hasErrors
              ? `Created ${data.created_count ?? 0} items; ${data.failed_count} rows had errors.`
              : `Imported ${(data.created_count || 0) + (data.updated_count || 0)} items.`,
          )
          onSuccess?.()
        } else if (data.status === 'failure') {
          if (intervalRef.current) clearInterval(intervalRef.current)
          intervalRef.current = null
          setTaskId(null)
          setLoading(false)
          toast.error(data.error || 'Import failed')
        }
      } catch (err) {
        console.error(err)
      }
    }, 2000)

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
      intervalRef.current = null
    }
  }, [taskId, onSuccess])

  if (!open) return null

  const resetAndClose = () => {
    if (intervalRef.current) clearInterval(intervalRef.current)
    intervalRef.current = null
    setTaskId(null)
    setProgress(0)
    setStatusMessage('')
    setLoading(false)
    setFile(null)
    setImportResult(null)
    setImportMode('opening_balance')
    if (fileInputRef.current) fileInputRef.current.value = ''
    onClose()
  }

  const handleDownloadTemplate = async () => {
    setDownloading(true)
    try {
      await downloadItemImportTemplate(importMode)
      toast.success('Template downloaded')
    } catch (err) {
      toast.error(extractApiErrorMessage(err) || 'Failed to download template')
    } finally {
      setDownloading(false)
    }
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0]
    if (!selected) return
    const ext = selected.name.split('.').pop()?.toLowerCase()
    if (!ext || !['xlsx', 'xls', 'csv'].includes(ext)) {
      toast.error('Please select a valid Excel (.xlsx, .xls) or CSV file')
      return
    }
    setFile(selected)
    setImportResult(null)
  }

  const handleImport = async () => {
    if (!file) {
      toast.error('Please select a file to import')
      return
    }
    setLoading(true)
    setStatusMessage('Starting import…')
    setImportResult(null)
    try {
      const data = await startItemImport(file, importMode)
      setTaskId(data.task_id)
      setProgress(0)
    } catch (err) {
      setLoading(false)
      toast.error(extractApiErrorMessage(err) || 'Failed to start import')
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        type="button"
        aria-label="Close dialog"
        className="absolute inset-0 bg-black/40"
        onClick={resetAndClose}
      />
      <div
        role="dialog"
        aria-modal="true"
        className="relative w-full max-w-lg rounded-2xl bg-white p-6 shadow-xl"
      >
        <h3 className="text-base font-semibold text-mainTextColor">Import Items from Excel</h3>
        <p className="mt-1 text-sm text-bodyText">
          Template includes Unit Price (selling), Unit Cost (purchase), and Quantity.
          Fill Quantity to create opening-balance journals automatically.
        </p>

        <div className="mt-5">
          <p className="mb-2 text-sm font-medium text-mainTextColor">What are you importing?</p>
          <div className="space-y-2 text-sm">
            <label className="flex cursor-pointer items-start gap-2">
              <input
                type="radio"
                name="item_import_mode"
                checked={importMode === 'opening_balance'}
                onChange={() => setImportMode('opening_balance')}
                disabled={loading || !!taskId}
                className="mt-1"
              />
              <span>
                <span className="font-medium text-mainTextColor">Items with opening balances</span>
                <span className="block text-xs text-bodyText">
                  Unit Price = selling price, Unit Cost = purchase/cost price.
                  Rows with Quantity create opening-balance journals for review before posting.
                </span>
              </span>
            </label>
            <label className="flex cursor-pointer items-start gap-2">
              <input
                type="radio"
                name="item_import_mode"
                checked={importMode === 'standard'}
                onChange={() => setImportMode('standard')}
                disabled={loading || !!taskId}
                className="mt-1"
              />
              <span>
                <span className="font-medium text-mainTextColor">Standard items only</span>
                <span className="block text-xs text-bodyText">
                  Create or update item cards only. Quantity column is ignored (no journals).
                </span>
              </span>
            </label>
          </div>
        </div>

        <div className="mt-5">
          <p className="mb-2 text-sm font-medium text-mainTextColor">Step 1: Download template</p>
          <button
            type="button"
            onClick={() => void handleDownloadTemplate()}
            disabled={downloading || loading}
            className="inline-flex items-center gap-2 rounded-xl border border-strokeColor px-3 py-2 text-sm font-medium text-mainTextColor transition hover:bg-softBg disabled:opacity-50"
          >
            <Download size={16} className="text-s1" />
            {downloading ? 'Downloading…' : 'Download Item Import Template'}
          </button>
        </div>

        <div className="mt-5">
          <p className="mb-2 text-sm font-medium text-mainTextColor">Step 2: Select your filled file</p>
          <input
            ref={fileInputRef}
            type="file"
            accept=".xlsx,.xls,.csv"
            onChange={handleFileChange}
            disabled={loading || !!taskId}
            className="block w-full text-sm text-bodyText file:mr-3 file:rounded-md file:border-0 file:bg-[#eef6f7] file:px-3 file:py-1.5 file:text-sm file:font-semibold file:text-s1 disabled:opacity-50"
          />
          {file ? (
            <p className="mt-1 text-xs text-bodyText">Selected: {file.name}</p>
          ) : null}
        </div>

        {(loading || progress > 0) && !importResult ? (
          <div className="mt-5">
            <p className="mb-2 text-sm text-bodyText">{statusMessage || `Progress: ${progress}%`}</p>
            <div className="h-2 w-full rounded-full bg-gray-200">
              <div
                className="h-2 rounded-full bg-s1 transition-all duration-300"
                style={{ width: `${Math.min(progress, 100)}%` }}
              />
            </div>
          </div>
        ) : null}

        {importResult ? (
          <div className="mt-5 rounded-xl bg-softBg p-4 text-sm">
            <p className="mb-2 font-semibold text-mainTextColor">Import results</p>
            <div className="grid grid-cols-2 gap-1 text-bodyText">
              <span>Total rows</span>
              <span className="font-medium text-mainTextColor">{importResult.total_rows ?? 0}</span>
              <span>Created</span>
              <span className="font-medium text-mainTextColor">{importResult.created_count ?? 0}</span>
              <span>Updated</span>
              <span className="font-medium text-mainTextColor">{importResult.updated_count ?? 0}</span>
              <span>Failed</span>
              <span className="font-medium text-mainTextColor">{importResult.failed_count ?? 0}</span>
            </div>
            {(importResult.errors?.length ?? 0) > 0 ? (
              <ul className="mt-2 list-disc space-y-1 pl-4 text-xs text-red-600">
                {importResult.errors!.slice(0, 5).map((err) => (
                  <li key={err}>{err}</li>
                ))}
              </ul>
            ) : null}
          </div>
        ) : null}

        <div className="mt-6 flex flex-wrap justify-end gap-2">
          <button
            type="button"
            onClick={resetAndClose}
            disabled={loading && !importResult}
            className="rounded-xl border border-strokeColor px-4 py-2.5 text-sm font-medium text-bodyText transition hover:bg-softBg disabled:opacity-50"
          >
            {importResult ? 'Close' : 'Cancel'}
          </button>
          {!importResult ? (
            <button
              type="button"
              onClick={() => void handleImport()}
              disabled={!file || loading || !!taskId}
              className="inline-flex items-center gap-2 rounded-xl bg-s1 px-4 py-2.5 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
            >
              <Upload size={16} />
              {loading ? 'Importing…' : 'Import'}
            </button>
          ) : null}
        </div>
      </div>
    </div>
  )
}
