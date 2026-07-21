'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import { getFieldCaption } from '@/lib/fieldCaption'
import { extractApiErrorMessage } from '@/lib/apiError'
import { listFieldValuesEqual, normalizeListFieldSaveValue } from '@/lib/listFieldValue'
import { getRecordFieldValue } from '@/lib/recordFieldValue'
import {
  hasContextRelation,
  contextRelationCacheKey,
  buildRelationRecordValues,
  getDependentRelationFields,
} from '@/lib/contextRelations'
import { formatRelationDisplay, resolveRelationSelectValue } from '@/lib/relationDisplay'
import { mapTableRelationValue, type RelationOption } from '@/hooks/useRelationOptions'
import { pageService } from '@/services/page.service'
import { useCreateRecord, useDeleteRecord, usePageDataList, useUpdateField } from '@/hooks/usePageData'
import { useWorksheetGridKeyboard } from '@/hooks/useWorksheetGridKeyboard'
import {
  type GridActiveCell,
  isLineFieldEditable,
  moveGridActiveCell,
  readActiveCellCommitValue,
} from '@/lib/worksheetGridKeyboard'
import { findWorksheetLinesControl, visibleLineFields } from '@/lib/worksheetControls'
import { worksheetFrozenFieldProps } from '@/lib/worksheetColumns'
import DynamicField from './DynamicField'
import SearchableRelationSelect from './SearchableRelationSelect'
import WorksheetRibbon from './WorksheetRibbon'
import WorksheetRowMenu from './WorksheetRowMenu'
import { ConfirmDialog } from '@/components/ui/ConfirmDialog'
import type { Page, PageAction, PageControlField } from '@/types/page'
import type { DataRecord } from '@/types/pagedata'

const EMPTY_RECORDS: DataRecord[] = []

const stickySelectBase =
  'w-10 min-w-10 shrink-0 px-2 text-center sticky left-0 z-20 overflow-visible shadow-[2px_0_4px_-1px_rgba(0,0,0,0.08)]'

function stickySelectCellClass(isSelected: boolean) {
  return cn(
    stickySelectBase,
    'py-2',
    isSelected ? 'bg-[#eef5f5]' : 'bg-white group-hover:bg-gray-50',
  )
}

