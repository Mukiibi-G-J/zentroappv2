'use client'

import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import {
  ArrowDownAZ,
  ArrowUpAZ,
  ChevronDown,
  Filter,
  FilterX,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import type { PageControlField } from '@/types/page'
import type { ListColumnSort, ListSortOrder } from '@/lib/listColumnFilters'

interface Props {
  field: PageControlField
  sort: ListColumnSort | null
  filterValue: string | null
  filterToValue: string | null
  onSort: (order: ListSortOrder) => void
  onFilterToValue: () => void
  onClearFilter: () => void
  className?: string
  style?: React.CSSProperties
}

interface MenuPosition {
  left: number
  top: number
}

export default function ListColumnHeaderMenu({
  field,
  sort,
  filterValue,
  filterToValue,
  onSort,
  onFilterToValue,
  onClearFilter,
  className,
  style,
}: Props) {
  const [open, setOpen] = useState(false)
  const [mounted, setMounted] = useState(false)
  const [menuPosition, setMenuPosition] = useState<MenuPosition | null>(null)
  const buttonRef = useRef<HTMLButtonElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)

  const isSorted = sort?.field === field.Name
  const sortAsc = isSorted && sort?.order === 'asc'
  const sortDesc = isSorted && sort?.order === 'desc'

  useEffect(() => {
    setMounted(true)
  }, [])

  const updatePosition = () => {
    const button = buttonRef.current
    const menu = menuRef.current
    if (!button) return
    const rect = button.getBoundingClientRect()
    const menuWidth = menu?.offsetWidth ?? 220
    const left = Math.min(rect.left, window.innerWidth - menuWidth - 8)
    setMenuPosition({ left: Math.max(8, left), top: rect.bottom + 4 })
  }

  useLayoutEffect(() => {
    if (!open) {
      setMenuPosition(null)
      return
    }
    updatePosition()
    requestAnimationFrame(updatePosition)
  }, [open, filterValue, filterToValue])

  useEffect(() => {
    if (!open) return
    const close = (event: MouseEvent) => {
      const target = event.target as Node
      if (buttonRef.current?.contains(target) || menuRef.current?.contains(target)) return
      setOpen(false)
    }
    const reposition = () => updatePosition()
    document.addEventListener('mousedown', close)
    window.addEventListener('scroll', reposition, true)
    window.addEventListener('resize', reposition)
    return () => {
      document.removeEventListener('mousedown', close)
      window.removeEventListener('scroll', reposition, true)
      window.removeEventListener('resize', reposition)
    }
  }, [open])

  const menu = open && menuPosition ? (
    <div
      ref={menuRef}
      className="fixed z-180 min-w-[220px] rounded-lg border border-gray-200 bg-white py-1 text-sm shadow-lg pointer-events-auto"
      style={{ top: menuPosition.top, left: menuPosition.left }}
      onMouseDown={(e) => e.stopPropagation()}
    >
      <button
        type="button"
        className={cn(
          'flex w-full items-center gap-2.5 px-3 py-2 hover:bg-gray-50 text-mainTextColor',
          sortAsc && 'bg-[#eef5f5]',
        )}
        onClick={() => {
          onSort('asc')
          setOpen(false)
        }}
      >
        <ArrowDownAZ size={15} className="text-s1 shrink-0" />
        Ascending
      </button>
      <button
        type="button"
        className={cn(
          'flex w-full items-center gap-2.5 px-3 py-2 hover:bg-gray-50 text-mainTextColor',
          sortDesc && 'bg-[#eef5f5]',
        )}
        onClick={() => {
          onSort('desc')
          setOpen(false)
        }}
      >
        <ArrowUpAZ size={15} className="text-s1 shrink-0" />
        Descending
      </button>
      <div className="my-1 border-t border-gray-100" />
      <button
        type="button"
        disabled={!filterToValue}
        title={filterToValue ? `Filter to "${filterToValue}"` : 'Select a row first'}
        className={cn(
          'flex w-full items-center gap-2.5 px-3 py-2 hover:bg-gray-50 text-mainTextColor disabled:opacity-40 disabled:cursor-not-allowed',
        )}
        onClick={() => {
          if (!filterToValue) return
          onFilterToValue()
          setOpen(false)
        }}
      >
        <Filter size={15} className="text-s1 shrink-0" />
        Filter to this value
      </button>
      <button
        type="button"
        disabled={!filterValue}
        className={cn(
          'flex w-full items-center gap-2.5 px-3 py-2 hover:bg-gray-50 text-mainTextColor disabled:opacity-40 disabled:cursor-not-allowed',
        )}
        onClick={() => {
          if (!filterValue) return
          onClearFilter()
          setOpen(false)
        }}
      >
        <FilterX size={15} className="text-bodyText shrink-0" />
        Clear filter
      </button>
    </div>
  ) : null

  return (
    <>
      <button
        ref={buttonRef}
        type="button"
        className={cn(
          'group/header flex w-full items-center gap-1 min-w-0 text-left font-medium uppercase tracking-wide text-xs text-bodyText hover:text-mainTextColor focus:outline-none focus-visible:ring-2 focus-visible:ring-s1/30 rounded',
          (filterValue || isSorted) && 'text-s1',
          className,
        )}
        style={style}
        title={field.Tooltip ?? field.Caption}
        onClick={(e) => {
          e.stopPropagation()
          setOpen((prev) => !prev)
        }}
      >
        <span className="truncate">{field.Caption}</span>
        {sortAsc && <ArrowDownAZ size={12} className="shrink-0 text-s1" aria-hidden />}
        {sortDesc && <ArrowUpAZ size={12} className="shrink-0 text-s1" aria-hidden />}
        {filterValue && !isSorted && (
          <Filter size={11} className="shrink-0 text-s1" aria-hidden />
        )}
        <ChevronDown
          size={12}
          className={cn(
            'shrink-0 text-bodyText/70 transition group-hover/header:text-bodyText',
            open && 'rotate-180',
          )}
          aria-hidden
        />
      </button>
      {mounted && menu ? createPortal(menu, document.body) : null}
    </>
  )
}
