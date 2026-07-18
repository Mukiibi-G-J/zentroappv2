'use client'

import BooleanToggle from '@/components/ui/BooleanToggle'
import { cn } from '@/lib/utils'

interface BooleanFieldRowProps {
  caption: string
  value: unknown
  disabled?: boolean
  required?: boolean
  className?: string
  onChange: (value: boolean) => void
}

export default function BooleanFieldRow({
  caption,
  value,
  disabled = false,
  required = false,
  className,
  onChange,
}: BooleanFieldRowProps) {
  const checked = !!value

  return (
    <div
      className={cn(
        'grid min-h-9 grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4',
        className,
      )}
    >
      <span className="truncate text-sm text-bodyText" title={caption}>
        {caption}
        {required && <span className="ml-0.5 text-red-500">*</span>}
      </span>
      {disabled ? (
        <span className="text-sm font-medium text-mainTextColor">{checked ? 'Yes' : 'No'}</span>
      ) : (
        <BooleanToggle
          checked={checked}
          disabled={disabled}
          aria-label={caption}
          onChange={onChange}
        />
      )}
    </div>
  )
}
