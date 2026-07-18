'use client'

import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import { createPortal } from 'react-dom'
import { getCountryCallingCode, type Country } from 'react-phone-number-input'
import { cn } from '@/lib/utils'

export type CountrySelectOption = {
  value?: Country
  label: string
  divider?: boolean
}

type IconProps = {
  country?: Country
  label?: string
  'aria-hidden'?: boolean
}

export type SearchableCountrySelectProps = {
  name?: string
  'aria-label'?: string
  value?: Country
  options: CountrySelectOption[]
  onChange: (country: Country | undefined) => void
  onFocus: () => void
  onBlur: () => void
  disabled?: boolean
  readOnly?: boolean
  className?: string
  iconComponent: React.ComponentType<IconProps>
  arrowComponent?: React.ComponentType
}

function DefaultArrow() {
  return <div className="PhoneInputCountrySelectArrow" aria-hidden />
}

function dialForCountry(country: Country | undefined): string {
  if (!country) return ''
  try {
    return `+${getCountryCallingCode(country)}`
  } catch {
    return ''
  }
}

function isInside(
  node: Node | null,
  triggerEl: HTMLElement | null,
  panelEl: HTMLElement | null,
): boolean {
  if (!node) return false
  return Boolean(triggerEl?.contains(node) || panelEl?.contains(node))
}

export default function SearchableCountrySelect({
  name,
  'aria-label': ariaLabel,
  value,
  options,
  onChange,
  onFocus,
  onBlur,
  disabled,
  readOnly,
  className,
  iconComponent: Icon,
  arrowComponent: Arrow = DefaultArrow,
}: SearchableCountrySelectProps) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [panelStyle, setPanelStyle] = useState<React.CSSProperties>({})
  const rootRef = useRef<HTMLDivElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)
  const searchRef = useRef<HTMLInputElement>(null)

  const selectedOption = useMemo(() => {
    for (const opt of options) {
      if (opt.divider) continue
      if (opt.value === value || (opt.value === undefined && value === undefined)) {
        return opt
      }
    }
    return undefined
  }, [options, value])

  const selectableOptions = useMemo(
    () => options.filter((o) => !o.divider),
    [options],
  )

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase().replace(/\s+/g, '')
    if (!q) return selectableOptions
    return selectableOptions.filter((o) => {
      const label = (o.label || '').toLowerCase()
      const dial = dialForCountry(o.value).toLowerCase().replace(/\s/g, '')
      const code = (o.value || '').toLowerCase()
      return label.includes(q) || dial.includes(q) || code.includes(q)
    })
  }, [selectableOptions, query])

  const close = useCallback(() => {
    setOpen(false)
    setQuery('')
  }, [])

  const closeAndNotify = useCallback(() => {
    close()
    onBlur()
  }, [close, onBlur])

  const updatePanelPosition = useCallback(() => {
    const el = rootRef.current
    if (!el) return
    const r = el.getBoundingClientRect()
    const maxW = 320
    const width = Math.min(maxW, window.innerWidth - 16)
    let left = r.left
    if (left + width > window.innerWidth - 8) {
      left = window.innerWidth - 8 - width
    }
    left = Math.max(8, left)
    setPanelStyle({
      position: 'fixed',
      top: r.bottom + 4,
      left,
      width,
      zIndex: 9999,
    })
  }, [])

  useLayoutEffect(() => {
    if (!open) return
    updatePanelPosition()
    window.addEventListener('scroll', updatePanelPosition, true)
    window.addEventListener('resize', updatePanelPosition)
    return () => {
      window.removeEventListener('scroll', updatePanelPosition, true)
      window.removeEventListener('resize', updatePanelPosition)
    }
  }, [open, updatePanelPosition])

  useEffect(() => {
    if (!open) return
    const handleFocusIn = (e: FocusEvent) => {
      const t = e.target as Node
      if (isInside(t, rootRef.current, panelRef.current)) return
      close()
      onBlur()
    }
    const handleMouseDown = (e: MouseEvent) => {
      const t = e.target as Node
      if (isInside(t, rootRef.current, panelRef.current)) return
      close()
      onBlur()
    }
    document.addEventListener('focusin', handleFocusIn)
    document.addEventListener('mousedown', handleMouseDown)
    return () => {
      document.removeEventListener('focusin', handleFocusIn)
      document.removeEventListener('mousedown', handleMouseDown)
    }
  }, [open, close, onBlur])

  useEffect(() => {
    if (open) {
      const id = requestAnimationFrame(() => searchRef.current?.focus())
      return () => cancelAnimationFrame(id)
    }
  }, [open])

  const pick = useCallback(
    (opt: CountrySelectOption) => {
      if (opt.divider) return
      onChange(opt.value)
      close()
      onBlur()
    },
    [onChange, onBlur, close],
  )

  const panel =
    open &&
    createPortal(
      <div
        ref={panelRef}
        style={panelStyle}
        className="PhoneInputCountrySearchPanel overflow-hidden"
        role="listbox"
        aria-label={ariaLabel}
      >
        <input
          ref={searchRef}
          type="search"
          className="PhoneInputCountrySearchInput"
          placeholder="Search country or dial code…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Escape') {
              e.stopPropagation()
              closeAndNotify()
            }
          }}
          onClick={(e) => e.stopPropagation()}
        />
        <ul className="PhoneInputCountrySearchList">
          {filtered.length === 0 ? (
            <li className="px-3 py-2 text-sm text-bodyText">No matches</li>
          ) : (
            filtered.map((opt) => {
              const key = opt.divider ? `div-${opt.label}` : String(opt.value ?? 'intl')
              const dial = dialForCountry(opt.value)
              const selected =
                opt.value === value || (opt.value === undefined && value === undefined)
              return (
                <li key={key} role="none">
                  <button
                    type="button"
                    role="option"
                    aria-selected={selected}
                    className={cn(selected && 'bg-softBg2/80')}
                    onMouseDown={(e) => {
                      e.preventDefault()
                      pick(opt)
                    }}
                  >
                    <span className="flex shrink-0 items-center">
                      <Icon country={opt.value} label={opt.label} aria-hidden />
                    </span>
                    <span className="min-w-0 flex-1 truncate">{opt.label}</span>
                    {dial ? (
                      <span className="shrink-0 tabular-nums text-bodyText">{dial}</span>
                    ) : null}
                  </button>
                </li>
              )
            })
          )}
        </ul>
      </div>,
      document.body,
    )

  return (
    <div ref={rootRef} className="PhoneInputCountry PhoneInputCountry--searchable relative">
      <button
        type="button"
        name={name}
        aria-label={ariaLabel}
        aria-haspopup="listbox"
        aria-expanded={open}
        disabled={disabled || readOnly}
        className={cn(
          'PhoneInputCountrySelect PhoneInputCountrySearchTrigger flex shrink-0 items-center gap-1',
          className,
        )}
        onClick={(e) => {
          e.preventDefault()
          if (disabled || readOnly) return
          if (open) {
            closeAndNotify()
          } else {
            setOpen(true)
          }
        }}
        onFocus={onFocus}
      >
        <Icon country={value} label={selectedOption?.label ?? ''} aria-hidden />
        <Arrow />
      </button>
      {panel}
    </div>
  )
}
