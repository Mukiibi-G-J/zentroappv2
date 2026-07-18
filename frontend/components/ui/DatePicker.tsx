'use client'

import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { Calendar, ChevronLeft, ChevronRight } from 'lucide-react'
import { cn } from '@/lib/utils'
import {
  addMonths,
  formatDisplayDate,
  getCalendarDays,
  isSameCalendarDay,
  parseIsoDate,
  parseTypedDate,
  startOfMonth,
  toIsoDate,
} from '@/lib/dateFormat'

interface Props {
  value: string
  disabled?: boolean
  placeholder?: string
  className?: string
  onChange?: (value: string) => void
}

interface PopoverPosition {
  left: number
  top: number
  width: number
  placement: 'above' | 'below'
}

const WEEKDAYS = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'] as const

export default function DatePicker({
  value,
  disabled,
  placeholder = 'DD-MMM-YYYY',
  className,
  onChange,
}: Props) {
  const [open, setOpen] = useState(false)
  const [mounted, setMounted] = useState(false)
  const [position, setPosition] = useState<PopoverPosition | null>(null)
  const [editing, setEditing] = useState(false)
  const [text, setText] = useState('')
  const selected = parseIsoDate(value)
  const [viewMonth, setViewMonth] = useState(() => startOfMonth(selected ?? new Date()))
  const containerRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const popoverRef = useRef<HTMLDivElement>(null)
  const ignoreBlurRef = useRef(false)

  useEffect(() => {
    setMounted(true)
  }, [])

  useEffect(() => {
    if (selected) setViewMonth(startOfMonth(selected))
  }, [value])

  useEffect(() => {
    if (!editing) setText(formatDisplayDate(value))
  }, [value, editing])

  const updatePosition = () => {
    const container = containerRef.current
    const popover = popoverRef.current
    if (!container) return

    const rect = container.getBoundingClientRect()
    const popoverHeight = popover?.offsetHeight ?? 320
    const spaceBelow = window.innerHeight - rect.bottom
    const placement =
      spaceBelow < popoverHeight + 8 && rect.top > popoverHeight + 8 ? 'above' : 'below'

    setPosition({
      left: rect.left,
      top: placement === 'below' ? rect.bottom + 6 : rect.top - 6,
      width: Math.max(rect.width, 280),
      placement,
    })
  }

  useLayoutEffect(() => {
    if (!open) {
      setPosition(null)
      return
    }
    updatePosition()
    requestAnimationFrame(updatePosition)
  }, [open, viewMonth])

  useEffect(() => {
    if (!open) return

    const closeOnOutside = (event: MouseEvent) => {
      const target = event.target as Node
      if (containerRef.current?.contains(target) || popoverRef.current?.contains(target)) return
      setOpen(false)
    }

    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }

    const reposition = () => updatePosition()

    document.addEventListener('mousedown', closeOnOutside)
    document.addEventListener('keydown', closeOnEscape)
    window.addEventListener('resize', reposition)
    window.addEventListener('scroll', reposition, true)

    return () => {
      document.removeEventListener('mousedown', closeOnOutside)
      document.removeEventListener('keydown', closeOnEscape)
      window.removeEventListener('resize', reposition)
      window.removeEventListener('scroll', reposition, true)
    }
  }, [open])

  const commit = (next: string) => {
    onChange?.(next)
    setText(next ? formatDisplayDate(next) : '')
    setEditing(false)
    setOpen(false)
  }

  const commitTypedInput = () => {
    const trimmed = text.trim()
    if (!trimmed) {
      commit('')
      return
    }
    const parsed = parseTypedDate(trimmed)
    if (parsed) {
      commit(toIsoDate(parsed))
      return
    }
    setText(formatDisplayDate(value))
    setEditing(false)
  }

  const today = new Date()
  const monthLabel = viewMonth.toLocaleString('en-GB', { month: 'long', year: 'numeric' })

  const popover =
    open && position && mounted ? (
      <div
        ref={popoverRef}
        role="dialog"
        aria-label="Choose date"
        className="fixed z-9999 rounded-xl border border-gray-200 bg-white shadow-lg"
        onMouseDown={() => {
          ignoreBlurRef.current = true
        }}
        style={{
          left: position.left,
          top: position.top,
          width: position.width,
          transform: position.placement === 'above' ? 'translateY(-100%)' : undefined,
        }}
      >
        <div className="flex items-center justify-between border-b border-gray-100 px-3 py-2.5">
          <button
            type="button"
            className="rounded-md p-1.5 text-bodyText hover:bg-gray-100"
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => setViewMonth((m) => addMonths(m, -1))}
            aria-label="Previous month"
          >
            <ChevronLeft size={16} />
          </button>
          <span className="text-sm font-semibold text-mainTextColor">{monthLabel}</span>
          <button
            type="button"
            className="rounded-md p-1.5 text-bodyText hover:bg-gray-100"
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => setViewMonth((m) => addMonths(m, 1))}
            aria-label="Next month"
          >
            <ChevronRight size={16} />
          </button>
        </div>

        <div className="grid grid-cols-7 gap-0.5 px-3 pt-2 text-center text-[11px] font-semibold uppercase tracking-wide text-bodyText">
          {WEEKDAYS.map((day) => (
            <span key={day} className="py-1">
              {day}
            </span>
          ))}
        </div>

        <div className="grid grid-cols-7 gap-0.5 px-3 pb-2 pt-1">
          {getCalendarDays(viewMonth).map(({ date, inMonth }) => {
            const iso = toIsoDate(date)
            const isSelected = selected ? isSameCalendarDay(date, selected) : false
            const isToday = isSameCalendarDay(date, today)

            return (
              <button
                key={iso}
                type="button"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => {
                  if (!inMonth) setViewMonth(startOfMonth(date))
                  commit(iso)
                }}
                className={cn(
                  'h-9 rounded-lg text-sm transition',
                  inMonth ? 'text-mainTextColor hover:bg-[#eef6f7]' : 'text-gray-300',
                  isSelected && 'bg-s1 text-white hover:bg-s1',
                  !isSelected && isToday && inMonth && 'ring-1 ring-s1/40 font-semibold text-s1',
                )}
              >
                {date.getDate()}
              </button>
            )
          })}
        </div>

        <div className="flex items-center justify-between border-t border-gray-100 px-3 py-2.5">
          <button
            type="button"
            className="text-sm font-medium text-s1 hover:underline"
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => commit('')}
          >
            Clear
          </button>
          <button
            type="button"
            className="text-sm font-medium text-s1 hover:underline"
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => commit(toIsoDate(today))}
          >
            Today
          </button>
        </div>
      </div>
    ) : null

  return (
    <>
      <div
        ref={containerRef}
        className={cn(
          'flex w-full items-center rounded-lg border border-gray-200 bg-white transition',
          'focus-within:ring-2 focus-within:ring-s1/30 focus-within:border-s1',
          disabled ? 'cursor-not-allowed bg-gray-50' : 'hover:border-gray-300',
          className,
        )}
      >
        <input
          ref={inputRef}
          type="text"
          disabled={disabled}
          value={editing ? text : formatDisplayDate(value)}
          placeholder={placeholder}
          className={cn(
            'min-w-0 flex-1 bg-transparent px-3 py-1.5 text-sm outline-none',
            disabled ? 'cursor-not-allowed text-gray-400' : 'text-mainTextColor',
          )}
          onFocus={() => {
            setEditing(true)
            setText(formatDisplayDate(value))
          }}
          onChange={(e) => setText(e.target.value)}
          onBlur={() => {
            window.setTimeout(() => {
              if (ignoreBlurRef.current) {
                ignoreBlurRef.current = false
                return
              }
              commitTypedInput()
            }, 0)
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              commitTypedInput()
              inputRef.current?.blur()
            }
            if (e.key === 'Escape') {
              setText(formatDisplayDate(value))
              setEditing(false)
              setOpen(false)
              inputRef.current?.blur()
            }
            if (e.key === 'ArrowDown' && !open) {
              e.preventDefault()
              setOpen(true)
            }
          }}
        />
        <button
          type="button"
          disabled={disabled}
          aria-label="Open calendar"
          className={cn(
            'shrink-0 px-2.5 py-1.5 text-bodyText transition',
            disabled ? 'cursor-not-allowed opacity-50' : 'hover:text-s1',
          )}
          onMouseDown={(e) => {
            e.preventDefault()
            ignoreBlurRef.current = true
          }}
          onClick={() => {
            if (disabled) return
            setOpen((prev) => !prev)
          }}
        >
          <Calendar size={15} aria-hidden />
        </button>
      </div>
      {popover ? createPortal(popover, document.body) : null}
    </>
  )
}
