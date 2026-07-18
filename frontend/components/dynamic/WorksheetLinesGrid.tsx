'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { Check, CircleX } from 'lucide-react'
import { cn } from '@/lib/utils'
import { getFieldCaption } from '@/lib/fieldCaption'
import { formatDecimalDisplay } from '@/lib/formatNumber'
import { getRecordFieldValue } from '@/lib/recordFieldValue'
import {
  amountToApplyInputValue,
  appliesToIdDisplay,
  getAmountToApplyForRow,
  isRowMarkedForPayment,
  isWorksheetVirtualField,
  parseAmountInput,
  rowRemainingAmount,
} from '@/lib/worksheetControls'
import { worksheetFrozenFieldProps } from '@/lib/worksheetColumns'
import type { Page, PageControlField } from '@/types/page'
import type { DataRecord } from '@/types/pagedata'

const stickySelectBase =
  'w-10 min-w-10 shrink-0 px-2 text-center sticky left-0 z-20 overflow-visible shadow-[2px_0_4px_-1px_rgba(0,0,0,0.08)]'

function stickySelectCellClass(isSelected: boolean) {
  return cn(
    stickySelectBase,
    'py-2',
    isSelected ? 'bg-[#eef5f5]' : 'bg-white group-hover:bg-gray-50',
  )
}

function formatCellValue(value: unknown, field: PageControlField): string {
  if (value === null || value === undefined || value === '') return '—'
  if (field.FieldType === 'Boolean') return value ? 'Yes' : 'No'
  if (field.FieldType === 'Date' && value) {
    try {
      return new Date(String(value)).toLocaleDateString()
    } catch {
      return String(value)
    }
  }
  if (field.FieldType === 'Decimal' || field.FieldType === 'Integer') {
    const n = Number(value)
    if (!Number.isNaN(n)) {
      return n.toLocaleString(undefined, {
        minimumFractionDigits: field.FieldType === 'Decimal' ? 2 : 0,
        maximumFractionDigits: field.FieldType === 'Decimal' ? 2 : 0,
      })
    }
  }
  return String(value)
}

function isDocumentHighlightField(field: PageControlField): boolean {
  return field.Name === 'document_type' || field.Name === 'document_no'
}

const APPLY_EDIT_FIELDS = ['applies_to_id', 'amount_to_apply'] as const
type ApplyEditField = (typeof APPLY_EDIT_FIELDS)[number]

function focusApplyGridInput(systemId: string, fieldName: ApplyEditField) {
  const el = document.querySelector(
    `[data-apply-grid-row="${systemId}"][data-apply-grid-field="${fieldName}"]`,
  ) as HTMLInputElement | null
  el?.focus({ preventScroll: true })
}

function rowHasApplyInputs(
  row: DataRecord,
  applySession: WorksheetApplySession,
): boolean {
  return isRowMarkedForPayment(row, applySession.appliesToOverrides, applySession.paymentAppliesToId)
}

export interface WorksheetApplySession {
  paymentAppliesToId: string
  appliesToOverrides: Record<string, string>
  amountToApplyBySystemId: Record<string, string>
  amountToApplyErrors?: Record<string, string>
  onAppliesToIdChange: (systemId: string, value: string) => void
  onAppliesToIdBlur: (row: DataRecord, value: string) => void
  onAmountChange: (systemId: string, value: string) => void
  onAmountBlur: (systemId: string, raw: string) => void
  saving?: boolean
}

interface Props {
  page: Page
  fields: PageControlField[]
  records: DataRecord[]
  selectedSystemId: string | null
  onSelectRow: (systemId: string) => void
  applySession?: WorksheetApplySession | null
}

