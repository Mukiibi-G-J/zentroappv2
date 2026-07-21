'use client'

import { useEffect, useRef, useState } from 'react'
import DatePicker from '@/components/ui/DatePicker'
import {
  formatDecimalDisplay,
  formatIntegerDisplay,
  formatNumericFieldDisplay,
  parseNumericInput,
} from '@/lib/formatNumber'
import {
  formatDisplayDate,
  parseIsoDate,
  parseTypedDate,
  toIsoDate,
} from '@/lib/dateFormat'
import type { PageControlField } from '@/types/page'
import { isCodeField, normalizeListFieldInputValue } from '@/lib/listFieldValue'
import BooleanToggle from '@/components/ui/BooleanToggle'
import YesNoSelect from '@/components/ui/YesNoSelect'
import { cn } from '@/lib/utils'

interface Props {
  field: PageControlField
  value: unknown
  disabled?: boolean
  className?: string
  singleLine?: boolean
  compact?: boolean
  /** List grid inline edit — field may be metadata read-only (drill-down PK) but still editable here. */
  listInlineEdit?: boolean
  autoFocus?: boolean
  initialInput?: string
  onChange?: (value: unknown) => void
  onBlur?: (value: unknown) => void
  onKeyDown?: (e: React.KeyboardEvent<HTMLInputElement>) => void
}

