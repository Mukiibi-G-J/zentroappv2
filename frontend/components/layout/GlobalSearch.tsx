'use client'

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
} from 'react'
import { useRouter } from 'next/navigation'
import {
  BookOpen,
  ChevronRight,
  FileText,
  Search,
  type LucideIcon,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useSession } from '@/context/SessionContext'
import { usePages } from '@/hooks/usePage'
import { usePageNavigation } from '@/hooks/usePageNavigation'
import { getCardRecordPath } from '@/lib/pageRoutes'
import { resolveRibbonIcon } from '@/lib/ribbonIcon'
import {
  flattenSections,
  mapApiRecordSections,
  searchNavPages,
} from '@/lib/globalSearchPages'
import { searchService } from '@/services/search.service'
import type { GlobalSearchItem, GlobalSearchSection } from '@/types/search'

const CATEGORY_ICONS: Record<string, LucideIcon> = {
  Inventory: BookOpen,
  Sales: FileText,
  Purchases: FileText,
  Financials: BookOpen,
  Payments: FileText,
}

function highlightMatch(text: string, query: string) {
  const q = query.trim()
  if (!q) return text

  const lowerText = text.toLowerCase()
  const lowerQuery = q.toLowerCase()
  const index = lowerText.indexOf(lowerQuery)
  if (index === -1) return text

  return (
    <>
      {text.slice(0, index)}
      <mark className="rounded bg-s2/40 px-0.5 text-mainTextColor">{text.slice(index, index + q.length)}</mark>
      {text.slice(index + q.length)}
    </>
  )
}

function resolveItemIcon(item: GlobalSearchItem): LucideIcon {
  if (item.imageUrl) return resolveRibbonIcon(item.imageUrl)
  if (item.iconKey && CATEGORY_ICONS[item.iconKey]) {
    return CATEGORY_ICONS[item.iconKey]
  }
  if (item.categoryTitle && CATEGORY_ICONS[item.categoryTitle]) {
    return CATEGORY_ICONS[item.categoryTitle]
  }
  return BookOpen
}

interface SearchPaletteProps {
  open: boolean
  onClose: () => void
}

