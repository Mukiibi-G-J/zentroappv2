import type { CSSProperties } from 'react'
import type { DataRecord } from '@/types/pagedata'

export const CHART_OF_ACCOUNTS_SOURCE_TABLE = 'G_LAccount'

/** Rem per indentation level (matches legacy Chart of Accounts UI). */
export const COA_INDENT_REM = 1.25

export function isChartOfAccountsList(sourceTable?: string | null): boolean {
  return sourceTable === CHART_OF_ACCOUNTS_SOURCE_TABLE
}

export function coaIndentLevel(record: DataRecord): number {
  const level = Number(record.indentation ?? 0)
  if (!Number.isFinite(level) || level < 0) return 0
  return level
}

export function coaIndentStyle(record: DataRecord): CSSProperties | undefined {
  const level = coaIndentLevel(record)
  if (level <= 0) return undefined
  return { paddingLeft: `${level * COA_INDENT_REM}rem` }
}

/** @deprecated Use coaIndentStyle */
export function coaIndentPx(record: DataRecord): number {
  const level = coaIndentLevel(record)
  return level * 16
}

/** Bold totals / headings like Business Central. */
export function coaRowTextClass(record: DataRecord): string {
  const type = String(record.accounttype ?? '')
  const level = coaIndentLevel(record)
  const classes: string[] = []

  if (type === 'Total' || type === 'End-Total') {
    classes.push('font-semibold')
  } else if (type === 'Heading' || type === 'Begin-Total') {
    classes.push('font-medium')
  }

  if (
    level === 0
    && (type === 'Heading' || type === 'Begin-Total' || type === 'End-Total')
  ) {
    classes.push('uppercase tracking-wide text-[13px]')
  }

  return classes.join(' ')
}

export function isCoaNameField(fieldName: string): boolean {
  return fieldName === 'name'
}
