'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { Eye, ImageIcon, Loader2, Trash2, Upload } from 'lucide-react'
import { toast } from 'sonner'
import FactBoxShell from '../FactBoxShell'
import { itemImagesService, type ItemImage } from '@/services/itemImages.service'
import type { FactBoxProps } from './types'

const ACCEPT = 'image/jpeg,image/png,image/webp'
const MAX_BYTES = 500_000

function validateFile(file: File): string | null {
  if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
    return 'Please upload a JPEG, PNG, or WebP image.'
  }
  if (file.size > MAX_BYTES) {
    return 'Image must be 500 KB or smaller.'
  }
  return null
}

export default function ItemImagesFactBox({
  control,
  parentKey,
  recordReady,
  readOnly,
  saveFirstHint = 'Save the item first',
  storageKey,
}: FactBoxProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [images, setImages] = useState<ItemImage[]>([])
  const [loading, setLoading] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [dragOver, setDragOver] = useState(false)

  const disabled = readOnly || !recordReady || !parentKey

  const loadImages = useCallback(async () => {
    if (!parentKey || !recordReady) {
      setImages([])
      return
    }
    setLoading(true)
    try {
      const list = await itemImagesService.list(parentKey)
      setImages(list)
    } catch {
      toast.error('Failed to load images')
    } finally {
      setLoading(false)
    }
  }, [parentKey, recordReady])

  useEffect(() => {
    loadImages()
  }, [loadImages])

  const handleUpload = async (file: File) => {
    if (!parentKey) return
    const err = validateFile(file)
    if (err) {
      toast.error(err)
      return
    }
    setUploading(true)
    try {
      const created = await itemImagesService.upload(parentKey, file)
      setImages((prev) => [created, ...prev])
      toast.success('Image uploaded')
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

  const handleDelete = async (image: ItemImage) => {
    if (!confirm('Delete this image?')) return
    setUploading(true)
    try {
      await itemImagesService.remove(image.id)
      setImages((prev) => prev.filter((img) => img.id !== image.id))
      if (previewUrl === itemImagesService.resolveUrl(image.url)) {
        setPreviewUrl(null)
      }
      toast.success('Image removed')
    } catch {
      toast.error('Failed to delete image')
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
        <div className="mx-auto w-full max-w-[200px] aspect-square rounded-lg border border-gray-200 bg-gray-50 overflow-hidden flex items-center justify-center">
          {loading ? (
            <Loader2 size={24} className="animate-spin text-gray-300" />
          ) : images[0] ? (
            <img
              src={itemImagesService.resolveUrl(images[0].url) ?? ''}
              alt={images[0].alt_text ?? 'Product'}
              className="h-full w-full object-cover"
            />
          ) : (
            <div className="flex flex-col items-center gap-2 text-gray-300 p-4 text-center">
              <ImageIcon size={40} strokeWidth={1.25} />
              <span className="text-xs">No image</span>
            </div>
          )}
        </div>

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
                {disabled ? saveFirstHint : 'Click or drag to add image'}
              </p>
              <p className="text-[10px] text-gray-400">JPEG, PNG · max 500 KB</p>
            </div>
          )}
        </div>

        {images.length > 0 && (
          <div className="grid grid-cols-3 gap-2">
            {images.map((img) => {
              const src = itemImagesService.resolveUrl(img.url)
              return (
                <div
                  key={img.id}
                  className="relative group aspect-square rounded-md border border-gray-200 overflow-hidden bg-gray-50"
                >
                  {src && (
                    <img src={src} alt="" className="h-full w-full object-cover" />
                  )}
                  {!readOnly && recordReady && (
                    <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition flex items-center justify-center gap-2">
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation()
                          setPreviewUrl(src)
                        }}
                        className="p-1 rounded bg-white/90 text-gray-700 hover:bg-white"
                        title="View"
                      >
                        <Eye size={12} />
                      </button>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation()
                          handleDelete(img)
                        }}
                        className="p-1 rounded bg-white/90 text-red-600 hover:bg-white"
                        title="Delete"
                      >
                        <Trash2 size={12} />
                      </button>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>

      {previewUrl && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
          onClick={() => setPreviewUrl(null)}
        >
          <img
            src={previewUrl}
            alt="Preview"
            className="max-h-[90vh] max-w-full rounded-lg object-contain"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}
    </FactBoxShell>
  )
}
