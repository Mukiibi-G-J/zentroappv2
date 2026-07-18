'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import { usePathname, useRouter, useSearchParams } from 'next/navigation'
import { Plus, Search, Trash2, PencilLine } from 'lucide-react'
import { usePages } from '@/hooks/usePage'
import { buildCardActionUrl } from '@/lib/cardAction'
import { buildListReturnPath, getCardRecordPath, getPageRouteId, listDashboardPath } from '@/lib/pageRoutes'
import { buildListPageActionUrl } from '@/lib/listPageAction'
import { isRibbonImageUrl, resolveRibbonIcon } from '@/lib/ribbonIcon'
import {
  actionsForRibbonTab,
  defaultRibbonTab,
  ribbonTabsFromActions,
  shouldShowRibbonTabBar,
} from '@/lib/ribbonTabs'
import { cn } from '@/lib/utils'
import type { Page, PageAction, PageControlField } from '@/types/page'
import type { DataRecord } from '@/types/pagedata'

type Props = {
  page: Page
  actions: PageAction[]
  selectedRecord: DataRecord | null
  sourceFields: PageControlField[]
  listPageId: number
  search: string
  onSearchChange: (value: string) => void
  onNew?: () => void
  onDelete?: () => void
  onServerAction?: (action: PageAction) => void
  onHashAction?: (action: PageAction) => void
  insertAllowed?: boolean
  deleteAllowed?: boolean
  disabled?: boolean
  showEditList?: boolean
  editListMode?: boolean
  onToggleEditList?: () => void
}

