import type { CSSProperties } from 'react'
import type { DataRecord } from '@/types/pagedata'

export const ITEM_CATEGORY_SOURCE_TABLE = 'ItemCategory'

/** Rem per hierarchy level (Business Central–style indent). */
export const ITEM_CATEGORY_INDENT_REM = 1.25

export function isItemCategoryList(sourceTable?: string | null): boolean {
  return sourceTable === ITEM_CATEGORY_SOURCE_TABLE
}

export function itemCategoryIndentLevel(record: DataRecord | { indentation?: unknown }): number {
  const level = Number(record.indentation ?? 0)
  if (!Number.isFinite(level) || level < 0) return 0
  return level
}

export function itemCategoryIndentStyle(
  record: DataRecord | { indentation?: unknown },
): CSSProperties | undefined {
  const level = itemCategoryIndentLevel(record)
  if (level <= 0) return undefined
  return { paddingLeft: `${level * ITEM_CATEGORY_INDENT_REM}rem` }
}

/** Parent codes bold; child codes teal like BC category picker. */
export function itemCategoryCodeClass(record: DataRecord | { indentation?: unknown }): string {
  const level = itemCategoryIndentLevel(record)
  if (level <= 0) return 'font-semibold uppercase tracking-wide text-mainTextColor'
  return 'font-medium uppercase tracking-wide text-s1'
}
