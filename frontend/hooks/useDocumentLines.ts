'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { pageDataService, extractErrorMessage } from '@/services/pagedata.service'
import { usePageDataInfinite, removeRecordFromPageDataCaches } from '@/hooks/usePageData'
import type { DataRecord } from '@/types/pagedata'

const DEFER_LINE_CREATE_TABLES = new Set(['PermissionSetLine'])

export interface UseDocumentLinesOptions {
  partPageId: number
  repeaterControlId: number
  linkField: string
  headerSystemId: string | null
  /** Part/list source table — used to defer DB create until required FKs are set. */
  sourceTable?: string
  /** Called after lines are added, updated, or deleted (e.g. refresh header totals). */
  onMutate?: () => void
}

export interface UseDocumentLinesReturn {
  lines: DataRecord[]
  isLoading: boolean
  isError: boolean
  errorMessage: string
  total: number
  addLine: () => Promise<void>
  updateLineField: (systemId: string, field: string, value: unknown) => Promise<DataRecord | undefined>
  deleteLine: (systemId: string) => Promise<void>
  refetch: () => void
  isAdding: boolean
  isDeleting: boolean
}

export function useDocumentLines(options: UseDocumentLinesOptions): UseDocumentLinesReturn {
  const { partPageId, repeaterControlId, linkField, headerSystemId, sourceTable, onMutate } = options
  const qc = useQueryClient()
  const enabled = Boolean(headerSystemId && partPageId && repeaterControlId)
  const deferLineCreate = DEFER_LINE_CREATE_TABLES.has(sourceTable ?? '')

  const filters = useMemo(
    () => (headerSystemId ? { parent_system_id: headerSystemId } : undefined),
    [headerSystemId],
  )

  const {
    data,
    isLoading,
    isError,
    error,
    refetch,
  } = usePageDataInfinite(partPageId, repeaterControlId, undefined, filters, { enabled })

  const [lines, setLines] = useState<DataRecord[]>([])
  const [pendingLineIds, setPendingLineIds] = useState<Set<string>>(() => new Set())
  const [isAdding, setIsAdding] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)

  const withParentLink = useCallback(
    (payload: Record<string, unknown>) => {
      const next = { ...payload }
      if (linkField && !linkField.includes('__') && headerSystemId) {
        next[linkField] = headerSystemId
      }
      return next
    },
    [headerSystemId, linkField],
  )

  const permissionLineReadyToSave = useCallback((line: DataRecord) => {
    const objectType = line.object_type
    const objectId = line.object_id
    return (
      objectType != null
      && String(objectType).trim() !== ''
      && objectId != null
      && String(objectId).trim() !== ''
    )
  }, [])

  useEffect(() => {
    setPendingLineIds(new Set())
  }, [headerSystemId])

  useEffect(() => {
    if (!data) {
      if (!enabled) {
        setLines((prev) => (prev.length === 0 ? prev : []))
        setPendingLineIds((prev) => (prev.size === 0 ? prev : new Set()))
      }
      return
    }
    const raw = data.pages.flatMap((p) => p)
    const serverLines = [...new Map(raw.map((r) => [r.SystemId, r])).values()]
    setLines((prev) => {
      const pending = prev.filter((line) => pendingLineIds.has(line.SystemId))
      if (pending.length === 0) return serverLines
      const serverIds = new Set(serverLines.map((line) => line.SystemId))
      return [
        ...pending.filter((line) => !serverIds.has(line.SystemId)),
        ...serverLines,
      ]
    })
  }, [data, enabled, pendingLineIds])

  const total = useMemo(
    () => lines.reduce(
      (sum, line) => sum + (Number(line.total_amount ?? line.amount) || 0),
      0,
    ),
    [lines],
  )

  const errorMessage = error instanceof Error ? error.message : 'Failed to load lines'

  const addLine = useCallback(async () => {
    if (!headerSystemId) return
    setIsAdding(true)
    try {
      if (deferLineCreate) {
        const id = crypto.randomUUID()
        setLines((prev) => [...prev, { SystemId: id, object_type: 'Page' }])
        setPendingLineIds((prev) => new Set(prev).add(id))
        return
      }

      const payload: Record<string, unknown> = {}
      const maxLineNo = lines.reduce((max, line) => Math.max(max, Number(line.line_no) || 0), 0)
      const nextLineNo = maxLineNo + 10000
      payload.line_no = nextLineNo
      const maxRowNo = lines.reduce((max, line) => Math.max(max, Number(line.row_no) || 0), 0)
      payload.row_no = maxRowNo > 0 ? String(maxRowNo + 10000) : String(nextLineNo)
      if (linkField && !linkField.includes('__')) {
        payload[linkField] = headerSystemId
      }
      const record = await pageDataService.create(
        partPageId,
        repeaterControlId,
        payload,
        headerSystemId,
      )
      setLines((prev) => [...prev, record])
      qc.invalidateQueries({ queryKey: ['pagedata', 'infinite', partPageId] })
      onMutate?.()
    } catch (err) {
      toast.error(extractErrorMessage(err))
      throw err
    } finally {
      setIsAdding(false)
    }
  }, [deferLineCreate, headerSystemId, linkField, lines, onMutate, partPageId, repeaterControlId, qc])

  const updateLineField = useCallback(
    async (systemId: string, field: string, value: unknown) => {
      try {
        if (deferLineCreate && pendingLineIds.has(systemId)) {
          const current = lines.find((line) => line.SystemId === systemId)
          if (!current) return
          const nextLine: DataRecord = { ...current, [field]: value }
          if (field === 'object_type') {
            nextLine.object_id = undefined
            nextLine.object_name = ''
          }
          setLines((prev) =>
            prev.map((line) => (line.SystemId === systemId ? nextLine : line)),
          )
          if (!permissionLineReadyToSave(nextLine)) {
            return nextLine
          }
          const payload = withParentLink({ ...nextLine })
          delete payload.SystemId
          delete payload.object_name
          delete payload.id
          const record = await pageDataService.create(
            partPageId,
            repeaterControlId,
            payload,
            headerSystemId ?? undefined,
          )
          setPendingLineIds((prev) => {
            const next = new Set(prev)
            next.delete(systemId)
            return next
          })
          setLines((prev) =>
            prev.map((line) => (line.SystemId === systemId ? record : line)),
          )
          qc.invalidateQueries({ queryKey: ['pagedata', 'infinite', partPageId] })
          onMutate?.()
          return record
        }

        const response = await pageDataService.update(
          partPageId,
          systemId,
          field,
          value,
          undefined,
          lines.find((line) => line.SystemId === systemId) ?? {},
        )
        if (response.record) {
          setLines((prev) =>
            prev.map((line) => (line.SystemId === systemId ? response.record : line)),
          )
        }
        qc.invalidateQueries({ queryKey: ['pagedata', 'infinite', partPageId] })
        onMutate?.()
        return response.record
      } catch (err) {
        toast.error(`${field}: ${extractErrorMessage(err)}`)
        throw err
      }
    },
    [
      deferLineCreate,
      headerSystemId,
      lines,
      onMutate,
      partPageId,
      pendingLineIds,
      permissionLineReadyToSave,
      qc,
      repeaterControlId,
      withParentLink,
    ],
  )

  const deleteLine = useCallback(
    async (systemId: string) => {
      setIsDeleting(true)
      try {
        if (deferLineCreate && pendingLineIds.has(systemId)) {
          setPendingLineIds((prev) => {
            const next = new Set(prev)
            next.delete(systemId)
            return next
          })
          setLines((prev) => prev.filter((line) => line.SystemId !== systemId))
          return
        }

        await pageDataService.delete(partPageId, repeaterControlId, systemId)
        removeRecordFromPageDataCaches(qc, partPageId, systemId)
        setLines((prev) => prev.filter((line) => line.SystemId !== systemId))
        qc.invalidateQueries({ queryKey: ['pagedata', 'infinite', partPageId] })
        qc.invalidateQueries({ queryKey: ['pagedata', partPageId] })
        onMutate?.()
      } catch (err) {
        toast.error(extractErrorMessage(err))
        throw err
      } finally {
        setIsDeleting(false)
      }
    },
    [deferLineCreate, onMutate, partPageId, pendingLineIds, repeaterControlId, qc],
  )

  return {
    lines,
    isLoading: enabled && isLoading,
    isError: enabled && isError,
    errorMessage,
    total,
    addLine,
    updateLineField,
    deleteLine,
    refetch,
    isAdding,
    isDeleting,
  }
}