export default function DynamicField({
  field,
  value,
  disabled,
  className,
  singleLine,
  compact = false,
  listInlineEdit = false,
  autoFocus = false,
  initialInput,
  onChange,
  onBlur,
  onKeyDown,
}: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const isFocusedRef = useRef(false)
  const pendingSelectValueRef = useRef<string | null>(null)
  const initialInputAppliedRef = useRef(false)
  const [local, setLocal] = useState(value ?? '')
  const [numericFocused, setNumericFocused] = useState(false)

  useEffect(() => {
    if (isFocusedRef.current) return
    const normalized = normalizeListFieldInputValue(field, value ?? '')
    if (pendingSelectValueRef.current !== null) {
      if (String(normalized) === pendingSelectValueRef.current) {
        pendingSelectValueRef.current = null
      } else {
        return
      }
    }
    setLocal((prev) => {
      const prevStr = prev === null || prev === undefined ? '' : String(prev)
      const nextStr = String(normalized)
      return prevStr === nextStr ? prev : normalized
    })
  }, [value, field.FieldType, field.Name])

  useEffect(() => {
    if (!autoFocus) {
      initialInputAppliedRef.current = false
      return
    }
    const el = inputRef.current
    if (!el) return
    el.focus()
    if (initialInputAppliedRef.current) return
    initialInputAppliedRef.current = true
    if (initialInput != null && initialInput !== '') {
      setLocal(initialInput)
      requestAnimationFrame(() => {
        el.setSelectionRange(initialInput.length, initialInput.length)
      })
    } else {
      el.select()
    }
  }, [autoFocus, initialInput])

  const formatNumericLocal = (raw: unknown) => {
    if (raw === '' || raw == null) return ''
    if (field.FieldType === 'Decimal') return formatDecimalDisplay(raw)
    if (field.FieldType === 'Integer') return formatIntegerDisplay(raw)
    return String(raw)
  }

  const fieldEditable = listInlineEdit || field.Editable
  const isDisabled = disabled || !fieldEditable

  const base = compact
    ? 'w-full min-w-0 px-2 py-1 text-sm text-mainTextColor border border-gray-200 rounded bg-white ' +
      'focus:outline-none focus:ring-2 focus:ring-s1/30 focus:border-s1 disabled:bg-gray-50 disabled:text-gray-400 transition'
    : 'w-full px-3 py-1.5 text-sm text-mainTextColor border border-gray-200 rounded-lg bg-white ' +
      'focus:outline-none focus:ring-2 focus:ring-s1/30 focus:border-s1 disabled:bg-gray-50 disabled:text-gray-400 transition'

  const handleBlur = () => {
    isFocusedRef.current = false
    let saved: unknown = isCodeField(field) && typeof local === 'string'
      ? local.toUpperCase().trim()
      : local
    if (typeof saved === 'string' && saved.trim() === '') saved = null
    onBlur?.(saved)
  }

  const handleFocus = () => {
    isFocusedRef.current = true
  }

  const codeInputClass = isCodeField(field) ? 'font-mono uppercase' : ''

  // Read-only display for non-editable text / code fields
  if (!fieldEditable && (field.FieldType === 'Text' || field.FieldType === 'Code')) {
    return (
      <div className={`${base} bg-gray-50 font-medium text-mainTextColor ${className ?? ''}`}>
        {String(local || '—')}
      </div>
    )
  }

  // Read-only display for non-editable numbers
  if (!fieldEditable && (field.FieldType === 'Decimal' || field.FieldType === 'Integer')) {
    return (
      <div className={`${base} bg-gray-50 font-medium text-mainTextColor text-right tabular-nums ${className ?? ''}`}>
        {formatNumericFieldDisplay(local, field.FieldType)}
      </div>
    )
  }

  // Boolean — dropdown in line grids; toggle on card-style forms
  if (field.FieldType === 'Boolean') {
    if (!fieldEditable || isDisabled) {
      return (
        <div className={`${base} bg-gray-50 font-medium text-mainTextColor ${className ?? ''}`}>
          {local ? 'Yes' : 'No'}
        </div>
      )
    }
    if (singleLine) {
      return (
        <YesNoSelect
          value={local}
          ariaLabel={field.Caption}
          className={className}
          onChange={(checked) => {
            setLocal(checked)
            onChange?.(checked)
            onBlur?.(checked)
          }}
        />
      )
    }
    return (
      <BooleanToggle
        checked={!!local}
        disabled={isDisabled}
        aria-label={field.Caption}
        className={className}
        onChange={(checked) => {
          setLocal(checked)
          onChange?.(checked)
          onBlur?.(checked)
        }}
      />
    )
  }

  // Enum / Option
  if ((field.FieldType === 'Enum' || field.FieldType === 'Option') && field.EnumValues) {
    const opts = field.EnumValues.split(',').map((v) => v.trim())
    const formatLabel = (opt: string) =>
      opt.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
    return (
      <select
        value={String(local)}
        disabled={isDisabled}
        className={`${base} ${className ?? ''}`}
        onChange={(e) => {
          const next = e.target.value
          pendingSelectValueRef.current = next
          setLocal(next)
          onChange?.(next)
          onBlur?.(next)
        }}
      >
        <option value="">Select {field.Caption}</option>
        {opts.map((opt) => (
          <option key={opt} value={opt}>{formatLabel(opt)}</option>
        ))}
      </select>
    )
  }

  // Date / DateTime
  if (field.FieldType === 'Date') {
    const raw = local ? String(local).trim() : ''
    const parsed = raw ? (parseIsoDate(raw) ?? parseTypedDate(raw)) : null
    const iso = parsed ? toIsoDate(parsed) : ''
    if (!fieldEditable) {
      return (
        <div className={`${base} bg-gray-50 font-medium text-mainTextColor ${className ?? ''}`}>
          {formatDisplayDate(iso) || '—'}
        </div>
      )
    }
    return (
      <DatePicker
        value={iso}
        disabled={isDisabled}
        placeholder={`Select ${field.Caption.toLowerCase()}…`}
        className={className}
        onChange={(next) => {
          setLocal(next)
          onChange?.(next)
          onBlur?.(next || null)
        }}
      />
    )
  }

  if (field.FieldType === 'DateTime') {
    const raw = String(local || '')
    const datePart = raw.slice(0, 10)
    const timePart = raw.includes('T') ? raw.slice(11, 16) : ''
    if (!fieldEditable) {
      return (
        <div className={`${base} bg-gray-50 font-medium text-mainTextColor ${className ?? ''}`}>
          {formatDisplayDate(datePart) || '—'}
          {timePart ? ` ${timePart}` : ''}
        </div>
      )
    }
    return (
      <div className={cn('flex gap-2', className)}>
        <DatePicker
          value={datePart}
          disabled={isDisabled}
          placeholder={`Select ${field.Caption.toLowerCase()}…`}
          className="min-w-0 flex-1"
          onChange={(next) => {
            const combined = next ? `${next}T${timePart || '00:00'}` : ''
            setLocal(combined)
            onChange?.(combined)
            onBlur?.(combined || null)
          }}
        />
        <input
          type="time"
          value={timePart}
          disabled={isDisabled}
          className={`${base} w-30 shrink-0 px-2 tabular-nums`}
          onChange={(e) => {
            const combined = datePart ? `${datePart}T${e.target.value || '00:00'}` : ''
            setLocal(combined)
            onChange?.(combined)
          }}
          onBlur={handleBlur}
        />
      </div>
    )
  }

  // Numbers — right-aligned, formatted with thousands separators when not editing
  if (field.FieldType === 'Integer' || field.FieldType === 'Decimal') {
    if (isDisabled) {
      return (
        <div className={`${base} bg-gray-50 font-medium text-mainTextColor text-right tabular-nums ${className ?? ''}`}>
          {formatNumericFieldDisplay(local, field.FieldType)}
        </div>
      )
    }
    const displayValue = numericFocused ? String(local) : formatNumericLocal(local)
    return (
      <input
        ref={inputRef}
        type="text"
        inputMode={field.FieldType === 'Decimal' ? 'decimal' : 'numeric'}
        value={displayValue}
        disabled={isDisabled}
        autoComplete="off"
        className={`${base} text-right tabular-nums ${className ?? ''}`}
        onFocus={() => {
          handleFocus()
          setNumericFocused(true)
          setLocal(parseNumericInput(String(local)))
        }}
        onChange={(e) => {
          const next = e.target.value
          setLocal(next)
          onChange?.(parseNumericInput(next))
        }}
        onBlur={() => {
          setNumericFocused(false)
          const cleaned = parseNumericInput(String(local))
          setLocal(cleaned)
          onBlur?.(cleaned === '' ? null : cleaned)
        }}
        onKeyDown={onKeyDown}
      />
    )
  }

  // Multiline textarea for note / remark / comment fields (skipped in table/single-line contexts)
  if (
    !singleLine &&
    field.FieldType === 'Text' &&
    field.Caption?.toLowerCase().match(/\b(note|remark|comment)s?\b/)
  ) {
    return (
      <textarea
        rows={3}
        value={String(local)}
        disabled={isDisabled}
        placeholder={field.Tooltip ?? `Enter ${field.Caption.toLowerCase()}…`}
        className={`${base} resize-none ${className ?? ''}`}
        onChange={(e) => { setLocal(e.target.value); onChange?.(e.target.value) }}
        onBlur={handleBlur}
      />
    )
  }

  return (
    <input
      ref={inputRef}
      type="text"
      value={String(local)}
      disabled={isDisabled}
      autoComplete="off"
      autoCorrect="off"
      autoCapitalize="off"
      spellCheck={false}
      placeholder={isDisabled ? '' : (field.Tooltip ?? `Enter ${field.Caption.toLowerCase()}…`)}
      className={`${base} ${codeInputClass} ${className ?? ''}`}
      onFocus={handleFocus}
      onChange={(e) => {
        const next = isCodeField(field) ? e.target.value.toUpperCase() : e.target.value
        setLocal(next)
        onChange?.(next)
      }}
      onBlur={handleBlur}
      onKeyDown={onKeyDown}
    />
  )
}
