import { useCallback, useEffect, type RefObject } from 'react'
import type { PageControlField } from '@/types/page'
import type { DataRecord } from '@/types/pagedata'
import {
  type GridActiveCell,
  closeOpenRelationMenu,
  isGridTypingTarget,
  isPrintableTypingKey,
  isRelationMenuOpen,
  isRelationSelectTarget,
  shouldNavigateFromInput,
} from '@/lib/worksheetGridKeyboard'

export interface UseWorksheetGridKeyboardOptions {
  enabled: boolean
  gridRef: RefObject<HTMLElement | null>
  records: DataRecord[]
  visibleFields: PageControlField[]
  editingCell: GridActiveCell | null
  selectedRowId: string | null
  fieldEditable: (field: PageControlField) => boolean
  focusCell: (
    record: DataRecord,
    field: PageControlField,
    opts?: { typeahead?: string },
  ) => void
  commitActiveCell: () => void
  navigateCell: (direction: 'left' | 'right' | 'up' | 'down') => void
  onEscape?: () => void
}

export function useWorksheetGridKeyboard({
  enabled,
  gridRef,
  records,
  visibleFields,
  editingCell,
  selectedRowId,
  fieldEditable,
  focusCell,
  commitActiveCell,
  navigateCell,
  onEscape,
}: UseWorksheetGridKeyboardOptions) {
  const focusDefaultCell = useCallback(() => {
    const record = records.find((row) => row.SystemId === selectedRowId) ?? records[0]
    const field = visibleFields.find((f) => fieldEditable(f)) ?? visibleFields[0]
    if (record && field) focusCell(record, field)
  }, [fieldEditable, focusCell, records, selectedRowId, visibleFields])

  const handleGridKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (!enabled || records.length === 0) return
      const target = e.target as HTMLElement
      const inGridContext = !!gridRef.current?.contains(target) || editingCell != null
      if (!inGridContext) return

      const arrowDirection =
        e.key === 'ArrowLeft' ? 'left'
        : e.key === 'ArrowRight' ? 'right'
        : e.key === 'ArrowUp' ? 'up'
        : e.key === 'ArrowDown' ? 'down'
        : null

      if (arrowDirection) {
        const menuOpen = isRelationMenuOpen()
        const onRelationSelect = isRelationSelectTarget(target)

        if (menuOpen && onRelationSelect && (arrowDirection === 'up' || arrowDirection === 'down')) {
          return
        }

        if (onRelationSelect && (arrowDirection === 'left' || arrowDirection === 'right')) {
          e.preventDefault()
          e.stopPropagation()
          if (menuOpen) closeOpenRelationMenu()
          if (!editingCell) {
            focusDefaultCell()
            return
          }
          navigateCell(arrowDirection)
          return
        }

        if (menuOpen) return

        if (
          isGridTypingTarget(target)
          && (arrowDirection === 'left' || arrowDirection === 'right')
          && !shouldNavigateFromInput(e, target, arrowDirection)
        ) {
          return
        }
        e.preventDefault()
        if (!editingCell) {
          focusDefaultCell()
          return
        }
        navigateCell(arrowDirection)
        return
      }

      if (e.key === 'Tab') {
        if (isRelationMenuOpen()) closeOpenRelationMenu()
        e.preventDefault()
        if (!editingCell) {
          focusDefaultCell()
          return
        }
        navigateCell(e.shiftKey ? 'left' : 'right')
        return
      }

      if (e.key === 'Escape' && editingCell) {
        if (isRelationMenuOpen()) {
          e.preventDefault()
          closeOpenRelationMenu()
          return
        }
        e.preventDefault()
        onEscape?.()
        return
      }

      if (isPrintableTypingKey(e) && !isGridTypingTarget(target)) {
        if (!editingCell) {
          const record = records.find((row) => row.SystemId === selectedRowId) ?? records[0]
          const field = visibleFields.find((f) => fieldEditable(f)) ?? visibleFields[0]
          if (!record || !field || !fieldEditable(field)) return
          e.preventDefault()
          focusCell(record, field, { typeahead: e.key })
          return
        }
        const field = visibleFields.find((f) => f.Name === editingCell.field)
        const record = records.find((row) => row.SystemId === editingCell.systemId)
        if (!field || !record || !fieldEditable(field)) return
        e.preventDefault()
        focusCell(record, field, { typeahead: e.key })
      }
    },
    [
      enabled,
      editingCell,
      fieldEditable,
      focusCell,
      focusDefaultCell,
      gridRef,
      navigateCell,
      onEscape,
      records,
      selectedRowId,
      visibleFields,
    ],
  )

  useEffect(() => {
    document.addEventListener('keydown', handleGridKeyDown, true)
    return () => document.removeEventListener('keydown', handleGridKeyDown, true)
  }, [handleGridKeyDown])
}
