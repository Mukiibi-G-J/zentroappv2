'use client'

import { useCallback, useMemo } from 'react'
import { usePathname, useRouter, useSearchParams } from 'next/navigation'
import type { PageControlField } from '@/types/page'
import {
  COLUMN_FILTER_PREFIX,
  LIST_ORDER_PARAM,
  LIST_SORT_PARAM,
  parseColumnFilters,
  parseListSort,
  serializeFilterValue,
  type ListSortOrder,
} from '@/lib/listColumnFilters'

export function useListColumnState(fields: PageControlField[]) {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()

  const allowedFieldNames = useMemo(
    () => new Set(fields.map((f) => f.Name)),
    [fields],
  )

  const columnFilters = useMemo(() => {
    const raw = parseColumnFilters(searchParams)
    const filtered: Record<string, string> = {}
    for (const [key, value] of Object.entries(raw)) {
      if (allowedFieldNames.has(key)) filtered[key] = value
    }
    return filtered
  }, [searchParams, allowedFieldNames])

  const sort = useMemo(() => {
    const parsed = parseListSort(searchParams)
    if (!parsed || !allowedFieldNames.has(parsed.field)) return null
    return parsed
  }, [searchParams, allowedFieldNames])

  const pushParams = useCallback(
    (mutate: (params: URLSearchParams) => void) => {
      const params = new URLSearchParams(searchParams.toString())
      mutate(params)
      const qs = params.toString()
      router.push(qs ? `${pathname}?${qs}` : pathname)
    },
    [pathname, router, searchParams],
  )

  const setSort = useCallback(
    (field: string, order: ListSortOrder) => {
      if (!allowedFieldNames.has(field)) return
      pushParams((params) => {
        params.set(LIST_SORT_PARAM, field)
        params.set(LIST_ORDER_PARAM, order)
      })
    },
    [allowedFieldNames, pushParams],
  )

  const setColumnFilter = useCallback(
    (field: PageControlField, value: unknown) => {
      const serialized = serializeFilterValue(field, value)
      if (!serialized) return
      pushParams((params) => {
        params.set(`${COLUMN_FILTER_PREFIX}${field.Name}`, serialized)
      })
    },
    [pushParams],
  )

  const clearColumnFilter = useCallback(
    (fieldName: string) => {
      pushParams((params) => {
        params.delete(`${COLUMN_FILTER_PREFIX}${fieldName}`)
      })
    },
    [pushParams],
  )

  const clearAllColumnState = useCallback(() => {
    pushParams((params) => {
      for (const key of [...params.keys()]) {
        if (key.startsWith(COLUMN_FILTER_PREFIX)) params.delete(key)
      }
      params.delete(LIST_SORT_PARAM)
      params.delete(LIST_ORDER_PARAM)
    })
  }, [pushParams])

  const getFieldFilterValue = useCallback(
    (fieldName: string) => columnFilters[fieldName] ?? null,
    [columnFilters],
  )

  const hasColumnState = Object.keys(columnFilters).length > 0 || sort !== null

  return {
    columnFilters,
    sort,
    setSort,
    setColumnFilter,
    clearColumnFilter,
    clearAllColumnState,
    getFieldFilterValue,
    hasColumnState,
  }
}
