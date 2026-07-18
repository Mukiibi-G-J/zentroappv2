'use client'

import { useRef, useState } from 'react'
import { Building2, Loader2, Upload } from 'lucide-react'
import { toast } from 'sonner'
import { uploadCompanyLogo } from '@/services/company.service'
import { resolveMediaUrl } from '@/lib/media'

interface Props {
  logoUrl: string | null | undefined
  onUploaded: (logoUrl: string | null) => void
}

export default function CompanyLogoField({ logoUrl, onUploaded }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)
  const src = resolveMediaUrl(logoUrl ?? null)

  const handleFile = async (file: File) => {
    const allowed = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif']
    if (!allowed.includes(file.type)) {
      toast.error('Upload a JPEG, PNG, or GIF image')
      return
    }
    if (file.size > 5 * 1024 * 1024) {
      toast.error('Image must be 5 MB or smaller')
      return
    }

    setUploading(true)
    try {
      const url = await uploadCompanyLogo(file)
      onUploaded(url)
      toast.success('Company logo updated')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to upload logo')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="flex items-center gap-4">
      <div className="h-20 w-20 rounded-xl border border-gray-200 bg-gray-50 overflow-hidden flex items-center justify-center shrink-0">
        {src ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={src} alt="Company logo" className="h-full w-full object-cover" />
        ) : (
          <Building2 className="h-8 w-8 text-bodyText/40" />
        )}
      </div>
      <div>
        <input
          ref={inputRef}
          type="file"
          accept="image/jpeg,image/png,image/gif"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0]
            if (file) void handleFile(file)
            e.target.value = ''
          }}
        />
        <button
          type="button"
          disabled={uploading}
          onClick={() => inputRef.current?.click()}
          className="inline-flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm font-medium text-mainTextColor hover:bg-gray-50 disabled:opacity-60 transition"
        >
          {uploading ? <Loader2 size={14} className="animate-spin" /> : <Upload size={14} />}
          {uploading ? 'Uploading…' : 'Upload logo'}
        </button>
        <p className="mt-1 text-xs text-bodyText">JPEG, PNG, or GIF · max 5 MB</p>
      </div>
    </div>
  )
}
