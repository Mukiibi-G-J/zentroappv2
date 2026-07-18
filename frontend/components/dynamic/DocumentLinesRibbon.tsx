'use client'

import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import {
  ChevronDown,
  Info,
  ListChecks,
  ListPlus,
  ListX,
  Loader2,
  Plus,
  RefreshCw,
  Zap,
} from 'lucide-react'
import { cn } from '@/lib/utils'

const LINE_TABS = ['Lines', 'Line'] as const
type LineTab = (typeof LINE_TABS)[number]

interface MenuItem {
  id: string
  label: string
  icon: React.ComponentType<{ size?: number; className?: string }>
  disabled?: boolean
  onClick: () => void
}

interface MenuGroup {
  id: string
  label: string
  icon: React.ComponentType<{ size?: number; className?: string }>
  items: MenuItem[]
}

interface Props {
  recordReady: boolean
  linesReadOnly: boolean
  insertAllowed: boolean
  deleteAllowed: boolean
  hasSelection: boolean
  multiSelectMode: boolean
  selectedCount?: number
  isAdding: boolean
  isDeleting: boolean
  lineCount: number
  onRefresh: () => void
  onAddLine: () => void
  onDeleteLine: () => void
  onToggleSelectMore: () => void
  canApplyEntries?: boolean
  onApplyEntries?: () => void
  pageFunctionItems?: MenuItem[]
}

function RibbonMenuGroup({ group }: { group: MenuGroup }) {
  const [open, setOpen] = useState(false)
  const [mounted, setMounted] = useState(false)
  const buttonRef = useRef<HTMLButtonElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)
  const [pos, setPos] = useState<{ left: number; top: number } | null>(null)
  const Icon = group.icon
  const enabledItems = group.items.filter((item) => !item.disabled)

  useEffect(() => {
    setMounted(true)
  }, [])

  useEffect(() => {
    if (!open) {
      setPos(null)
      return
    }
    const button = buttonRef.current
    if (!button) return
    const rect = button.getBoundingClientRect()
    setPos({ left: rect.left, top: rect.bottom + 4 })
  }, [open, group.items.length])

  useEffect(() => {
    if (!open) return
    const close = (event: MouseEvent) => {
      const target = event.target as Node
      if (buttonRef.current?.contains(target) || menuRef.current?.contains(target)) return
      setOpen(false)
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])

  const run = (item: MenuItem) => {
    setOpen(false)
    item.onClick()
  }

  const menu =
    open && mounted && pos && enabledItems.length > 0 ? (
      <div
        ref={menuRef}
        role="menu"
        style={{ position: 'fixed', left: pos.left, top: pos.top, zIndex: 9999 }}
        className="min-w-[12rem] rounded-lg border border-gray-200 bg-white py-1 shadow-lg"
      >
        {enabledItems.map((item) => {
          const ItemIcon = item.icon
          return (
            <button
              key={item.id}
              type="button"
              role="menuitem"
              disabled={item.disabled}
              className="flex w-full items-center gap-2.5 px-3 py-2 text-left text-sm text-mainTextColor hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40"
              onClick={() => run(item)}
            >
              <ItemIcon size={16} className="text-s1 shrink-0" />
              {item.label}
            </button>
          )
        })}
      </div>
    ) : null

  return (
    <>
      <button
        ref={buttonRef}
        type="button"
        disabled={enabledItems.length === 0}
        onClick={() => setOpen((value) => !value)}
        className={cn(
          'inline-flex items-center gap-1.5 px-2.5 py-1.5 text-sm font-medium rounded-lg border border-transparent',
          'text-mainTextColor hover:bg-gray-50 hover:border-gray-200 transition disabled:opacity-40 disabled:cursor-not-allowed',
          open && 'bg-gray-50 border-gray-200',
        )}
      >
        <Icon size={15} className="text-s1 shrink-0" />
        <span>{group.label}</span>
        <ChevronDown size={14} className="text-bodyText shrink-0" />
      </button>
      {menu ? createPortal(menu, document.body) : null}
    </>
  )
}

