'use client'

import { useEffect, useMemo, useState } from 'react'
import axios from 'axios'
import { useQueryClient } from '@tanstack/react-query'
import { pageService } from '@/services/page.service'
import type { PageControlField } from '@/types/page'

export interface RelationOption {
  value: string
  label: string
  caption: string | null
  code?: string | null
  name?: string | null
  quantityPerUnit?: string | null
}

export function mapTableRelationValue(v: {
  Value: string
  Caption: string | null
  Code?: string | null
  Name?: string | null
  QuantityPerUnit?: string | null
}): RelationOption {
  return {
    value: v.Value,
    label: v.Code?.trim() || v.Value,
    caption: v.Caption,
    code: v.Code ?? null,
    name: v.Name ?? null,
    quantityPerUnit: v.QuantityPerUnit ?? null,
  }
}

const EMPTY_RECORD_VALUES: Record<string, unknown> = {}
const EMPTY_OPTIONS: Record<number, RelationOption[]> = {}

function optionsEqual(
  prev: Record<number, RelationOption[]>,
  merged: Record<number, RelationOption[]>,
): boolean {
  const keys = Object.keys(merged)
  if (keys.length !== Object.keys(prev).length) return false
  return keys.every((k) => {
    const id = Number(k)
    const a = prev[id]
    const b = merged[id]
    return (
      a?.length === b?.length &&
      a?.every((opt, i) => opt.value === b[i]?.value && opt.label === b[i]?.label)
    )
  })
}

export function useRelationOptions(
  pageId: number | undefined,
  fields: PageControlField[],
  systemId: string | null = null,
  recordValues: Record<string, unknown> = EMPTY_RECORD_VALUES,
) {
  const queryClient = useQueryClient()

  const relationFieldKey = useMemo(
    () =>
      fields
        .filter((f) => f.Visible && f.HasTableRelation)
        .map((f) => f.PageControlFieldId)
        .join(','),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [fields.map((f) => `${f.PageControlFieldId}:${f.Visible}:${f.HasTableRelation}`).join('|')],
  )

  const relationFields = useMemo(
    () => fields.filter((f) => f.Visible && f.HasTableRelation),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [relationFieldKey],
  )

  const recordValuesKey = useMemo(() => JSON.stringify(recordValues), [recordValues])

  const [options, setOptions] = useState<Record<number, RelationOption[]>>(EMPTY_OPTIONS)

  useEffect(() => {
    if (!pageId || !relationFieldKey) {
      setOptions((prev) => (Object.keys(prev).length === 0 ? prev : EMPTY_OPTIONS))
      return
    }

    const activeIds = new Set(
      relationFieldKey.split(',').filter(Boolean).map((id) => Number(id)),
    )

    // Drop cached options for field ids no longer on the page (e.g. after seed_pages).
    setOptions((prev) => {
      const trimmed: Record<number, RelationOption[]> = {}
      for (const [key, value] of Object.entries(prev)) {
        const id = Number(key)
        if (activeIds.has(id)) trimmed[id] = value
      }
      return Object.keys(trimmed).length === Object.keys(prev).length ? prev : trimmed
    })

    let cancelled = false
    ;(async () => {
      const next: Record<number, RelationOption[]> = {}
      let stalePageMetadata = false

      for (const field of relationFields) {
        try {
          const values = await pageService.fetchTableRelations(
            pageId,
            field.PageControlId,
            field.PageControlFieldId,
            systemId,
            recordValues,
          )
          if (cancelled) return
          next[field.PageControlFieldId] = values.map(mapTableRelationValue)
        } catch (err) {
          if (cancelled) return
          const status = axios.isAxiosError(err) ? err.response?.status : undefined
          if (status === 404) {
            stalePageMetadata = true
            continue
          }
          next[field.PageControlFieldId] = []
        }
      }

      if (stalePageMetadata) {
        await queryClient.invalidateQueries({ queryKey: ['page', pageId] })
        await queryClient.invalidateQueries({ queryKey: ['pages'] })
      }

      if (!cancelled && Object.keys(next).length > 0) {
        setOptions((prev) => {
          const merged = { ...prev, ...next }
          return optionsEqual(prev, merged) ? prev : merged
        })
      }
    })()

    return () => {
      cancelled = true
    }
  }, [pageId, relationFieldKey, relationFields, systemId, recordValuesKey, queryClient])

  return options
}
