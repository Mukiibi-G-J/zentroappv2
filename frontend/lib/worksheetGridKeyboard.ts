import type { PageControlField } from '@/types/page'
import type { DataRecord } from '@/types/pagedata'
import { parseNumericInput } from '@/lib/formatNumber'
import { isCodeField, normalizeDateSaveValue } from '@/lib/listFieldValue'

export interface GridActiveCell {
  systemId: string
  field: string
}

export function isLineFieldEditable(
  field: PageControlField,
  modifyAllowed: boolean,
  controlEditable: boolean,
): boolean {
  return controlEditable && !!field.Editable && modifyAllowed && !field.NoSeriesCode
}

export function moveGridActiveCell(
  active: GridActiveCell,
  direction: 'left' | 'right' | 'up' | 'down',
  fields: PageControlField[],
  lines: DataRecord[],
): GridActiveCell | null {
  const colIdx = fields.findIndex((f) => f.Name === active.field)
  const rowIdx = lines.findIndex((l) => l.SystemId === active.systemId)
  if (colIdx < 0 || rowIdx < 0) return null

  let nextCol = colIdx
  let nextRow = rowIdx

  if (direction === 'left') nextCol = colIdx - 1
  else if (direction === 'right') nextCol = colIdx + 1
  else if (direction === 'up') nextRow = rowIdx - 1
  else if (direction === 'down') nextRow = rowIdx + 1

  if (nextCol < 0 || nextCol >= fields.length || nextRow < 0 || nextRow >= lines.length) {
    return null
  }

  return { systemId: lines[nextRow].SystemId, field: fields[nextCol].Name }
}

export function isPrintableTypingKey(e: KeyboardEvent): boolean {
  return e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey
}

export function isGridTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false
  if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.tagName === 'SELECT') {
    return true
  }
  return !!target.closest('[class*="relation-select"]')
}

export function isRelationSelectTarget(target: EventTarget | null): boolean {
  return target instanceof HTMLElement && !!target.closest('[class*="relation-select"]')
}

export function isRelationMenuOpen(): boolean {
  if (typeof document === 'undefined') return false
  return !!document.querySelector('[class*="relation-select__menu"]')
}

export function closeOpenRelationMenu(): void {
  if (!isRelationMenuOpen()) return
  const active = document.activeElement
  if (active instanceof HTMLElement) {
    active.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'Escape', code: 'Escape', bubbles: true }),
    )
  }
}

export function shouldNavigateFromInput(
  e: KeyboardEvent,
  target: HTMLElement,
  direction: 'left' | 'right',
): boolean {
  if (target.tagName !== 'INPUT' && target.tagName !== 'TEXTAREA') return true
  const input = target as HTMLInputElement
  if (direction === 'left') return (input.selectionStart ?? 0) === 0
  return (input.selectionEnd ?? 0) === (input.value?.length ?? 0)
}

function isTextLikeInput(
  input: HTMLInputElement | HTMLTextAreaElement,
): boolean {
  if (input instanceof HTMLTextAreaElement) return true
  const type = (input.type || 'text').toLowerCase()
  return !['checkbox', 'radio', 'hidden', 'button', 'submit', 'reset', 'file', 'image'].includes(type)
}

function resolveTextInputFromActive(
  active: HTMLElement,
  field: PageControlField,
): HTMLInputElement | HTMLTextAreaElement | null {
  if (active instanceof HTMLInputElement || active instanceof HTMLTextAreaElement) {
    return isTextLikeInput(active) ? active : null
  }

  if (field.FieldType === 'Date' || field.FieldType === 'DateTime') {
    const container = active.closest('div')?.parentElement ?? active.parentElement
    const textInput = container?.querySelector('input[type="text"]')
    if (textInput instanceof HTMLInputElement) return textInput
  }

  const found = active.querySelector(
    'input:not([type="radio"]):not([type="checkbox"]):not([type="hidden"]), textarea',
  )
  if (found instanceof HTMLInputElement || found instanceof HTMLTextAreaElement) {
    return isTextLikeInput(found) ? found : null
  }
  return null
}

/** Read the in-progress value from the focused grid input before navigating away. */
export function readActiveCellCommitValue(
  active: HTMLElement | null,
  field: PageControlField,
): unknown | undefined {
  if (!active) return undefined
  if (field.FieldType === 'Boolean') return undefined

  const input = resolveTextInputFromActive(active, field)
  if (!input) return undefined

  if (field.FieldType === 'Integer' || field.FieldType === 'Decimal') {
    const cleaned = parseNumericInput(input.value)
    return cleaned === '' ? null : cleaned
  }
  if (field.FieldType === 'Date' || field.FieldType === 'DateTime') {
    return normalizeDateSaveValue(input.value)
  }
  if (isCodeField(field)) {
    const trimmed = input.value.trim()
    return trimmed ? trimmed.toUpperCase() : null
  }
  const trimmed = input.value.trim()
  return trimmed === '' ? null : input.value
}
