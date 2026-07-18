'use client'

import { cn } from '@/lib/utils'

interface YesNoSelectProps {
  value: unknown
  disabled?: boolean
  className?: string
  ariaLabel?: string
  onChange: (value: boolean) => void
  onClick?: (e: React.MouseEvent<HTMLSelectElement>) => void
}

export default function YesNoSelect({
  value,
  disabled = false,
  className,
  ariaLabel,
  onChange,
  onClick,
}: YesNoSelectProps) {
  const checked = !!value

  return (
    <select
      value={checked ? 'Yes' : 'No'}
      disabled={disabled}
      aria-label={ariaLabel}
      className={cn(
        'w-full min-w-0 rounded border border-gray-200 bg-white px-2 py-1 text-sm text-mainTextColor',
        'focus:border-s1 focus:outline-none focus:ring-2 focus:ring-s1/30',
        'disabled:bg-gray-50 disabled:text-gray-400',
        className,
      )}
      onClick={onClick}
      onChange={(e) => onChange(e.target.value === 'Yes')}
    >
      <option value="Yes">Yes</option>
      <option value="No">No</option>
    </select>
  )
}
