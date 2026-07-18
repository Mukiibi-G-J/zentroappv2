'use client'

import { useMemo, useState } from 'react'
import { Eye, Plus, RefreshCw, Search, Send, Settings } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { PageAction } from '@/types/page'

interface Props {
  pageActions: PageAction[]
  insertAllowed: boolean
  search: string
  onSearch: (value: string) => void
  onRefresh: () => void
  onAddNew: () => void
  onAction: (action: PageAction) => void
  onOpenBatches?: () => void
  isRefreshing?: boolean
  isAdding?: boolean
  actionLoading?: boolean
  /** BC Apply Entries worksheets have no line search. */
  showSearch?: boolean
}

const TAB_ORDER = ['Home', 'Manage', 'Line'] as const

function actionIcon(action: PageAction) {
  if (action.Name === 'PreviewPosting' || action.Caption.toLowerCase().includes('preview')) {
    return Eye
  }
  return Send
}

export default function WorksheetRibbon({
  pageActions,
  insertAllowed,
  search,
  onSearch,
  onRefresh,
  onAddNew,
  onAction,
  onOpenBatches,
  isRefreshing,
  isAdding,
  actionLoading,
  showSearch = true,
}: Props) {
  const tabs = useMemo(() => {
    const fromActions = [...new Set(
      pageActions.map((a) => a.RibbonTab || 'Home').filter(Boolean),
    )]
    const ordered = TAB_ORDER.filter((t) => fromActions.includes(t) || t === 'Home' || t === 'Manage')
    if (onOpenBatches && !ordered.includes('Manage')) ordered.push('Manage')
    return ordered.length ? ordered : ['Home']
  }, [pageActions, onOpenBatches])

  const [activeTab, setActiveTab] = useState(tabs[0] ?? 'Home')
  const tabActions = pageActions.filter((a) => (a.RibbonTab || 'Home') === activeTab)

  return (
    <div className="rounded-xl border border-gray-200 bg-white overflow-hidden">
      <div className="flex items-center gap-1 px-2 pt-2 border-b border-gray-200 bg-gray-50/80">
        {tabs.map((tab) => (
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
      </div>

      <div className="flex flex-wrap items-center gap-2 px-3 py-2.5">
        {activeTab === 'Home' && (
          <>
            {tabActions.map((action) => {
              const Icon = actionIcon(action)
              const isPrimary = action.Name === 'Post'
              return (
                <button
                  key={action.ActionId}
                  type="button"
                  onClick={() => onAction(action)}
                  disabled={actionLoading}
                  title={action.Tooltip ?? action.Caption}
                  className={cn(
                    'inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg transition disabled:opacity-50',
                    isPrimary
                      ? 'bg-s1 text-white hover:opacity-90'
                      : 'border border-gray-200 text-mainTextColor hover:bg-gray-50',
                  )}
                >
                  <Icon size={14} />
                  {action.Caption}
                </button>
              )
            })}

            {insertAllowed && (
              <button
                type="button"
                onClick={onAddNew}
                disabled={isAdding}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium border border-gray-200 rounded-lg hover:bg-gray-50 text-mainTextColor transition disabled:opacity-50"
              >
                <Plus size={14} />
                Add New
              </button>
            )}

            <button
              type="button"
              onClick={onRefresh}
              className="p-2 rounded-lg hover:bg-gray-100 text-bodyText transition"
              title="Refresh"
            >
              <RefreshCw size={15} className={isRefreshing ? 'animate-spin' : ''} />
            </button>

            {showSearch ? (
              <div className="relative ml-auto w-full sm:w-56">
                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
                <input
                  className="w-full pl-9 pr-3 py-1.5 text-sm text-mainTextColor bg-white border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-s1/30 focus:border-s1"
                  placeholder="Search lines…"
                  value={search}
                  onChange={(e) => onSearch(e.target.value)}
                />
              </div>
            ) : null}
          </>
        )}

        {activeTab === 'Manage' && onOpenBatches && (
          <button
            type="button"
            onClick={onOpenBatches}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium border border-gray-200 rounded-lg hover:bg-gray-50 text-mainTextColor transition"
          >
            <Settings size={14} />
            Journal Batches
          </button>
        )}

        {activeTab !== 'Home' && activeTab !== 'Manage' && tabActions.map((action) => (
          <button
            key={action.ActionId}
            type="button"
            onClick={() => onAction(action)}
            disabled={actionLoading}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium border border-gray-200 rounded-lg hover:bg-gray-50 text-mainTextColor transition disabled:opacity-50"
          >
            {action.Caption}
          </button>
        ))}
      </div>
    </div>
  )
}
