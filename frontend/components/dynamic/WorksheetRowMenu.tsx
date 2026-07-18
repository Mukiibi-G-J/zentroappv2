'use client'

import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { Link2, ListChecks, ListPlus, ListX, MoreVertical } from 'lucide-react'
import { cn } from '@/lib/utils'

interface ExtraMenuItem {
  id: string
  label: string
  icon: React.ComponentType<{ size?: number; className?: string }>
  disabled?: boolean
  onClick: () => void
}

interface Props {
  insertAllowed: boolean
  deleteAllowed: boolean
  multiSelectActive: boolean
  rowSelected: boolean
  onNewLine: () => void
  onDeleteLine: () => void
  onSelectMore: () => void
  extraItems?: ExtraMenuItem[]
}

interface MenuPosition {
  left: number
  top: number
  placement: 'above' | 'below'
}

export default function WorksheetRowMenu({
  insertAllowed,
  deleteAllowed,
  multiSelectActive,
  rowSelected,
  onNewLine,
  onDeleteLine,
  onSelectMore,
  extraItems = [],
}: Props) {
  const [open, setOpen] = useState(false)
  const [mounted, setMounted] = useState(false)
  const [menuPosition, setMenuPosition] = useState<MenuPosition | null>(null)
  const buttonRef = useRef<HTMLButtonElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    setMounted(true)
  }, [])

  const updatePosition = () => {
    const button = buttonRef.current
    const menu = menuRef.current
    if (!button) return

    const rect = button.getBoundingClientRect()
    const menuHeight = menu?.offsetHeight ?? 132
    const spaceBelow = window.innerHeight - rect.bottom
    const placement = spaceBelow < menuHeight + 8 && rect.top > menuHeight + 8 ? 'above' : 'below'

    setMenuPosition({
      left: rect.left,
      top: placement === 'below' ? rect.bottom + 4 : rect.top - 4,
      placement,
    })
  }

  useLayoutEffect(() => {
    if (!open) {
      setMenuPosition(null)
      return
    }
    updatePosition()
    requestAnimationFrame(updatePosition)
  }, [open, insertAllowed, deleteAllowed, multiSelectActive, extraItems.length])

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
  }, [open, insertAllowed, deleteAllowed, multiSelectActive, extraItems.length])

  const run = (action: () => void) => {
    setOpen(false)
    action()
  }

  const menu = open && mounted ? (
    <div
      ref={menuRef}
      role="menu"
      style={{
        position: 'fixed',
        left: menuPosition?.left ?? -9999,
        top: menuPosition?.top ?? -9999,
        transform: menuPosition?.placement === 'above' ? 'translateY(-100%)' : undefined,
        visibility: menuPosition ? 'visible' : 'hidden',
        zIndex: 9999,
      }}
      className="min-w-[11rem] rounded-lg border border-gray-200 bg-white py-1 shadow-lg"
      onClick={(e) => e.stopPropagation()}
    >
      {insertAllowed && (
        <button
          type="button"
          role="menuitem"
          className="flex w-full items-center gap-2.5 px-3 py-2 text-left text-sm text-mainTextColor hover:bg-gray-50"
          onClick={() => run(onNewLine)}
        >
          <ListPlus size={16} className="text-s1 shrink-0" />
          New Line
        </button>
      )}
      {deleteAllowed && (
        <button
          type="button"
          role="menuitem"
          className="flex w-full items-center gap-2.5 px-3 py-2 text-left text-sm text-mainTextColor hover:bg-gray-50"
          onClick={() => run(onDeleteLine)}
        >
          <ListX size={16} className="text-s1 shrink-0" />
          Delete Line
        </button>
      )}
      {extraItems.map((item) => {
        const ItemIcon = item.icon
        return (
          <button
            key={item.id}
            type="button"
            role="menuitem"
            disabled={item.disabled}
            className="flex w-full items-center gap-2.5 px-3 py-2 text-left text-sm text-mainTextColor hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40"
            onClick={() => run(item.onClick)}
          >
            <ItemIcon size={16} className="text-s1 shrink-0" />
            {item.label}
          </button>
        )
      })}
      <button
        type="button"
        role="menuitem"
        className="flex w-full items-center gap-2.5 px-3 py-2 text-left text-sm text-mainTextColor hover:bg-gray-50"
        onClick={() => run(onSelectMore)}
      >
        <ListChecks size={16} className="text-s1 shrink-0" />
        {multiSelectActive ? 'Select One' : 'Select More'}
      </button>
    </div>
  ) : null

  return (
    <>
      <button
        ref={buttonRef}
        type="button"
        title="Line actions"
        aria-label="Line actions"
        aria-expanded={open}
        onClick={(e) => {
          e.stopPropagation()
          setOpen((value) => !value)
        }}
        className={cn(
          'relative z-30 flex h-6 w-6 shrink-0 items-center justify-center rounded bg-s1 text-white shadow-sm transition-opacity',
          'opacity-0 group-hover:opacity-100 focus:opacity-100 focus:outline-none focus:ring-2 focus:ring-s1/40',
          (open || rowSelected) && 'opacity-100',
        )}
      >
        <MoreVertical size={14} />
      </button>
      {menu ? createPortal(menu, document.body) : null}
    </>
  )
}
