'use client'

import { AlertCircle, ArrowLeft, RefreshCw } from 'lucide-react'
import { cn } from '@/lib/utils'

interface ErrorBannerProps {
  message: string
  onRetry?: () => void
  onBack?: () => void
  className?: string
  variant?: 'banner' | 'card'
}

export default function ErrorBanner({
  message,
  onRetry,
  onBack,
  className,
  variant = 'banner',
}: ErrorBannerProps) {
  if (variant === 'card') {
    return (
      <div
        className={cn(
          'flex flex-col items-center justify-center rounded-xl border border-red-200 bg-red-50 p-8 text-center',
          className,
        )}
      >
        <AlertCircle className="mb-3 h-10 w-10 text-red-500" />
        <p className="text-sm font-medium text-red-800">{message}</p>
        <div className="mt-5 flex flex-wrap items-center justify-center gap-3">
          {onRetry && (
            <button
              type="button"
              onClick={onRetry}
              className="inline-flex items-center gap-1.5 rounded-lg bg-s1 px-4 py-2 text-sm font-medium text-white hover:opacity-90 transition"
            >
              <RefreshCw size={14} />
              Retry
            </button>
          )}
          {onBack && (
            <button
              type="button"
              onClick={onBack}
              className="inline-flex items-center gap-1.5 rounded-lg border border-strokeColor bg-white px-4 py-2 text-sm font-medium text-mainTextColor hover:bg-softBg transition"
            >
              <ArrowLeft size={14} />
              Back
            </button>
          )}
        </div>
      </div>
    )
  }

  return (
    <div
      className={cn(
        'flex items-start justify-between gap-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3',
        className,
      )}
      role="alert"
    >
      <div className="flex items-start gap-2 min-w-0">
        <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-500" />
        <p className="text-sm text-red-800">{message}</p>
      </div>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-red-200 bg-white px-3 py-1.5 text-xs font-medium text-red-700 hover:bg-red-100 transition"
        >
          <RefreshCw size={12} />
          Retry
        </button>
      )}
    </div>
  )
}
