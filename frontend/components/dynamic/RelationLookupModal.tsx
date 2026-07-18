'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useRouter } from 'next/navigation'
import {
  Eye,
  ListChecks,
  Loader2,
  MoreVertical,
  Pencil,
  Plus,
  RefreshCw,
  Trash2,
  X,
} from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import { colWidthPx } from '@/lib/worksheetColumns'
import {
  usePageDataInfinite,
  useCreateRecord,
  useUpdateField,
  useDeleteRecord,
  pendingRowHasRequiredFields,
} from '@/hooks/usePageData'
import { usePages } from '@/hooks/usePage'
import DynamicField from '@/components/dynamic/DynamicField'
import SearchableRelationSelect from '@/components/dynamic/SearchableRelationSelect'
import { useRelationOptions } from '@/hooks/useRelationOptions'
import { drillDownDefaultsForNewRow } from '@/lib/listInlineCreate'
import { listFieldValuesEqual, normalizeListFieldSaveValue } from '@/lib/listFieldValue'
import { extractErrorMessage } from '@/services/pagedata.service'
import { getRecordFieldValue } from '@/lib/recordFieldValue'
import { relationValueFromRecord } from '@/lib/relationValue'
import { getCardRecordPath, getPageRouteId } from '@/lib/pageRoutes'
import type { Page, PageControlField } from '@/types/page'
import type { DataRecord } from '@/types/pagedata'

/** BC-style narrow column for row ⋮ menu between Code and Description */
const MENU_COL_PX = 32

export interface RelationLookupModalProps {
  open: boolean
  lookupPage: Page
  targetField: PageControlField
  drillDownFilters: Record<string, string>
  autoNew?: boolean
  /** When set, card Back navigates here instead of the lookup list (e.g. POS). */
  returnPath?: string | null
  onClose: () => void
  onConfirm: (value: string, record: DataRecord) => void
}

interface RowMenu {
  systemId: string
  x: number
  y: number
}

interface RecordActionMenuProps {
  cardPageId: number | null | undefined
  canDelete: boolean
  disabled?: boolean
  onEdit: () => void
  onView: () => void
  onDelete: () => void
  className?: string
}

function RecordActionMenu({
  cardPageId,
  canDelete,
  disabled,
  onEdit,
  onView,
  onDelete,
  className,
}: RecordActionMenuProps) {
  const canNavigate = Boolean(cardPageId)
  return (
    <div className={cn('py-1 text-sm', className)}>
      {canNavigate ? (
        <>
          <button
            type="button"
            disabled={disabled}
            onMouseDown={(e) => e.preventDefault()}
            onClick={onEdit}
            className="flex w-full items-center gap-2 px-3 py-1.5 text-mainTextColor hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Pencil size={13} />
            Edit
          </button>
          <button
            type="button"
            disabled={disabled}
            onMouseDown={(e) => e.preventDefault()}
            onClick={onView}
            className="flex w-full items-center gap-2 px-3 py-1.5 text-mainTextColor hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Eye size={13} />
            View
          </button>
        </>
      ) : null}
      {canNavigate && canDelete ? <div className="my-1 border-t border-gray-100" /> : null}
      {canDelete ? (
        <button
          type="button"
          disabled={disabled}
          onMouseDown={(e) => e.preventDefault()}
          onClick={onDelete}
          className="flex w-full items-center gap-2 px-3 py-1.5 text-red-600 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Trash2 size={13} />
          Delete
        </button>
      ) : null}
    </div>
  )
}

function formatValue(value: unknown, field: PageControlField): string {
  if (value === null || value === undefined || value === '') return '—'
  if (field.FieldType === 'Boolean') return value ? 'Yes' : 'No'
  if (field.FieldType === 'Code') return String(value).toUpperCase()
  return String(value)
}