function SearchPalette({ open, onClose }: SearchPaletteProps) {
  const router = useRouter()
  const { session } = useSession()
  const { data: pages = [] } = usePages()
  const { navigateToPageName } = usePageNavigation()
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLDivElement>(null)

  const [query, setQuery] = useState('')
  const [recordSections, setRecordSections] = useState<GlobalSearchSection[]>([])
  const [loadingRecords, setLoadingRecords] = useState(false)
  const [selectedIndex, setSelectedIndex] = useState(0)

  const pageSections = useMemo(
    () => searchNavPages(query, session?.navItems ?? [], pages),
    [query, session?.navItems, pages],
  )

  const sections = useMemo(
    () => [...pageSections, ...recordSections],
    [pageSections, recordSections],
  )

  const flatItems = useMemo(() => flattenSections(sections), [sections])

  const resetState = useCallback(() => {
    setQuery('')
    setRecordSections([])
    setLoadingRecords(false)
    setSelectedIndex(0)
  }, [])

  const handleClose = useCallback(() => {
    onClose()
    resetState()
  }, [onClose, resetState])

  useEffect(() => {
    if (!open) return
    const timer = setTimeout(() => inputRef.current?.focus(), 50)
    return () => clearTimeout(timer)
  }, [open])

  useEffect(() => {
    if (!open) return

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        handleClose()
      }
    }

    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [open, handleClose])

  useEffect(() => {
    setSelectedIndex(0)
  }, [query, sections.length])

  useEffect(() => {
    const trimmed = query.trim()
    if (!trimmed) {
      setRecordSections([])
      setLoadingRecords(false)
      return
    }

    let cancelled = false
    setLoadingRecords(true)

    const timer = setTimeout(async () => {
      try {
        const apiSections = await searchService.globalSearch(trimmed)
        if (cancelled) return
        setRecordSections(mapApiRecordSections(apiSections))
      } catch {
        if (!cancelled) setRecordSections([])
      } finally {
        if (!cancelled) setLoadingRecords(false)
      }
    }, 250)

    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [query])

  useEffect(() => {
    if (!listRef.current) return
    const active = listRef.current.querySelector('[data-active="true"]')
    active?.scrollIntoView({ block: 'nearest' })
  }, [selectedIndex])

  const handleSelect = useCallback(
    async (item: GlobalSearchItem) => {
      handleClose()

      const pageMeta = pages.find((p) => p.Name === item.pageName)
      if (
        item.systemId &&
        pageMeta &&
        (pageMeta.PageType === 'Card' || pageMeta.PageType === 'Document')
      ) {
        router.push(getCardRecordPath(pageMeta.PageId, item.systemId, pageMeta.PageType))
        return
      }

      await navigateToPageName(item.pageName)
    },
    [handleClose, navigateToPageName, pages, router],
  )

  const handleInputKeyDown = (event: ReactKeyboardEvent<HTMLInputElement>) => {
    if (flatItems.length === 0) return

    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setSelectedIndex((prev) => (prev + 1) % flatItems.length)
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setSelectedIndex((prev) => (prev - 1 + flatItems.length) % flatItems.length)
    } else if (event.key === 'Enter') {
      event.preventDefault()
      const item = flatItems[selectedIndex]
      if (item) void handleSelect(item)
    }
  }

  if (!open) return null

  let runningIndex = -1

  return (
    <div className="fixed inset-0 z-[100] flex items-start justify-center bg-black/40 px-4 pt-[12vh]">
      <button
        type="button"
        className="absolute inset-0 cursor-default"
        aria-label="Close search"
        onClick={handleClose}
      />

      <div
        role="dialog"
        aria-modal="true"
        aria-label="Global search"
        className="relative z-10 w-full max-w-2xl overflow-hidden rounded-xl border border-strokeColor bg-white shadow-2xl"
      >
        <div className="flex items-center gap-3 border-b border-strokeColor px-4">
          <Search className="h-5 w-5 shrink-0 text-bodyText" aria-hidden />
          <input
            ref={inputRef}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={handleInputKeyDown}
            placeholder="Search pages, customers, items, accounts…"
            className="flex-1 border-0 bg-transparent py-4 text-base text-mainTextColor outline-none placeholder:text-bodyText/70"
          />
          {loadingRecords && (
            <span className="text-xs text-bodyText">Searching…</span>
          )}
          <button
            type="button"
            onClick={handleClose}
            className="rounded-md border border-strokeColor px-2 py-1 text-xs text-bodyText hover:bg-softBg"
          >
            Esc
          </button>
        </div>

        <div ref={listRef} className="max-h-[min(60vh,520px)] overflow-y-auto px-3 py-4">
          {sections.length === 0 && query.trim() && !loadingRecords ? (
            <div className="px-3 py-10 text-center">
              <p className="text-sm text-bodyText">
                No results for{' '}
                <span className="font-semibold text-mainTextColor">&ldquo;{query}&rdquo;</span>
              </p>
              <p className="mt-1 text-xs text-bodyText/80">
                Try a page name, customer, item number, or G/L account.
              </p>
            </div>
          ) : (
            sections.map((section) => (
              <div key={section.title} className="mb-5 last:mb-0">
                <h3 className="mb-2 px-2 text-xs font-semibold uppercase tracking-wide text-bodyText">
                  {section.title}
                </h3>
                <div className="space-y-1">
                  {section.items.map((item) => {
                    runningIndex += 1
                    const itemIndex = runningIndex
                    const isActive = itemIndex === selectedIndex
                    const Icon = resolveItemIcon(item)

                    return (
                      <button
                        key={item.id}
                        type="button"
                        data-active={isActive ? 'true' : undefined}
                        onMouseEnter={() => setSelectedIndex(itemIndex)}
                        onClick={() => void handleSelect(item)}
                        className={cn(
                          'flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left transition-colors',
                          isActive ? 'bg-softBg2 ring-1 ring-s2/40' : 'hover:bg-softBg',
                        )}
                      >
                        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-strokeColor bg-white text-p1">
                          <Icon className="h-4 w-4" aria-hidden />
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-sm font-medium text-mainTextColor">
                            {highlightMatch(item.title, query)}
                          </span>
                          {item.description && (
                            <span className="mt-0.5 block truncate text-xs text-bodyText">
                              {highlightMatch(item.description, query)}
                            </span>
                          )}
                        </span>
                        <span className="hidden shrink-0 items-center gap-1 text-xs text-bodyText sm:flex">
                          {item.kind === 'record' ? 'Record' : 'Page'}
                          <ChevronRight className="h-3.5 w-3.5" aria-hidden />
                        </span>
                      </button>
                    )
                  })}
                </div>
              </div>
            ))
          )}
        </div>

        <div className="flex items-center justify-between border-t border-strokeColor bg-softBg px-4 py-2 text-xs text-bodyText">
          <span>Use ↑ ↓ to navigate, Enter to open</span>
          <span className="hidden sm:inline">Ctrl+K</span>
        </div>
      </div>
    </div>
  )
}

interface GlobalSearchProps {
  className?: string
}

export function GlobalSearch({ className }: GlobalSearchProps) {
  const [open, setOpen] = useState(false)

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setOpen((prev) => !prev)
      }
    }

    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [])

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className={cn(
          'flex items-center gap-2 rounded-lg border border-strokeColor bg-white px-3 py-2 text-sm text-bodyText transition-colors hover:border-s2/60 hover:bg-softBg md:hidden',
          className,
        )}
        aria-label="Open search"
      >
        <Search className="h-4 w-4" />
        Search
      </button>

      <button
        type="button"
        onClick={() => setOpen(true)}
        className={cn(
          'relative hidden w-full cursor-text rounded-lg border border-strokeColor bg-white text-left transition-colors hover:border-s2/60 md:block',
          className,
        )}
        aria-label="Open search (Ctrl+K)"
      >
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-bodyText" />
        <span className="block w-full py-2 pl-10 pr-16 text-sm text-bodyText/70">
          Search pages, records…
        </span>
        <kbd className="absolute right-3 top-1/2 hidden -translate-y-1/2 rounded border border-strokeColor bg-softBg px-1.5 py-0.5 text-[10px] font-medium text-bodyText lg:inline">
          Ctrl+K
        </kbd>
      </button>

      <SearchPalette open={open} onClose={() => setOpen(false)} />
    </>
  )
}
