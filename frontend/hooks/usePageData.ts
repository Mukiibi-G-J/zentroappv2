'use client'

import { useQuery, useInfiniteQuery, useMutation, useQueryClient, type InfiniteData } from '@tanstack/react-query'
import { pageDataService } from '@/services/pagedata.service'
import { useBranchCacheKey } from '@/hooks/useBranchCacheKey'
import type { PageControlField } from '@/types/page'
import type { DataRecord } from '@/types/pagedata'

export function removeRecordFromPageDataCaches(
  qc: ReturnType<typeof useQueryClient>,
  pageId: number,
  systemId: string,
) {
  qc.setQueriesData<DataRecord[]>(
    { queryKey: ['pagedata', pageId] },
    (old) => {
      if (!Array.isArray(old)) return old
      const next = old.filter((row) => row.SystemId !== systemId)
      return next.length === old.length ? old : next
    },
  )

  qc.setQueriesData<InfiniteData<DataRecord[]>>(
    { queryKey: ['pagedata', 'infinite', pageId] },
    (old) => {
      if (!old?.pages) return old
      let changed = false
      const pages = old.pages.map((page) => {
        const next = page.filter((row) => row.SystemId !== systemId)
        if (next.length !== page.length) changed = true
        return next
      })
      return changed ? { ...old, pages } : old
    },
  )
}

export function usePageDataList(
  pageId: number,
  controlId?: number,
  search?: string,
  limit = 100,
  filters?: Record<string, string>,
  sort?: { field: string; order: 'asc' | 'desc' } | null,
) {
  const branchKey = useBranchCacheKey()
  return useQuery({
    queryKey: ['pagedata', pageId, controlId, search, filters, sort, branchKey],
    queryFn: () => pageDataService.list(pageId, controlId, search, limit, filters, 0, sort),
    enabled: !!pageId,
    staleTime: 0,
  })
}

const PAGE_SIZE = 50

export function usePageDataInfinite(
  pageId: number,
  controlId?: number,
  search?: string,
  filters?: Record<string, string>,
  options?: { enabled?: boolean; sort?: { field: string; order: 'asc' | 'desc' } | null },
) {
  const branchKey = useBranchCacheKey()
  const sort = options?.sort ?? null
  return useInfiniteQuery({
    queryKey: ['pagedata', 'infinite', pageId, controlId, search, filters, sort, branchKey],
    queryFn: ({ pageParam }) =>
      pageDataService.list(pageId, controlId, search, PAGE_SIZE, filters, pageParam, sort),
    initialPageParam: 0,
    getNextPageParam: (lastPage, allPages) => {
      if (lastPage.length < PAGE_SIZE) return undefined
      return allPages.length * PAGE_SIZE
    },
    enabled: options?.enabled ?? !!pageId,
    staleTime: 0,
  })
}

export function useUpdateField(pageId: number, controlId?: number, options?: { cardPage?: boolean; listPageId?: number }) {
  const qc = useQueryClient()
  const syncRecordInListCaches = (targetPageId: number, systemId: string, record: DataRecord) => {
    qc.setQueriesData<DataRecord[]>(
      { queryKey: ['pagedata', targetPageId] },
      (old) => {
        if (!Array.isArray(old)) return old
        let changed = false
        const next = old.map((row) => {
          if (row.SystemId !== systemId) return row
          changed = true
          return { ...row, ...record }
        })
        return changed ? next : old
      },
    )
  }

  return useMutation({
    mutationFn: ({
      systemId,
      field,
      value,
      recordValues,
    }: {
      systemId: string
      field: PageControlField
      value: unknown
      recordValues?: Record<string, unknown>
    }) =>
      pageDataService.update(pageId, systemId, field.Name, value, options?.listPageId, recordValues),
    onSuccess: (response, { systemId }) => {
      if (response.record) {
        if (options?.cardPage) {
          qc.setQueryData<DataRecord>(
            ['pagedata', 'record', pageId, 'card', systemId],
            response.record,
          )
        } else if (controlId !== undefined) {
          qc.setQueryData<DataRecord>(
            ['pagedata', 'record', pageId, controlId, systemId],
            response.record,
          )
        }
        syncRecordInListCaches(pageId, systemId, response.record)
        if (options?.listPageId && options.listPageId !== pageId) {
          syncRecordInListCaches(options.listPageId, systemId, response.record)
        }
      }
      qc.invalidateQueries({ queryKey: ['pagedata', 'infinite', pageId] })
      qc.invalidateQueries({ queryKey: ['pagedata', pageId] })
      // Card updates merge into the list cache; refetching the list drops card-only fields.
      if (options?.listPageId && options.listPageId !== pageId && !options?.cardPage) {
        qc.invalidateQueries({ queryKey: ['pagedata', 'infinite', options.listPageId] })
        qc.invalidateQueries({ queryKey: ['pagedata', options.listPageId] })
      }
    },
  })
}

export function useDeleteRecord(pageId: number, controlId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (systemId: string) => pageDataService.delete(pageId, controlId, systemId),
    onSuccess: (_data, systemId) => {
      removeRecordFromPageDataCaches(qc, pageId, systemId)
      qc.invalidateQueries({ queryKey: ['pagedata', 'infinite', pageId] })
      qc.invalidateQueries({ queryKey: ['pagedata', pageId] })
    },
  })
}

export function useCreateRecord(pageId: number, controlId: number, _fields: PageControlField[]) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: Record<string, unknown>) => pageDataService.create(pageId, controlId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['pagedata', 'infinite', pageId] })
      qc.invalidateQueries({ queryKey: ['pagedata', pageId] })
    },
  })
}

export function pendingRowHasRequiredFields(
  record: DataRecord,
  fields: PageControlField[],
): boolean {
  for (const field of fields) {
    if (!field.Visible) continue
    if (!field.Required && !field.PrimaryKey) continue
    const val = record[field.Name] ?? record[field.Name.toLowerCase()]
    if (val === null || val === undefined || val === '') return false
  }
  return true
}

/** True when the user entered any visible list field on a not-yet-saved row. */
export function pendingRowHasAnyData(
  record: DataRecord,
  fields: PageControlField[],
): boolean {
  for (const field of fields) {
    if (!field.Visible) continue
    const val = record[field.Name] ?? record[field.Name.toLowerCase()]
    if (val !== null && val !== undefined && val !== '') return true
  }
  return false
}

export function usePageDataRecord(
  pageId: number,
  controlId: number | undefined,
  systemId: string | undefined,
  options?: { cardPage?: boolean },
) {
  const branchKey = useBranchCacheKey()
  const cardPage = options?.cardPage ?? false
  return useQuery({
    queryKey: cardPage
      ? ['pagedata', 'record', pageId, 'card', systemId, branchKey]
      : ['pagedata', 'record', pageId, controlId, systemId, branchKey],
    queryFn: () => pageDataService.getRecord(pageId, cardPage ? undefined : controlId, systemId!),
    enabled: !!pageId && !!systemId,
    staleTime: 0,
  })
}

/** Prev/next SystemIds for Business Central–style card record navigation. */
export function usePageDataNeighbors(
  listPageId: number | undefined,
  systemId: string | undefined,
  enabled = true,
) {
  const branchKey = useBranchCacheKey()
  return useQuery({
    queryKey: ['pagedata', 'neighbors', listPageId, systemId, branchKey],
    queryFn: () => pageDataService.getNeighbors(listPageId!, systemId!),
    enabled: enabled && !!listPageId && !!systemId && systemId !== 'new',
    staleTime: 30_000,
  })
}