export default function RelationLookupModal({
  open,
  lookupPage,
  targetField,
  drillDownFilters,
  autoNew = false,
  returnPath,
  onClose,
  onConfirm,
}: RelationLookupModalProps) {
  const router = useRouter()
  const { data: allPages = [] } = usePages()
  const listControl = lookupPage.PageControls.find(
    (c) => c.ControlType === 'Repeater' || c.ControlType === 'Group',
  )
  const visibleFields = listControl?.Fields.filter((f) => f.Visible) ?? []
  const displayFields =
    lookupPage.ContextFilterField
      ? visibleFields.filter((f) => f.Name !== lookupPage.ContextFilterField)
      : visibleFields
  const firstField = displayFields[0] ?? null
  const restFields = displayFields.slice(1)
  const firstColWidth = firstField ? colWidthPx(firstField) : 192
  const canEditList =
    lookupPage.ModifyAllowed !== false &&
    lookupPage.Editable !== false &&
    listControl?.Editable !== false

  const isFieldEditable = (field: PageControlField) =>
    field.Editable && lookupPage.ModifyAllowed !== false && !field.NoSeriesCode

  const {
    data,
    isLoading,
    isError,
    error,
    refetch,
  } = usePageDataInfinite(
    lookupPage.PageId,
    listControl?.PageControlId,
    undefined,
    drillDownFilters,
    { enabled: open && !!listControl },
  )

  const [pendingRows, setPendingRows] = useState<DataRecord[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [rowMenu, setRowMenu] = useState<RowMenu | null>(null)
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)
  const [editListMode, setEditListMode] = useState(false)
  const [toolbarMenuOpen, setToolbarMenuOpen] = useState(false)
  const autoNewStarted = useRef(false)
  const rowMenuRef = useRef<HTMLDivElement>(null)
  const toolbarMenuRef = useRef<HTMLDivElement>(null)

  const cardPage = useMemo(
    () =>
      lookupPage.CardPageId
        ? allPages.find((p) => p.PageId === lookupPage.CardPageId)
        : undefined,
    [allPages, lookupPage.CardPageId],
  )
  const canDelete = lookupPage.DeleteAllowed !== false
  const canNavigateCard = Boolean(lookupPage.CardPageId)
  const showRowActions = canNavigateCard || canDelete

  const rawRecords = data?.pages.flatMap((p) => p) ?? []
  const serverRecords: DataRecord[] = [...new Map(rawRecords.map((r) => [r.SystemId, r])).values()]
  const records = useMemo(() => {
    const merged = [...pendingRows, ...serverRecords]
    const seen = new Set<string>()
    return merged.filter((row) => {
      const id = String(row.SystemId)
      if (seen.has(id)) return false
      seen.add(id)
      return true
    })
  }, [pendingRows, serverRecords])

  const filteredRecords = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return records
    return records.filter((record) =>
      displayFields.some((field) => {
        const val = getRecordFieldValue(record, field.Name)
        return val != null && String(val).toLowerCase().includes(q)
      }),
    )
  }, [records, search, displayFields])

  const selectedRecord = useMemo(
    () => records.find((r) => String(r.SystemId) === selectedId) ?? null,
    [records, selectedId],
  )

  const createRecord = useCreateRecord(
    lookupPage.PageId,
    listControl?.PageControlId ?? 0,
    listControl?.Fields ?? [],
  )
  const updateField = useUpdateField(lookupPage.PageId, listControl?.PageControlId)
  const deleteRecord = useDeleteRecord(lookupPage.PageId, listControl?.PageControlId ?? 0)
  const relationOptions = useRelationOptions(
    open ? lookupPage.PageId : undefined,
    visibleFields,
    null,
    drillDownFilters,
  )

  const getFieldOptions = (field: PageControlField) =>
    relationOptions[field.PageControlFieldId] ?? []

  const isPendingRow = (record: DataRecord) =>
    pendingRows.some((r) => String(r.SystemId) === String(record.SystemId))

  const updatePendingRow = (systemId: string, patch: Partial<DataRecord>): DataRecord => {
    let updated!: DataRecord
    setPendingRows((prev) =>
      prev.map((r) => {
        if (String(r.SystemId) !== systemId) return r
        updated = { ...r, ...patch }
        return updated
      }),
    )
    return updated
  }

  const tryCreatePending = async (record: DataRecord) => {
    if (!pendingRowHasRequiredFields(record, visibleFields)) return null
    const payload: Record<string, unknown> = {}
    for (const field of visibleFields) {
      if (!field.Visible) continue
      const val = record[field.Name]
      if (val !== undefined && val !== null && val !== '') {
        payload[field.Name] = normalizeListFieldSaveValue(field, val)
      }
    }
    for (const [key, value] of Object.entries(drillDownFilters)) {
      if (value !== undefined && value !== null && value !== '') {
        payload[key] = value
      }
    }
    return createRecord.mutateAsync(payload)
  }

  const handleAddNew = () => {
    if (!lookupPage.InsertAllowed) return
    if (lookupPage.CardPageId) {
      const query: Record<string, string> = { fromList: String(getPageRouteId(lookupPage)) }
      if (returnPath?.startsWith('/')) query.return = returnPath
      onClose()
      router.push(
        getCardRecordPath(
          lookupPage.CardPageId,
          'new',
          cardPage?.PageType ?? 'Card',
          query,
        ),
      )
      return
    }
    const id = crypto.randomUUID()
    const defaults: DataRecord = {
      SystemId: id,
      ...(lookupPage.SourceTable === 'ItemUnitOfMeasure' ? { quantity_per_unit: 1 } : {}),
      ...drillDownDefaultsForNewRow(visibleFields, drillDownFilters),
    }
    setPendingRows((prev) => [defaults, ...prev])
    setSelectedId(id)
  }

  const handleFieldBlur = async (record: DataRecord, field: PageControlField, value: unknown) => {
    const normalized = normalizeListFieldSaveValue(field, value)
    if (listFieldValuesEqual(normalized, record[field.Name], field)) return
    try {
      if (isPendingRow(record)) {
        updatePendingRow(String(record.SystemId), { [field.Name]: normalized })
        return
      }
      await updateField.mutateAsync({ systemId: record.SystemId, field, value: normalized })
      await refetch()
    } catch (err) {
      toast.error(extractErrorMessage(err))
    }
  }

  const renderInlineEditor = (record: DataRecord, field: PageControlField) => {
    const fieldValue = getRecordFieldValue(record, field.Name)
    if (field.HasTableRelation) {
      return (
        <SearchableRelationSelect
          compact
          options={getFieldOptions(field)}
          value={String(fieldValue ?? '')}
          placeholder={`Search ${field.Caption}…`}
          onChange={(val) => void handleFieldBlur(record, field, val)}
        />
      )
    }
    return (
      <DynamicField
        field={field}
        singleLine
        value={fieldValue}
        onBlur={(value) => void handleFieldBlur(record, field, value)}
        onKeyDown={(e: React.KeyboardEvent<HTMLInputElement>) => {
          if (e.key === 'Enter') e.currentTarget.blur()
        }}
      />
    )
  }

  const renderReadOnlyValue = (record: DataRecord, field: PageControlField) => {
    const fieldValue = getRecordFieldValue(record, field.Name)
    if (fieldValue === null || fieldValue === undefined || fieldValue === '') return '—'
    const str = String(fieldValue)
    if (field.HasTableRelation) {
      const match = getFieldOptions(field).find((o) => o.value === str)
      return match?.label ?? str
    }
    return formatValue(fieldValue, field)
  }

  const renderCell = (record: DataRecord, field: PageControlField, isSelected: boolean, pending: boolean) => {
    if (pending || (editListMode && isFieldEditable(field))) {
      return renderInlineEditor(record, field)
    }
    return (
      <span
        className={cn(
          'block truncate',
          field === firstField && 'font-medium font-mono',
          isSelected && 'text-mainTextColor',
        )}
      >
        {renderReadOnlyValue(record, field)}
      </span>
    )
  }

  const handleRequestDelete = (systemId: string) => {
    setDeleteError(null)
    setPendingDeleteId(systemId)
    setRowMenu(null)
  }

  const handleDeleteRow = async (systemId: string) => {
    const record = records.find((r) => String(r.SystemId) === systemId)
    if (!record) return
    if (isPendingRow(record)) {
      setPendingRows((prev) => prev.filter((r) => String(r.SystemId) !== systemId))
      if (selectedId === systemId) setSelectedId(null)
      return
    }
    await deleteRecord.mutateAsync(systemId)
    if (selectedId === systemId) setSelectedId(null)
    await refetch()
  }

  const handleOpenMenu = (e: React.MouseEvent, record: DataRecord) => {
    e.stopPropagation()
    setSelectedId(String(record.SystemId))
    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
    setRowMenu({ systemId: record.SystemId, x: rect.left, y: rect.bottom + 4 })
    setToolbarMenuOpen(false)
  }

  const navigateToCard = (systemId: string, mode: 'edit' | 'view') => {
    if (!lookupPage.CardPageId) {
      toast.error('No card page is configured for this list.')
      return
    }
    const query: Record<string, string> = { fromList: String(getPageRouteId(lookupPage)) }
    if (mode === 'view') query.mode = 'view'
    if (returnPath?.startsWith('/')) query.return = returnPath
    onClose()
    router.push(
      getCardRecordPath(
        lookupPage.CardPageId,
        systemId,
        cardPage?.PageType ?? 'Card',
        query,
      ),
    )
  }

  const openRecordEdit = (systemId: string) => navigateToCard(systemId, 'edit')
  const openRecordView = (systemId: string) => navigateToCard(systemId, 'view')

  const selectedActionsDisabled =
    !selectedRecord || isPendingRow(selectedRecord) || editListMode

  const handleDeleteConfirm = async () => {
    if (!pendingDeleteId || isDeleting) return
    setIsDeleting(true)
    setDeleteError(null)
    try {
      await handleDeleteRow(pendingDeleteId)
      setPendingDeleteId(null)
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : 'Failed to delete record')
    } finally {
      setIsDeleting(false)
    }
  }

  useEffect(() => {
    if (!open) {
      autoNewStarted.current = false
      setPendingRows([])
      setSelectedId(null)
      setSearch('')
      setRowMenu(null)
      setPendingDeleteId(null)
      setDeleteError(null)
      setEditListMode(false)
      setToolbarMenuOpen(false)
      return
    }
    if (autoNew && lookupPage.InsertAllowed && !autoNewStarted.current) {
      autoNewStarted.current = true
      handleAddNew()
    }
  }, [open, autoNew, lookupPage.InsertAllowed])

  useEffect(() => {
    if (!open || filteredRecords.length === 0) return
    setSelectedId((prev) => {
      if (prev && filteredRecords.some((r) => String(r.SystemId) === prev)) return prev
      return String(filteredRecords[0].SystemId)
    })
  }, [open, filteredRecords])

  useEffect(() => {
    if (!rowMenu && !toolbarMenuOpen) return
    const handler = (e: MouseEvent) => {
      const target = e.target as Node
      if (rowMenuRef.current?.contains(target)) return
      if (toolbarMenuRef.current?.contains(target)) return
      setRowMenu(null)
      setToolbarMenuOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [rowMenu, toolbarMenuOpen])

  const handleOk = async (recordOverride?: DataRecord) => {
    const record = recordOverride ?? selectedRecord
    if (!record) {
      toast.error('Select a record first.')
      return
    }

    let confirmedRecord = record

    if (isPendingRow(record)) {
      if (!pendingRowHasRequiredFields(record, visibleFields)) {
        toast.error('Fill in required fields before confirming.')
        return
      }
      try {
        const created = await tryCreatePending(record)
        if (!created?.SystemId) {
          toast.error('Could not create the record.')
          return
        }
        setPendingRows((prev) =>
          prev.filter((r) => String(r.SystemId) !== String(record.SystemId)),
        )
        setSelectedId(String(created.SystemId))
        confirmedRecord = created
        await refetch()
      } catch (err) {
        toast.error(extractErrorMessage(err))
        return
      }
    }

    const value = relationValueFromRecord(targetField, confirmedRecord)
    if (!value) {
      toast.error('Could not resolve a value from the selected row.')
      return
    }
    onConfirm(value, confirmedRecord)
  }

  if (!open || typeof document === 'undefined') return null

  const errorMessage = error instanceof Error ? error.message : 'Failed to load records'
  const colSpan = Math.max(displayFields.length, 1) + 1

  return createPortal(
    <>
      <div
        className="fixed inset-0 z-[200] flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm"
        role="dialog"
        aria-modal="true"
        aria-labelledby="relation-lookup-title"
      >
        <div className="flex max-h-[90dvh] w-full max-w-4xl flex-col overflow-hidden rounded-xl bg-white shadow-2xl">
          <div className="flex items-center justify-between border-b border-gray-200 px-5 py-4">
            <h2 id="relation-lookup-title" className="text-lg font-semibold text-mainTextColor">
              Select — {lookupPage.Caption}
            </h2>
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg p-2 text-bodyText hover:bg-gray-100"
              aria-label="Close"
            >
              <X size={18} />
            </button>
          </div>

          <div className="flex items-center gap-2 border-b border-gray-100 px-5 py-3">
            <input
              className="w-full max-w-xs rounded-lg border border-strokeColor px-3 py-2 text-sm focus:border-s1 focus:outline-none focus:ring-2 focus:ring-s1/20"
              placeholder="Search…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            <button
              type="button"
              onClick={() => refetch()}
              className="rounded-lg p-2 text-bodyText hover:bg-gray-100"
              title="Refresh"
            >
              <RefreshCw size={15} />
            </button>
            <div className="ml-auto flex items-center gap-2">
              {canEditList ? (
                <button
                  type="button"
                  onClick={() => setEditListMode((v) => !v)}
                  className={cn(
                    'inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm transition',
                    editListMode
                      ? 'border-s1 bg-s1/10 text-s1 font-medium'
                      : 'border-strokeColor text-bodyText hover:bg-gray-50',
                  )}
                  title={editListMode ? 'Exit edit mode' : 'Edit records in the list'}
                >
                  <ListChecks size={14} />
                  Edit List
                </button>
              ) : null}
              {lookupPage.InsertAllowed ? (
                <button
                  type="button"
                  onClick={handleAddNew}
                  disabled={createRecord.isPending}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-s1 px-3 py-1.5 text-sm text-white hover:opacity-90 disabled:opacity-60"
                >
                  {createRecord.isPending ? (
                    <Loader2 size={14} className="animate-spin" />
                  ) : (
                    <Plus size={14} />
                  )}
                  New
                </button>
              ) : null}
              {showRowActions ? (
                <div className="relative" ref={toolbarMenuRef}>
                  <button
                    type="button"
                    onClick={() => {
                      setToolbarMenuOpen((v) => !v)
                      setRowMenu(null)
                    }}
                    className="rounded-lg border border-strokeColor p-2 text-bodyText hover:bg-gray-50"
                    title="Actions"
                    aria-label="List actions"
                  >
                    <MoreVertical size={16} />
                  </button>
                  {toolbarMenuOpen ? (
                    <div className="absolute right-0 top-full z-50 mt-1 min-w-[180px] overflow-hidden rounded-lg border border-gray-200 bg-white shadow-lg">
                      <div className="border-b border-gray-100 px-3 py-1.5 text-xs font-semibold uppercase tracking-wide text-bodyText">
                        Manage
                      </div>
                      <RecordActionMenu
                        cardPageId={lookupPage.CardPageId}
                        canDelete={canDelete}
                        disabled={selectedActionsDisabled}
                        onEdit={() => {
                          if (!selectedRecord) return
                          openRecordEdit(String(selectedRecord.SystemId))
                          setToolbarMenuOpen(false)
                        }}
                        onView={() => {
                          if (!selectedRecord) return
                          openRecordView(String(selectedRecord.SystemId))
                          setToolbarMenuOpen(false)
                        }}
                        onDelete={() => {
                          if (!selectedRecord) return
                          handleRequestDelete(String(selectedRecord.SystemId))
                          setToolbarMenuOpen(false)
                        }}
                      />
                    </div>
                  ) : null}
                </div>
              ) : null}
            </div>
          </div>

          <div className="min-h-0 flex-1 overflow-auto">
            {isError ? (
              <p className="px-5 py-8 text-sm text-red-600">{errorMessage}</p>
            ) : (
              <table className="min-w-full text-sm">
                <thead className="sticky top-0 z-10 border-b border-gray-200 bg-gray-50">
                  <tr>
                    {firstField && (
                      <th
                        className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-bodyText"
                        style={{ width: firstColWidth, minWidth: firstColWidth }}
                      >
                        {firstField.Caption}
                      </th>
                    )}
                    <th
                      className="border-b p-0"
                      style={{ width: MENU_COL_PX, minWidth: MENU_COL_PX }}
                      aria-hidden
                    />
                    {restFields.map((f) => (
                      <th
                        key={f.PageControlFieldId}
                        className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-bodyText"
                        style={{ width: colWidthPx(f), minWidth: colWidthPx(f) }}
                      >
                        {f.Caption}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {isLoading && filteredRecords.length === 0 ? (
                    <tr>
                      <td colSpan={colSpan} className="px-4 py-10 text-center text-bodyText">
                        <Loader2 size={20} className="mx-auto animate-spin" />
                      </td>
                    </tr>
                  ) : filteredRecords.length === 0 ? (
                    <tr>
                      <td colSpan={colSpan} className="px-4 py-10 text-center text-bodyText">
                        No records found
                      </td>
                    </tr>
                  ) : (
                    filteredRecords.map((record) => {
                      const isSelected = selectedId === String(record.SystemId)
                      const pending = isPendingRow(record)
                      return (
                        <tr
                          key={record.SystemId}
                          className={cn(
                            'group cursor-pointer transition',
                            isSelected && !pending && 'bg-[#e8f4f4]',
                            isSelected && pending && 'bg-amber-100/80',
                            !isSelected && 'hover:bg-gray-50',
                            pending && !isSelected && 'bg-amber-50/60',
                          )}
                          onFocusCapture={() => setSelectedId(String(record.SystemId))}
                          onClick={() => setSelectedId(String(record.SystemId))}
                          onDoubleClick={() => {
                            if (!pending && !editListMode) void handleOk(record)
                          }}
                        >
                          {firstField && (
                            <td
                              className="px-4 py-2 align-middle"
                              style={{ width: firstColWidth, minWidth: firstColWidth }}
                            >
                              {renderCell(record, firstField, isSelected, pending)}
                            </td>
                          )}
                          <td
                            className="relative p-0 align-middle"
                            style={{ width: MENU_COL_PX, minWidth: MENU_COL_PX }}
                            onClick={(e) => e.stopPropagation()}
                          >
                            {showRowActions && (
                              <button
                                type="button"
                                onClick={(e) => handleOpenMenu(e, record)}
                                className={cn(
                                  'flex h-full min-h-9 w-full items-center justify-center text-bodyText transition hover:bg-white/80 hover:text-mainTextColor',
                                  isSelected ? 'opacity-100' : 'opacity-0 group-hover:opacity-100 focus:opacity-100',
                                )}
                                title="Actions"
                                aria-label="Row actions"
                              >
                                <MoreVertical size={14} />
                              </button>
                            )}
                          </td>
                          {restFields.map((field) => (
                            <td
                              key={field.PageControlFieldId}
                              className="px-4 py-2 align-middle"
                              style={{ width: colWidthPx(field), minWidth: colWidthPx(field) }}
                            >
                              {renderCell(record, field, isSelected, pending)}
                            </td>
                          ))}
                        </tr>
                      )
                    })
                  )}
                </tbody>
              </table>
            )}
          </div>

          <div className="flex justify-end gap-2 border-t border-gray-200 px-5 py-4">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-strokeColor px-4 py-2 text-sm text-bodyText hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={() => void handleOk()}
              disabled={createRecord.isPending}
              className="rounded-lg bg-s1 px-5 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-60"
            >
              {createRecord.isPending ? 'Saving…' : 'OK'}
            </button>
          </div>
        </div>
      </div>

      {rowMenu &&
        createPortal(
          <div
            ref={rowMenuRef}
            className="fixed z-[210] min-w-[160px] rounded-lg border border-gray-200 bg-white shadow-lg pointer-events-auto"
            style={{ top: rowMenu.y, left: rowMenu.x }}
            onMouseDown={(e) => e.stopPropagation()}
          >
            <RecordActionMenu
              cardPageId={lookupPage.CardPageId}
              canDelete={canDelete}
              disabled={
                editListMode ||
                pendingRows.some((r) => String(r.SystemId) === rowMenu.systemId)
              }
              onEdit={() => {
                openRecordEdit(rowMenu.systemId)
                setRowMenu(null)
              }}
              onView={() => {
                openRecordView(rowMenu.systemId)
                setRowMenu(null)
              }}
              onDelete={() => handleRequestDelete(rowMenu.systemId)}
            />
          </div>,
          document.body,
        )}

      {pendingDeleteId && (
        <div className="fixed inset-0 z-[220] flex items-center justify-center bg-black/40">
          <div className="mx-4 w-full max-w-sm rounded-xl bg-white p-6 shadow-xl">
            <h3 className="text-base font-semibold text-mainTextColor">Delete record?</h3>
            <p className="mt-1 text-sm text-bodyText">This action cannot be undone.</p>
            {deleteError && <p className="mt-2 text-sm text-red-600">{deleteError}</p>}
            <div className="mt-5 flex justify-end gap-3">
              <button
                onClick={() => {
                  setPendingDeleteId(null)
                  setDeleteError(null)
                }}
                disabled={isDeleting}
                className="rounded-lg border border-strokeColor px-4 py-2 text-sm font-medium text-bodyText transition-colors hover:bg-softBg disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={() => void handleDeleteConfirm()}
                disabled={isDeleting}
                className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-red-700 disabled:opacity-50"
              >
                {isDeleting ? 'Deleting…' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>,
    document.body,
  )
}