export default function WorksheetLinesGrid({
  page,
  fields,
  records,
  selectedSystemId,
  onSelectRow,
  applySession,
}: Props) {
  const [focusedAmountSystemId, setFocusedAmountSystemId] = useState<string | null>(null)
  const gridRef = useRef<HTMLDivElement>(null)

  const navigateApplyCell = useCallback(
    (
      direction: 'left' | 'right' | 'up' | 'down',
      currentRowId: string,
      currentField: ApplyEditField,
    ) => {
      if (!applySession) return
      const rowIdx = records.findIndex((row) => row.SystemId === currentRowId)
      if (rowIdx < 0) return

      const colIdx = APPLY_EDIT_FIELDS.indexOf(currentField)
      let nextRow = rowIdx
      let nextCol = colIdx

      if (direction === 'left') nextCol -= 1
      else if (direction === 'right') nextCol += 1
      else if (direction === 'up') nextRow -= 1
      else if (direction === 'down') nextRow += 1

      while (nextRow >= 0 && nextRow < records.length) {
        while (nextCol >= 0 && nextCol < APPLY_EDIT_FIELDS.length) {
          const row = records[nextRow]
          if (rowHasApplyInputs(row, applySession)) {
            focusApplyGridInput(row.SystemId, APPLY_EDIT_FIELDS[nextCol])
            return
          }
          if (direction === 'left' || direction === 'right') {
            nextCol += direction === 'right' ? 1 : -1
          } else {
            break
          }
        }
        if (direction === 'up' || direction === 'down') {
          nextRow += direction === 'down' ? 1 : -1
          nextCol = direction === 'down' ? 0 : APPLY_EDIT_FIELDS.length - 1
        } else {
          break
        }
      }
    },
    [applySession, records],
  )

  useEffect(() => {
    if (!applySession) return

    const onKeyDown = (e: KeyboardEvent) => {
      const target = e.target
      if (!(target instanceof HTMLInputElement)) return
      if (!gridRef.current?.contains(target)) return
      const rowId = target.dataset.applyGridRow
      const fieldName = target.dataset.applyGridField as ApplyEditField | undefined
      if (!rowId || !fieldName || !APPLY_EDIT_FIELDS.includes(fieldName)) return

      const direction =
        e.key === 'ArrowLeft' ? 'left'
        : e.key === 'ArrowRight' ? 'right'
        : e.key === 'ArrowUp' ? 'up'
        : e.key === 'ArrowDown' ? 'down'
        : null
      if (!direction) return

      if (
        (direction === 'left' || direction === 'right')
        && target.selectionStart != null
        && target.selectionEnd != null
      ) {
        if (direction === 'left' && target.selectionStart > 0) return
        if (direction === 'right' && target.selectionEnd < target.value.length) return
      }

      e.preventDefault()
      navigateApplyCell(direction, rowId, fieldName)
    }

    document.addEventListener('keydown', onKeyDown, true)
    return () => document.removeEventListener('keydown', onKeyDown, true)
  }, [applySession, navigateApplyCell])

  function formatAmountInputDisplay(raw: string, isFocused: boolean): string {
    if (isFocused || raw === '') return raw
    const parsed = parseAmountInput(raw)
    if (parsed === null) return raw
    return formatDecimalDisplay(parsed)
  }

  return (
    <div ref={gridRef} tabIndex={-1} className="outline-none">
    <table className="min-w-max w-full text-sm">
      <thead className="sticky top-0 z-30">
        <tr className="border-b border-gray-200 bg-gray-50">
          <th className={cn(stickySelectBase, 'py-2.5 z-50 bg-gray-50')} />
          {fields.map((field, fi) => {
            const frozen = worksheetFrozenFieldProps(fields, fi, 'header')
            return (
              <th key={field.PageControlFieldId} className={frozen.className} style={frozen.style}>
                {getFieldCaption(field, page)}
              </th>
            )
          })}
        </tr>
      </thead>
      <tbody className="divide-y divide-gray-100 [&_td]:overflow-visible">
        {records.map((row) => {
          const selected = selectedSystemId === row.SystemId
          const marked = applySession
            ? isRowMarkedForPayment(row, applySession.appliesToOverrides, applySession.paymentAppliesToId)
            : false
          return (
            <tr
              key={row.SystemId}
              className={cn('group cursor-pointer transition', selected ? 'bg-s1/10' : 'hover:bg-gray-50')}
              onClick={() => onSelectRow(row.SystemId)}
            >
              <td className={stickySelectCellClass(selected)}>
                {selected ? <Check size={14} className="mx-auto text-s1" /> : null}
              </td>
              {fields.map((field, fi) => {
                const frozen = worksheetFrozenFieldProps(fields, fi, 'body', {
                  isSelected: selected,
                })
                const numericAlign = field.FieldType === 'Decimal' || field.FieldType === 'Integer'
                const highlight = isDocumentHighlightField(field)

                if (applySession && field.Name === 'applies_to_id') {
                  return (
                    <td
                      key={field.PageControlFieldId}
                      className={frozen.className}
                      style={frozen.style}
                      onClick={(e) => e.stopPropagation()}
                    >
                      <input
                        type="text"
                        data-apply-grid-row={row.SystemId}
                        data-apply-grid-field="applies_to_id"
                        value={appliesToIdDisplay(row, applySession.appliesToOverrides)}
                        disabled={applySession.saving}
                        onChange={(e) => applySession.onAppliesToIdChange(row.SystemId, e.target.value)}
                        onBlur={(e) => applySession.onAppliesToIdBlur(row, e.target.value)}
                        className={cn(
                          'h-8 w-full rounded border bg-white px-2 text-sm tabular-nums text-mainTextColor',
                          selected ? 'border-s1 ring-1 ring-s1/30' : 'border-gray-200',
                        )}
                        aria-label={getFieldCaption(field, page)}
                      />
                    </td>
                  )
                }

                if (applySession && field.Name === 'appln_remaining_amount') {
                  return (
                    <td
                      key={field.PageControlFieldId}
                      className={cn(frozen.className, 'text-right tabular-nums text-blue-700')}
                      style={frozen.style}
                    >
                      {formatCellValue(rowRemainingAmount(row), field)}
                    </td>
                  )
                }

                if (applySession && field.Name === 'amount_to_apply') {
                  const rawInput = amountToApplyInputValue(
                    row,
                    applySession.appliesToOverrides,
                    applySession.paymentAppliesToId,
                    applySession.amountToApplyBySystemId,
                  )
                  const amountFocused = focusedAmountSystemId === row.SystemId
                  const inputValue = formatAmountInputDisplay(rawInput, amountFocused)
                  const amountError = applySession.amountToApplyErrors?.[row.SystemId]
                  return (
                    <td
                      key={field.PageControlFieldId}
                      className={cn(frozen.className, 'text-right tabular-nums')}
                      style={frozen.style}
                      onClick={(e) => e.stopPropagation()}
                    >
                      {marked ? (
                        <div className="relative flex items-center gap-1">
                          {amountError ? (
                            <span
                              className="shrink-0 text-red-600"
                              title={amountError}
                              aria-label={amountError}
                            >
                              <CircleX size={16} aria-hidden />
                            </span>
                          ) : null}
                          <input
                            type="text"
                            inputMode="decimal"
                            data-apply-grid-row={row.SystemId}
                            data-apply-grid-field="amount_to_apply"
                            value={inputValue}
                            disabled={applySession.saving}
                            onFocus={() => setFocusedAmountSystemId(row.SystemId)}
                            onChange={(e) => applySession.onAmountChange(row.SystemId, e.target.value)}
                            onBlur={(e) => {
                              applySession.onAmountBlur(row.SystemId, e.target.value)
                              setFocusedAmountSystemId((id) => (id === row.SystemId ? null : id))
                            }}
                            className={cn(
                              'h-8 min-w-0 flex-1 rounded border bg-white px-2 text-right text-sm tabular-nums text-mainTextColor',
                              amountError
                                ? 'border-red-500 ring-1 ring-red-200'
                                : selected
                                  ? 'border-s1 ring-1 ring-s1/30'
                                  : 'border-gray-200',
                            )}
                            aria-label={getFieldCaption(field, page)}
                            aria-invalid={amountError ? true : undefined}
                            title={amountError ?? undefined}
                          />
                        </div>
                      ) : (
                        <span className="text-bodyText">—</span>
                      )}
                    </td>
                  )
                }

                if (applySession && field.Name === 'appln_amount_to_apply') {
                  const amt = marked
                    ? getAmountToApplyForRow(
                      row,
                      applySession.appliesToOverrides,
                      applySession.paymentAppliesToId,
                      applySession.amountToApplyBySystemId,
                    )
                    : 0
                  return (
                    <td
                      key={field.PageControlFieldId}
                      className={cn(frozen.className, 'text-right tabular-nums text-blue-700')}
                      style={frozen.style}
                    >
                      {marked ? formatCellValue(amt, field) : '—'}
                    </td>
                  )
                }

                if (applySession && isWorksheetVirtualField(field)) {
                  return (
                    <td key={field.PageControlFieldId} className={frozen.className} style={frozen.style}>
                      —
                    </td>
                  )
                }

                const value = getRecordFieldValue(row, field.Name)
                return (
                  <td
                    key={field.PageControlFieldId}
                    className={cn(
                      frozen.className,
                      highlight && 'italic text-red-700',
                      numericAlign && 'text-right tabular-nums',
                      !numericAlign && 'whitespace-nowrap',
                      field.Name === 'remaining_amount' && 'text-blue-700',
                    )}
                    style={frozen.style}
                  >
                    {formatCellValue(value, field)}
                  </td>
                )
              })}
            </tr>
          )
        })}
      </tbody>
    </table>
    </div>
  )
}