function formatValue(value: unknown, field: PageControlField): string {
  if (value === null || value === undefined || value === '') return '—'
  if (field.FieldType === 'Boolean') return value ? 'Yes' : 'No'
  if (field.FieldType === 'Date' && value) {
    try {
      return new Date(String(value)).toLocaleDateString()
    } catch {
      return String(value)
    }
  }
  if (field.FieldType === 'Decimal') {
    return Number(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  }
  if (field.FieldType === 'Integer') return Number(value).toLocaleString()
  return String(value)
}

export interface WorksheetEditableGridProps {
  pageId: number
  page: Page
  lineFilters: Record<string, string>
  /** Static defaults merged into every new line. */
  lineDefaults?: Record<string, unknown>
  /** Dynamic defaults when Add New is pressed (e.g. remaining quantity). */
  getCreatePayload?: () => Record<string, unknown>
  /** Hide columns (after standard visible-line filtering). */
  fieldFilter?: (field: PageControlField) => boolean
  /** Per-row editability override (default: page modify + field editable). */
  isFieldEditable?: (field: PageControlField, record: DataRecord) => boolean
  /** Fires on blur before save (even when the value did not change). */
  onFieldBlur?: (record: DataRecord, field: PageControlField, value: unknown) => void
  onFieldSaved?: (record: DataRecord, field: PageControlField, value: unknown) => void
  pageActions?: PageAction[]
  onPageAction?: (action: PageAction) => void
  showSearch?: boolean
  gridClassName?: string
  onCreateSuccess?: (record: DataRecord) => void
  /** Called whenever the loaded line records change (including after delete). */
  onRecordsChange?: (records: DataRecord[]) => void
  /** Disables add/edit/delete (e.g. posted item tracking entries). */
  gridReadOnly?: boolean
}

export default function WorksheetEditableGrid({
  pageId,
  page,
  lineFilters,
  lineDefaults = {},
  getCreatePayload,
  fieldFilter,
  isFieldEditable,
  onFieldBlur,
  onFieldSaved,
  pageActions = [],
  onPageAction,
  showSearch = false,
  gridClassName,
  onCreateSuccess,
  onRecordsChange,
  gridReadOnly = false,
}: WorksheetEditableGridProps) {
  const [search, setSearch] = useState('')
  const [selectedRow, setSelectedRow] = useState<string | null>(null)
  const [editingCell, setEditingCell] = useState<GridActiveCell | null>(null)
  const [typeahead, setTypeahead] = useState<{ cell: GridActiveCell; char: string } | null>(null)
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null)
  const [relationOptions, setRelationOptions] = useState<Record<number, RelationOption[]>>({})
  const [contextRelationOptions, setContextRelationOptions] = useState<Record<string, RelationOption[]>>({})
  const loadedContextOptions = useRef(new Set<string>())
  const gridRef = useRef<HTMLDivElement>(null)

  const listControl = findWorksheetLinesControl(page)

  const insertAllowed = !gridReadOnly && !!page.InsertAllowed
  const modifyAllowed = !gridReadOnly && !!page.ModifyAllowed
  const deleteAllowed = !gridReadOnly && !!page.DeleteAllowed
  const visibleFields = useMemo(() => {
    const fields = visibleLineFields(listControl?.Fields, page.ContextFilterField)
    return fieldFilter ? fields.filter(fieldFilter) : fields
  }, [fieldFilter, listControl?.Fields, page.ContextFilterField])

  const { data, isLoading, refetch, isFetching } = usePageDataList(
    pageId,
    listControl?.PageControlId,
    search,
    500,
    lineFilters,
  )
  // Stable empty fallback — `data ?? []` allocates a new array every render and
  // combined with onRecordsChange → parent setState causes max update depth.
  const records = data ?? EMPTY_RECORDS

  const updateField = useUpdateField(pageId, listControl?.PageControlId)
  const deleteRecord = useDeleteRecord(pageId, listControl?.PageControlId ?? 0)
  const createRecord = useCreateRecord(pageId, listControl?.PageControlId ?? 0, listControl?.Fields ?? [])
  /** Latest in-flight value per row+field — blocks duplicate identical saves only. */
  const pendingFieldSaves = useRef(new Map<string, unknown>())

  const onRecordsChangeRef = useRef(onRecordsChange)
  onRecordsChangeRef.current = onRecordsChange

  useEffect(() => {
    onRecordsChangeRef.current?.(records)
  }, [records])

  useEffect(() => {
    if (records.length === 0) {
      setSelectedRow(null)
      return
    }
    setSelectedRow((prev) => (
      prev && records.some((row) => row.SystemId === prev) ? prev : records[0].SystemId
    ))
  }, [records])

  const loadContextRelationOptions = useCallback(
    async (field: PageControlField, record: DataRecord | Record<string, unknown>) => {
      if (!listControl) return
      const cacheKey = contextRelationCacheKey(field, record)
      if (!cacheKey || loadedContextOptions.current.has(cacheKey)) return
      try {
        const values = await pageService.fetchTableRelations(
          pageId,
          listControl.PageControlId,
          field.PageControlFieldId,
          null,
          buildRelationRecordValues(field, record) ?? {},
        )
        loadedContextOptions.current.add(cacheKey)
        setContextRelationOptions((prev) => ({
          ...prev,
          [cacheKey]: values.map(mapTableRelationValue),
        }))
      } catch {
        loadedContextOptions.current.delete(cacheKey)
      }
    },
    [listControl, pageId],
  )

  const relationFieldKey = useMemo(() => {
    if (!listControl) return ''
    return listControl.Fields
      .filter((f) => f.Visible && f.HasTableRelation && !hasContextRelation(f))
      .map((f) => f.PageControlFieldId)
      .join(',')
  }, [listControl?.Fields])

  useEffect(() => {
    if (!listControl || !relationFieldKey) return
    const relationFields = listControl.Fields.filter(
      (f) => f.Visible && f.HasTableRelation && !hasContextRelation(f),
    )
    let cancelled = false
    ;(async () => {
      const next: typeof relationOptions = {}
      for (const field of relationFields) {
        const values = await pageService.fetchTableRelations(
          pageId,
          listControl.PageControlId,
          field.PageControlFieldId,
        )
        if (!cancelled) next[field.PageControlFieldId] = values.map(mapTableRelationValue)
      }
      if (!cancelled) setRelationOptions(next)
    })()
    return () => {
      cancelled = true
    }
  }, [listControl, pageId, relationFieldKey])

  const getFieldRelationOptions = useCallback(
    (field: PageControlField, record: DataRecord) => {
      if (hasContextRelation(field)) {
        const cacheKey = contextRelationCacheKey(field, record)
        return cacheKey ? contextRelationOptions[cacheKey] ?? [] : []
      }
      return relationOptions[field.PageControlFieldId] ?? []
    },
    [contextRelationOptions, relationOptions],
  )

  const fieldEditable = useCallback(
    (field: PageControlField, record?: DataRecord) => {
      const base = isLineFieldEditable(
        field,
        modifyAllowed,
        listControl?.Editable !== false,
      )
      if (!base) return false
      if (record && isFieldEditable) return isFieldEditable(field, record)
      return true
    },
    [isFieldEditable, listControl?.Editable, modifyAllowed],
  )

  const focusCell = useCallback(
    (record: DataRecord, field: PageControlField, opts?: { typeahead?: string }) => {
      setSelectedRow(record.SystemId)
      const cell: GridActiveCell = { systemId: record.SystemId, field: field.Name }
      setEditingCell(cell)
      setTypeahead(
        opts?.typeahead != null && opts.typeahead !== ''
          ? { cell, char: opts.typeahead }
          : null,
      )
      if (hasContextRelation(field)) void loadContextRelationOptions(field, record)
      if (!fieldEditable(field, record)) {
        requestAnimationFrame(() => {
          gridRef.current?.focus({ preventScroll: true })
        })
      }
    },
    [fieldEditable, loadContextRelationOptions],
  )

  const saveFieldValue = useCallback(
    (record: DataRecord, field: PageControlField, value: unknown) => {
      const normalized = normalizeListFieldSaveValue(field, value)
      if (listFieldValuesEqual(normalized, getRecordFieldValue(record, field.Name), field)) return
      if (
        field.HasTableRelation
        && (normalized == null || normalized === '')
        && getRecordFieldValue(record, field.Name) != null
        && getRecordFieldValue(record, field.Name) !== ''
      ) {
        return
      }

      const saveKey = `${record.SystemId}:${field.Name}`
      const inFlight = pendingFieldSaves.current.get(saveKey)
      // Only skip an identical in-flight save — a newer value must still PATCH
      // (browser autofill can blur between keystrokes and would otherwise drop the final text).
      if (inFlight !== undefined && listFieldValuesEqual(inFlight, normalized, field)) return
      pendingFieldSaves.current.set(saveKey, normalized)

      const mutationOpts = {
        onError: (err: unknown) => toast.error(extractApiErrorMessage(err)),
        onSuccess: () => {
          if (pendingFieldSaves.current.get(saveKey) !== normalized) return
          onFieldSaved?.(record, field, normalized)
        },
        onSettled: () => {
          if (pendingFieldSaves.current.get(saveKey) === normalized) {
            pendingFieldSaves.current.delete(saveKey)
          }
        },
      }

      const dependentFields = getDependentRelationFields(listControl?.Fields ?? [], field.Name)
      if (dependentFields.length > 0) {
        updateField.mutate({ systemId: record.SystemId, field, value: normalized }, mutationOpts)
        for (const dep of dependentFields) {
          void loadContextRelationOptions(dep, { ...record, [field.Name]: normalized })
          if (getRecordFieldValue(record, dep.Name)) {
            updateField.mutate(
              { systemId: record.SystemId, field: dep, value: null },
              { onError: mutationOpts.onError },
            )
          }
        }
        return
      }
      updateField.mutate({ systemId: record.SystemId, field, value: normalized }, mutationOpts)
    },
    [listControl?.Fields, loadContextRelationOptions, onFieldSaved, updateField],
  )

  const commitActiveCell = useCallback(() => {
    if (!editingCell) return
    const record = records.find((row) => row.SystemId === editingCell.systemId)
    const field = visibleFields.find((f) => f.Name === editingCell.field)
    if (!record || !field || !fieldEditable(field, record)) return
    if (field.HasTableRelation) return

    const commitValue = readActiveCellCommitValue(
      document.activeElement as HTMLElement | null,
      field,
    )
    if (commitValue !== undefined) {
      saveFieldValue(record, field, commitValue)
    }
  }, [editingCell, fieldEditable, records, saveFieldValue, visibleFields])

  const navigateCell = useCallback(
    (direction: 'left' | 'right' | 'up' | 'down') => {
      commitActiveCell()
      if (!editingCell || records.length === 0) return
      const next = moveGridActiveCell(editingCell, direction, visibleFields, records)
      if (!next) return
      const record = records.find((row) => row.SystemId === next.systemId)
      const field = visibleFields.find((f) => f.Name === next.field)
      if (!record || !field) return
      focusCell(record, field)
    },
    [commitActiveCell, editingCell, focusCell, records, visibleFields],
  )

  useWorksheetGridKeyboard({
    enabled: modifyAllowed && records.length > 0,
    gridRef,
    records,
    visibleFields,
    editingCell,
    selectedRowId: selectedRow,
    fieldEditable: (field) => {
      const record = editingCell
        ? records.find((row) => row.SystemId === editingCell.systemId)
        : records.find((row) => row.SystemId === selectedRow)
      return fieldEditable(field, record)
    },
    focusCell,
    commitActiveCell,
    navigateCell,
    onEscape: () => setTypeahead(null),
  })

  useEffect(() => {
    if (!typeahead) return
    const timer = window.setTimeout(() => setTypeahead(null), 0)
    return () => window.clearTimeout(timer)
  }, [typeahead])

  const handleFieldBlur = useCallback(
    (record: DataRecord, field: PageControlField, value: unknown) => {
      onFieldBlur?.(record, field, value)
      saveFieldValue(record, field, value)
    },
    [onFieldBlur, saveFieldValue],
  )

  const handleCellClick = useCallback(
    (record: DataRecord, field: PageControlField) => {
      commitActiveCell()
      setSelectedRow(record.SystemId)
      if (!fieldEditable(field, record)) return
      focusCell(record, field)
    },
    [commitActiveCell, fieldEditable, focusCell],
  )

  const handleAddRow = useCallback(() => {
    if (!insertAllowed || !listControl) return
    const payload = {
      ...lineDefaults,
      ...(getCreatePayload?.() ?? {}),
    }
    createRecord.mutate(payload, {
      onSuccess: (created) => {
        if (created?.SystemId) {
          setSelectedRow(String(created.SystemId))
          onCreateSuccess?.(created)
        }
      },
      onError: (err) => toast.error(extractApiErrorMessage(err)),
    })
  }, [createRecord, getCreatePayload, insertAllowed, lineDefaults, listControl, onCreateSuccess])

  const handleRibbonAction = useCallback(
    (action: PageAction) => {
      if (onPageAction?.(action)) return
      if (action.ActionRelativeUrl === '#delete-line' || action.Name === 'DeleteLine') {
        if (!selectedRow) {
          toast.error('Select a line first')
          return
        }
        setPendingDeleteId(selectedRow)
      }
    },
    [onPageAction, selectedRow],
  )

  return (
    <>
      <WorksheetRibbon
        pageActions={pageActions}
        insertAllowed={insertAllowed}
        search={search}
        onSearch={setSearch}
        onRefresh={() => void refetch()}
        onAddNew={handleAddRow}
        onAction={handleRibbonAction}
        isRefreshing={isFetching}
        isAdding={createRecord.isPending}
        actionLoading={deleteRecord.isPending || updateField.isPending}
        showSearch={showSearch}
      />

      <div
        ref={gridRef}
        tabIndex={0}
        className={cn(
          'rounded-xl border border-gray-200 bg-white overflow-x-auto max-h-[50vh] overflow-y-auto outline-none',
          gridClassName,
        )}
      >
        {isLoading && records.length === 0 ? (
          <div className="flex items-center justify-center gap-2 py-16 text-sm text-bodyText">
            <Loader2 size={16} className="animate-spin" />
            Loading lines…
          </div>
        ) : (
          <table className="min-w-max w-full text-sm">
            <thead className="sticky top-0 z-30">
              <tr className="bg-gray-50 border-b border-gray-200">
                <th className={cn(stickySelectBase, 'py-3 z-50 bg-gray-50')} />
                {visibleFields.map((f, fi) => {
                  const frozen = worksheetFrozenFieldProps(visibleFields, fi, 'header')
                  return (
                    <th key={f.PageControlFieldId} className={frozen.className} style={frozen.style}>
                      {getFieldCaption(f, page)}
                      {f.Required ? <span className="ml-0.5 text-red-600">*</span> : null}
                    </th>
                  )
                })}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 [&_td]:overflow-visible">
              {records.length === 0 ? (
                <tr>
                  <td
                    colSpan={visibleFields.length + 1}
                    className="px-4 py-12 text-center text-bodyText"
                  >
                    No lines — use Add New to create a line
                  </td>
                </tr>
              ) : (
                records.map((record) => {
                  const rowSelected = selectedRow === record.SystemId
                  return (
                    <tr
                      key={record.SystemId}
                      className={cn('group transition', rowSelected ? 'bg-s1/5' : 'hover:bg-gray-50')}
                    >
                      <td className={stickySelectCellClass(rowSelected)}>
                        <input
                          type="radio"
                          name="worksheet-editable-row"
                          checked={rowSelected}
                          onChange={() => setSelectedRow(record.SystemId)}
                          className="accent-s1"
                        />
                      </td>
                      {visibleFields.map((field, fi) => {
                        const canEdit = fieldEditable(field, record)
                        const isActive =
                          editingCell?.systemId === record.SystemId
                          && editingCell.field === field.Name
                        const isEditing = isActive && canEdit
                        const fieldValue = getRecordFieldValue(record, field.Name)
                        const options = field.HasTableRelation
                          ? getFieldRelationOptions(field, record)
                          : []
                        const caption = getFieldCaption(field, page)
                        const typeaheadChar =
                          typeahead?.cell.systemId === record.SystemId
                          && typeahead?.cell.field === field.Name
                            ? typeahead.char
                            : undefined
                        const frozen = worksheetFrozenFieldProps(visibleFields, fi, 'body', {
                          isSelected: rowSelected,
                          extraClass: canEdit ? 'cursor-text' : undefined,
                        })

                        const cellContent = isEditing ? (
                          field.HasTableRelation ? (
                            <SearchableRelationSelect
                              autoFocus
                              initialInput={typeaheadChar}
                              options={options}
                              value={resolveRelationSelectValue(fieldValue, options)}
                              placeholder={`Search ${caption}…`}
                              onChange={(val) => handleFieldBlur(record, field, val)}
                            />
                          ) : (
                            <DynamicField
                              field={field}
                              value={fieldValue}
                              singleLine
                              autoFocus
                              initialInput={typeaheadChar}
                              disabled={!canEdit}
                              onBlur={(value) => handleFieldBlur(record, field, value)}
                            />
                          )
                        ) : (
                          <span className="text-mainTextColor truncate">
                            {field.HasTableRelation && options.length > 0
                              ? formatRelationDisplay(fieldValue, field, options)
                              : formatValue(fieldValue, field)}
                          </span>
                        )

                        return (
                          <td
                            key={field.PageControlFieldId}
                            className={cn(
                              frozen.className,
                              isActive && !isEditing && 'ring-2 ring-s1/30 ring-inset',
                            )}
                            style={frozen.style}
                            onClick={() => handleCellClick(record, field)}
                          >
                            {fi === 0 ? (
                              <div className="flex items-center gap-1.5 min-w-0">
                                <WorksheetRowMenu
                                  insertAllowed={insertAllowed}
                                  deleteAllowed={deleteAllowed}
                                  multiSelectActive={false}
                                  rowSelected={rowSelected}
                                  onNewLine={handleAddRow}
                                  onDeleteLine={() => setPendingDeleteId(record.SystemId)}
                                  onSelectMore={() => setSelectedRow(record.SystemId)}
                                />
                                <div className="min-w-0 flex-1">{cellContent}</div>
                              </div>
                            ) : (
                              cellContent
                            )}
                          </td>
                        )
                      })}
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        )}
      </div>

      {pendingDeleteId ? (
        <ConfirmDialog
          open
          title="Delete line?"
          message="Delete this tracking line?"
          confirmLabel="Delete"
          variant="danger"
          onConfirm={() => {
            deleteRecord.mutate(pendingDeleteId, {
              onSuccess: () => toast.success('Line deleted'),
              onError: (err) => toast.error(extractApiErrorMessage(err)),
            })
            if (selectedRow === pendingDeleteId) setSelectedRow(null)
            setPendingDeleteId(null)
          }}
          onCancel={() => setPendingDeleteId(null)}
        />
      ) : null}
    </>
  )
}
