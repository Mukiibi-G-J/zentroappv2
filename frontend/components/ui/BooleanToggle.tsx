'use client'

import { cn } from '@/lib/utils'

interface BooleanToggleProps {
  checked: boolean
  disabled?: boolean
  className?: string
  onChange?: (checked: boolean) => void
  'aria-label'?: string
}

export default function BooleanToggle({
  checked,
  disabled = false,
  className,
  onChange,
  'aria-label': ariaLabel,
}: BooleanToggleProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={ariaLabel}
      disabled={disabled}
      onClick={() => {
        if (!disabled) onChange?.(!checked)
      }}
      className={cn(
        'relative inline-flex h-6 w-11 shrink-0 items-center rounded-full border-2 border-s1 transition-colors',
        checked ? 'bg-s1' : 'bg-white',
        disabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer',
        className,
      )}
    >
      <span
        className={cn(
          'pointer-events-none inline-block h-4 w-4 rounded-full transition-transform',
          checked ? 'translate-x-[1.35rem] bg-white' : 'translate-x-0.5 bg-s1',
        )}
      />
    </button>
  )
}