export default function DocumentLinesRibbon({
  recordReady,
  linesReadOnly,
  insertAllowed,
  deleteAllowed,
  hasSelection,
  multiSelectMode,
  selectedCount = 0,
  isAdding,
  isDeleting,
  lineCount,
  onRefresh,
  onAddLine,
  onDeleteLine,
  onToggleSelectMore,
  canApplyEntries = false,
  onApplyEntries,
  pageFunctionItems = [],
}: Props) {
  const [activeTab, setActiveTab] = useState<LineTab>('Lines')

  const lineGroups: MenuGroup[] = [
    {
      id: 'functions',
      label: 'Functions',
      icon: Zap,
      items: [
        {
          id: 'new-line',
          label: 'New Line',
          icon: ListPlus,
          disabled: !insertAllowed || linesReadOnly || !recordReady || isAdding,
          onClick: onAddLine,
        },
        {
          id: 'delete-line',
          label: 'Delete Line',
          icon: ListX,
          disabled: !deleteAllowed || linesReadOnly || !hasSelection || isDeleting,
          onClick: onDeleteLine,
        },
        {
          id: 'select-more',
          label: multiSelectMode ? 'Select One' : 'Select More',
          icon: ListChecks,
          disabled: !hasSelection && !multiSelectMode,
          onClick: onToggleSelectMore,
        },
        ...pageFunctionItems,
      ],
    },
    {
      id: 'related',
      label: 'Related Information',
      icon: Info,
      items: [
        {
          id: 'line-count',
          label: `${lineCount} line${lineCount === 1 ? '' : 's'} on document`,
          icon: Info,
          disabled: true,
          onClick: () => {},
        },
      ],
    },
  ]

  return (
    <div className="border-b border-gray-200 bg-gray-50/80">
      <div className="flex items-center gap-1 px-2 pt-2">
        {LINE_TABS.map((tab) => (
          <button
            key={tab}
            type="button"
            onClick={() => setActiveTab(tab)}
            className={cn(
              'px-3 py-1.5 text-xs font-medium rounded-t-md transition',
              activeTab === tab
                ? 'bg-white text-s1 border border-b-white border-gray-200 -mb-px'
                : 'text-bodyText hover:text-mainTextColor',
            )}
          >
            {tab}
          </button>
        ))}
        <span className="ml-auto pr-2 text-xs text-bodyText tabular-nums">
          {lineCount} line{lineCount === 1 ? '' : 's'}
          {multiSelectMode && selectedCount > 0 && (
            <span className="ml-2 text-s1">{selectedCount} selected</span>
          )}
        </span>
      </div>

      <div className="flex flex-wrap items-center gap-2 px-3 py-2.5 bg-white border-t border-gray-100">
        {activeTab === 'Lines' && (
          <>
            {insertAllowed && !linesReadOnly && (
              <button
                type="button"
                onClick={onAddLine}
                disabled={!recordReady || isAdding}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-s1 text-white text-sm font-medium rounded-lg hover:opacity-90 disabled:opacity-60 transition"
              >
                {isAdding ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
                Add Line
              </button>
            )}
            {deleteAllowed && !linesReadOnly && multiSelectMode && selectedCount > 0 && (
              <button
                type="button"
                onClick={onDeleteLine}
                disabled={isDeleting}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium border border-red-200 rounded-lg text-red-600 hover:bg-red-50 transition disabled:opacity-40"
              >
                <ListX size={14} />
                Delete {selectedCount} line{selectedCount !== 1 ? 's' : ''}
              </button>
            )}
            {multiSelectMode && (
              <button
                type="button"
                onClick={onToggleSelectMore}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium border border-gray-200 rounded-lg hover:bg-gray-50 text-mainTextColor transition"
              >
                <ListChecks size={14} className="text-s1" />
                Select One
              </button>
            )}
            <button
              type="button"
              onClick={onRefresh}
              disabled={!recordReady}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium border border-gray-200 rounded-lg hover:bg-gray-50 text-mainTextColor transition disabled:opacity-40"
            >
              <RefreshCw size={14} />
              Refresh
            </button>
            {pageFunctionItems.map((item) => {
              const ItemIcon = item.icon
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={item.onClick}
                  disabled={item.disabled}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium border border-gray-200 rounded-lg hover:bg-gray-50 text-mainTextColor transition disabled:opacity-40"
                >
                  <ItemIcon size={14} className="text-s1" />
                  {item.label}
                </button>
              )
            })}
          </>
        )}

        {activeTab === 'Line' && (
          <>
            {hasSelection && pageFunctionItems.map((item) => {
              const ItemIcon = item.icon
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={item.onClick}
                  disabled={item.disabled}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium border border-gray-200 rounded-lg hover:bg-gray-50 text-mainTextColor transition disabled:opacity-40"
                >
                  <ItemIcon size={14} className="text-s1" />
                  {item.label}
                </button>
              )
            })}
            {lineGroups.map((group) => (
              <RibbonMenuGroup key={group.id} group={group} />
            ))}
            {!hasSelection && (
              <span className="text-xs text-bodyText italic ml-1">
                Select a line to use line actions
              </span>
            )}
          </>
        )}
      </div>
    </div>
  )
}
