import type { CSSProperties } from 'react'
import { cn } from '@/lib/utils'
import type { PageControlField } from '@/types/page'

/** Width of the row-selector column (matches w-10). */
export const SELECTOR_COL_PX = 40

const COL_WIDTH_PX: Record<string, number> = {
  Boolean: 112,
  Integer: 142,
  Decimal: 172,
  Date: 162,
  DateTime: 162,
  Option: 128,
  Enum: 128,
}

const COL_MIN_WIDTH_CLASS: Record<string, string> = {
  Boolean: 'min-w-[80px]',
  Integer: 'min-w-[110px]',
  Decimal: 'min-w-[140px]',
  Date: 'min-w-[130px]',
  DateTime: 'min-w-[130px]',
  Option: 'min-w-[96px]',
  Enum: 'min-w-[96px]',
}

/** BC-style line Type (Item / Resource / G/L Account) — keep compact. */
const LINE_TYPE_COL_PX = 96

export function colWidthPx(field: PageControlField): number {
  if (
    field.Name === 'type'
    && (field.FieldType === 'Option' || field.FieldType === 'Enum')
  ) {
    return LINE_TYPE_COL_PX
  }
  return COL_WIDTH_PX[field.FieldType] ?? 192
}

export function colMinWidth(field: PageControlField): string {
  if (
    field.Name === 'type'
    && (field.FieldType === 'Option' || field.FieldType === 'Enum')
  ) {
    return 'min-w-[72px]'
  }
  return COL_MIN_WIDTH_CLASS[field.FieldType] ?? 'min-w-[160px]'
}

function colWidthClass(field: PageControlField): string {
  return colMinWidth(field)
}

function colWidthStyle(field: PageControlField): CSSProperties {
  const width = colWidthPx(field)
  return { width, minWidth: width, maxWidth: width }
}

/** True when field is in the consecutive frozen prefix (left to right). */
export function isConsecutiveFrozen(visibleFields: PageControlField[], index: number): boolean {
  if (!visibleFields[index]?.FreezeColumn) return false
  for (let i = 0; i < index; i++) {
    if (!visibleFields[i].FreezeColumn) return false
  }
  return true
}

export function lastConsecutiveFrozenIndex(visibleFields: PageControlField[]): number {
  let last = -1
  for (let i = 0; i < visibleFields.length; i++) {
    if (visibleFields[i].FreezeColumn) last = i
    else break
  }
  return last
}

export function frozenLeftOffset(
  visibleFields: PageControlField[],
  fieldIndex: number,
  selectorColPx = SELECTOR_COL_PX,
): number {
  let left = selectorColPx
  for (let i = 0; i < fieldIndex; i++) {
    if (isConsecutiveFrozen(visibleFields, i)) {
      left += colWidthPx(visibleFields[i])
    }
  }
  return left
}

type FrozenVariant = 'header' | 'body' | 'footer' | 'skeleton'

export function worksheetFrozenFieldProps(
  visibleFields: PageControlField[],
  fieldIndex: number,
  variant: FrozenVariant,
  options?: { isSelected?: boolean; extraClass?: string; selectorColPx?: number },
): { className: string; style?: CSSProperties } {
  const field = visibleFields[fieldIndex]
  const selectorColPx = options?.selectorColPx ?? SELECTOR_COL_PX

  if (!isConsecutiveFrozen(visibleFields, fieldIndex)) {
    return {
      className: cn(
        'px-4',
        colMinWidth(field),
        variant === 'header' &&
          'py-3 text-left text-xs font-medium text-bodyText uppercase tracking-wide whitespace-nowrap bg-gray-50',
        variant === 'body' && 'py-3',
        variant === 'skeleton' && 'py-3',
        options?.extraClass,
      ),
    }
  }

  const left = frozenLeftOffset(visibleFields, fieldIndex, selectorColPx)
  const zBase = variant === 'header' ? 50 : 20
  const zIndex = zBase + fieldIndex
  const isLast = fieldIndex === lastConsecutiveFrozenIndex(visibleFields)

  const bg =
    variant === 'header' || variant === 'footer' || variant === 'skeleton'
      ? 'bg-gray-50'
      : options?.isSelected
        ? 'bg-[#eef5f5] group-hover:bg-[#eef5f5]'
        : 'bg-white group-hover:bg-gray-50'

  return {
    className: cn(
      'px-4 sticky shrink-0 overflow-visible',
      colWidthClass(field),
      bg,
      isLast && 'shadow-[2px_0_4px_-1px_rgba(0,0,0,0.08)]',
      variant === 'header' &&
        'py-3 text-left text-xs font-medium text-bodyText uppercase tracking-wide whitespace-nowrap',
      variant === 'body' && 'py-3',
      variant === 'footer' && 'py-3',
      variant === 'skeleton' && 'py-3',
      options?.extraClass,
    ),
    style: { ...colWidthStyle(field), left, zIndex },
  }
}

/** Frozen columns on list pages (no row-selector offset). */
export function listFrozenFieldProps(
  visibleFields: PageControlField[],
  fieldIndex: number,
  variant: FrozenVariant,
  options?: { extraClass?: string },
) {
  return worksheetFrozenFieldProps(visibleFields, fieldIndex, variant, {
    ...options,
    selectorColPx: 0,
  })
}