export default function ListPageRibbon({
  page,
  actions,
  selectedRecord,
  sourceFields,
  listPageId,
  search,
  onSearchChange,
  onNew,
  onDelete,
  onServerAction,
  onHashAction,
  insertAllowed = false,
  deleteAllowed = false,
  disabled,
  showEditList = false,
  editListMode = false,
  onToggleEditList,
}: Props) {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const { data: pages = [] } = usePages()
  const searchInputRef = useRef<HTMLInputElement>(null)
  const [searchOpen, setSearchOpen] = useState(Boolean(search.trim()))

  useEffect(() => {
    if (search.trim()) setSearchOpen(true)
  }, [search])

  useEffect(() => {
    if (searchOpen) searchInputRef.current?.focus()
  }, [searchOpen])

  const tabs = useMemo(() => ribbonTabsFromActions(actions), [actions])

  const hasTabs = shouldShowRibbonTabBar(tabs)
  const [activeTab, setActiveTab] = useState(() => defaultRibbonTab(tabs))

  useEffect(() => {
    setActiveTab((prev) => (tabs.includes(prev) ? prev : defaultRibbonTab(tabs)))
  }, [tabs])

  const tabActions = actionsForRibbonTab(actions, activeTab)
  const listReturnPath = useMemo(
    () => buildListReturnPath(page, searchParams, pathname),
    [page, searchParams, pathname],
  )

  const ribbonHasNew = actions.some((a) => (a.ActionRelativeUrl || '').trim() === '#new')
  const ribbonHasDelete = actions.some((a) => (a.ActionRelativeUrl || '').trim() === '#delete')
  const showBuiltinNew = insertAllowed && onNew && !ribbonHasNew
  const showBuiltinDelete = deleteAllowed && onDelete && !ribbonHasDelete

  const needsSelection = (action: PageAction) => {
    const target = (action.ActionRelativeUrl || '').trim()
    if (!target) return true
    if (target === '#delete') return false
    if (target === '#select-more') return false
    if (target.startsWith('#')) return false
    if (target.includes('{') || target.includes('applied_to_entry_id=')) return true
    if (
      target.includes('vendor_ledger_entry_id=')
      || target.includes('customer_ledger_entry_id=')
    ) {
      return true
    }
    const pageName = target.split('?', 1)[0]
    const targetPage = pages.find((p) => p.Name === pageName)
    if (targetPage?.PageType === 'Card' || targetPage?.PageType === 'Document') return true
    return Boolean(targetPage?.ContextFilterField)
  }

  const handleAction = (action: PageAction) => {
    const target = (action.ActionRelativeUrl || '').trim()
    if (disabled) return

    if (!target) {
      if (!selectedRecord) return
      onServerAction?.(action)
      return
    }

    if (target === '#new') {
      onNew?.()
      return
    }
    if (target === '#delete') {
      if (!deleteAllowed) return
      onDelete?.()
      return
    }
    if (target === '#stub') return
    if (target.startsWith('#')) {
      onHashAction?.(action)
      return
    }

    const selectionRequired = needsSelection(action)
    if (selectionRequired && !selectedRecord) return

    const targetPageName = target.split('?', 1)[0]
    const targetPage = pages.find((p) => p.Name === targetPageName)

    if (
      selectedRecord
      && targetPage
      && (targetPage.PageType === 'Card' || targetPage.PageType === 'Document')
    ) {
      router.push(
        getCardRecordPath(
          targetPage.PageId,
          String(selectedRecord.SystemId),
          targetPage.PageType,
          {
            fromList: String(getPageRouteId(page)),
            return: listReturnPath,
          },
        ),
      )
      return
    }

    if (selectedRecord) {
      const href = buildCardActionUrl(
        '/dashboard',
        target,
        pages,
        selectedRecord,
        sourceFields,
        listReturnPath,
      )
      if (href) {
        router.push(href)
        return
      }
    }

    if (targetPage?.PageType === 'List') {
      const listHref = buildListPageActionUrl('/dashboard', target, pages, listReturnPath)
      router.push(listHref ?? listDashboardPath(targetPage))
    }
  }

  const renderSearchControl = () => {
    if (searchOpen || search.trim()) {
      return (
        <div className="relative min-w-[200px] max-w-sm flex-1">
          <Search
            size={15}
            className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-s1"
          />
          <input
            ref={searchInputRef}
            type="search"
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            onBlur={() => {
              if (!search.trim()) setSearchOpen(false)
            }}
            placeholder="Search"
            className="h-8 w-full rounded border border-gray-200 bg-white py-1 pl-8 pr-2 text-sm text-mainTextColor focus:border-s1 focus:outline-none focus:ring-1 focus:ring-s1/30"
          />
        </div>
      )
    }

    return (
      <button
        type="button"
        onClick={() => setSearchOpen(true)}
        className="inline-flex items-center gap-2 rounded px-2 py-1.5 text-sm text-bodyText transition hover:bg-[#eef6f7] hover:text-s1"
      >
        <Search size={16} className="text-s1" strokeWidth={1.75} />
        <span>Search</span>
      </button>
    )
  }

  const renderActionButton = (action: PageAction) => {
    const imageUrl = action.ImageUrl?.trim()
    const assetUrl = imageUrl && isRibbonImageUrl(imageUrl) ? imageUrl : null
    const Icon = assetUrl ? null : resolveRibbonIcon(imageUrl)
    const target = (action.ActionRelativeUrl || '').trim()
    const selectionRequired = needsSelection(action)
    const actionDisabled =
      disabled
      || (target === '#delete' ? !deleteAllowed : selectionRequired && !selectedRecord)
      || action.ActionRelativeUrl === '#stub'

    return (
      <button
        key={action.ActionId}
        type="button"
        title={
          target === '#delete' && !deleteAllowed
            ? 'Select a row first'
            : selectionRequired && !selectedRecord
              ? 'Select a row first'
              : action.Tooltip ?? action.Caption
        }
        disabled={actionDisabled}
        onClick={() => handleAction(action)}
        className="inline-flex items-center gap-2 rounded px-2 py-1.5 text-sm text-bodyText transition hover:bg-[#eef6f7] hover:text-s1 disabled:cursor-not-allowed disabled:opacity-45"
      >
        {assetUrl ? (
          <img src={assetUrl} alt="" className="h-[18px] w-[18px] shrink-0 object-contain" />
        ) : Icon ? (
          <Icon className="h-[18px] w-[18px] shrink-0 text-s1" strokeWidth={1.75} />
        ) : null}
        <span>{action.Caption}</span>
      </button>
    )
  }

  return (
    <div className="shrink-0 border-b border-gray-200 bg-white">
      {hasTabs ? (
        <div className="flex border-b border-gray-100 bg-[#fafbfb] px-2 pt-1">
          {tabs.map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => setActiveTab(tab)}
              className={cn(
                'border-b-2 px-3 py-1.5 text-sm font-medium transition-colors',
                activeTab === tab
                  ? 'border-s1 text-s1'
                  : 'border-transparent text-bodyText hover:text-mainTextColor',
              )}
            >
              {tab}
            </button>
          ))}
        </div>
      ) : null}

      <div className="flex flex-wrap items-center gap-1 px-2 py-1.5">
        {renderSearchControl()}

        {showBuiltinNew ? (
          <button
            type="button"
            disabled={disabled}
            onClick={onNew}
            className="inline-flex items-center gap-2 rounded px-2 py-1.5 text-sm text-bodyText transition hover:bg-[#eef6f7] hover:text-s1 disabled:opacity-45"
          >
            <Plus size={16} className="text-s1" strokeWidth={1.75} />
            <span>New</span>
          </button>
        ) : null}

        {showEditList ? (
          <button
            type="button"
            disabled={disabled}
            onClick={onToggleEditList}
            title={editListMode ? 'Exit edit mode' : 'Edit rows directly in the list'}
            className={cn(
              'inline-flex items-center gap-2 rounded px-2 py-1.5 text-sm transition disabled:opacity-45',
              editListMode
                ? 'bg-[#eef6f7] text-s1 ring-1 ring-s1/30 font-medium'
                : 'text-bodyText hover:bg-[#eef6f7] hover:text-s1',
            )}
          >
            <PencilLine size={16} className="text-s1" strokeWidth={1.75} />
            <span>Edit List</span>
          </button>
        ) : null}

        {tabActions.map(renderActionButton)}

        {showBuiltinDelete ? (
          <button
            type="button"
            disabled={disabled}
            onClick={onDelete}
            className="inline-flex items-center gap-2 rounded px-2 py-1.5 text-sm text-bodyText transition hover:bg-[#eef6f7] hover:text-red-600 disabled:opacity-45"
          >
            <Trash2 size={16} className="text-s1" strokeWidth={1.75} />
            <span>Delete</span>
          </button>
        ) : null}
      </div>
    </div>
  )
}
