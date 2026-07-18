'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { Download, FileText, Loader2, Paperclip, Trash2, Upload } from 'lucide-react'
import { toast } from 'sonner'
import FactBoxShell from '../FactBoxShell'
import {
  documentAttachmentsService,
  fileExtension,
  type DocumentAttachment,
} from '@/services/documentAttachments.service'
import type { FactBoxProps } from './types'

const ACCEPT =
  '.pdf,.doc,.docx,image/jpeg,image/png,image/gif,image/webp,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document'
const MAX_BYTES = 15 * 1024 * 1024

function validateFile(file: File): string | null {
  if (file.size > MAX_BYTES) {
    return 'File must be 15 MB or smaller.'
  }
  return null
}

export default function DocumentAttachmentsFactBox({
  control,
  parentKey,
  recordReady,
  readOnly,
  saveFirstHint = 'Save the document first',
  storageKey,
}: FactBoxProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [attachments, setAttachments] = useState<DocumentAttachment[]>([])
  const [loading, setLoading] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [dragOver, setDragOver] = useState(false)

  const disabled = readOnly || !recordReady || !parentKey

  const loadAttachments = useCallback(async () => {
    if (!parentKey || !recordReady) {
      setAttachments([])
      return
    }
    setLoading(true)
    try {
      const list = await documentAttachmentsService.list(parentKey)
      setAttachments(list)
    } catch {
      toast.error('Failed to load attachments')
    } finally {
      setLoading(false)
    }
  }, [parentKey, recordReady])

  useEffect(() => {
    loadAttachments()
  }, [loadAttachments])

  const handleUpload = async (file: File) => {
    if (!parentKey) return
    const err = validateFile(file)
    if (err) {
      toast.error(err)
      return
    }
    setUploading(true)
    try {
      const created = await documentAttachmentsService.upload(parentKey, file)
      setAttachments((prev) => [created, ...prev])
      toast.success('Attachment uploaded')
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) handleUpload(file)
    e.target.value = ''
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    if (disabled || uploading) return
    const file = e.dataTransfer.files?.[0]
    if (file) handleUpload(file)
  }

  const handleDelete = async (attachment: DocumentAttachment) => {
    if (!confirm(`Delete "${attachment.display_name || attachment.name}"?`)) return
    setUploading(true)
    try {
      await documentAttachmentsService.remove(attachment.id)
      setAttachments((prev) => prev.filter((item) => item.id !== attachment.id))
      toast.success('Attachment removed')
    } catch {
      toast.error('Failed to delete attachment')
    } finally {
      setUploading(false)
    }
  }

  return (
    <FactBoxShell
      control={control}
      recordReady={recordReady}
      saveFirstHint={saveFirstHint}
      storageKey={storageKey}
    >
      <div className="p-4 space-y-3">
        <div
          onDragOver={(e) => {
            e.preventDefault()
            if (!disabled) setDragOver(true)
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => !disabled && !uploading && inputRef.current?.click()}
          className={[
            'rounded-lg border-2 border-dashed p-3 text-center transition',
            dragOver ? 'border-s1 bg-s1/5' : 'border-gray-200',
            disabled ? 'opacity-60 cursor-not-allowed' : 'cursor-pointer hover:border-s1/50',
          ].join(' ')}
        >
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPT}
            className="hidden"
            disabled={disabled || uploading}
            onChange={handleInputChange}
          />
          {uploading ? (
            <div className="flex items-center justify-center gap-2 py-2 text-xs text-bodyText">
              <Loader2 size={14} className="animate-spin" /> Uploading…
            </div>
          ) : (
            <div className="flex flex-col items-center gap-1 py-1">
              <Upload size={16} className="text-bodyText" />
              <p className="text-xs text-bodyText">
                {disabled ? saveFirstHint : 'Click or drag to attach a file'}
              </p>
              <p className="text-[10px] text-gray-400">PDF, images, Word · max 15 MB</p>
            </div>
          )}
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-6 text-bodyText">
            <Loader2 size={18} className="animate-spin" />
          </div>
        ) : attachments.length === 0 ? (
          <div className="rounded-lg border border-gray-100 bg-gray-50 px-3 py-6 text-center text-xs text-gray-400">
            <Paperclip size={18} className="mx-auto mb-2 opacity-60" />
            There is nothing to show in this view
          </div>
        ) : (
          <div className="overflow-hidden rounded-lg border border-gray-200">
            <table className="w-full text-xs">
              <thead className="bg-gray-50 text-bodyText">
                <tr>
                  <th className="px-3 py-2 text-left font-medium">Name</th>
                  <th className="px-3 py-2 text-left font-medium w-20">Ext.</th>
                  <th className="px-3 py-2 w-16" />
                </tr>
              </thead>
              <tbody>
                {attachments.map((attachment) => {
                  const label = attachment.display_name || attachment.name || 'Attachment'
                  const ext = fileExtension(label)
                  return (
                    <tr key={attachment.id} className="border-t border-gray-100">
                      <td className="px-3 py-2">
                        <div className="flex items-center gap-2 min-w-0">
                          <FileText size={14} className="shrink-0 text-gray-400" />
                          <span className="truncate text-mainTextColor" title={label}>
                            {label}
                          </span>
                        </div>
                      </td>
                      <td className="px-3 py-2 text-bodyText">{ext || '—'}</td>
                      <td className="px-3 py-2">
                        <div className="flex items-center justify-end gap-1">
                          <button
                            type="button"
                            className="p-1 rounded hover:bg-gray-100 text-bodyText"
                            title="Download"
                            onClick={async (e) => {
                              e.stopPropagation()
                              try {
                                await documentAttachmentsService.download(attachment.id, label)
                              } catch {
                                toast.error('Failed to download attachment')
                              }
                            }}
                          >
                            <Download size={12} />
                          </button>
                          {!readOnly && recordReady && (
                            <button
                              type="button"
                              onClick={() => handleDelete(attachment)}
                              className="p-1 rounded hover:bg-red-50 text-red-600"
                              title="Delete"
                            >
                              <Trash2 size={12} />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </FactBoxShell>
  )
}
