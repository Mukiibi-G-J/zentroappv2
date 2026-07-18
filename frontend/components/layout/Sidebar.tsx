'use client'

import { useMemo } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { ChevronLeft, ChevronRight, type LucideIcon } from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import { usePages } from '@/hooks/usePage'
import { useSession } from '@/context/SessionContext'
import { pageDataService } from '@/services/pagedata.service'
import { getCardRecordPath, listDashboardPath, resolveListPageForCard, resolvePageFromRouteParam } from '@/lib/pageRoutes'
import { isSetupSingletonCardPage } from '@/lib/setupPages'
import { resolveRibbonIcon } from '@/lib/ribbonIcon'
import type { AuthNavItem } from '@/types/auth'
import type { Page } from '@/types/page'

interface SidebarProps {
  collapsed: boolean
  onToggle: () => void
}

interface NavEntry {
  key: string
  label: string
  pageName: string | null
  icon: LucideIcon
  group: string
}

const NAV_GROUP_ORDER = [
  'General',
  'Inventory',
  'Sales',
  'Purchase',
  'Finance',
  'Administration',
] as const

function navItemToPageName(item: AuthNavItem): string | null {
  const target = item.targetPageName?.trim()
  if (!target) return null
  return target
}

function toNavEntry(item: AuthNavItem): NavEntry {
  const ribbonTab = item.ribbonTab?.trim() || 'Navigation'
  const group =
    ribbonTab === 'Setup' || ribbonTab === 'Navigation' ? 'General' : ribbonTab
  return {
    key: item.name,
    label: item.caption,
    pageName: navItemToPageName(item),
    icon: resolveRibbonIcon(item.imageUrl),
    group,
  }
}

function groupNavEntries(items: NavEntry[]): { label: string; items: NavEntry[] }[] {
  const byGroup = new Map<string, NavEntry[]>()
  for (const entry of items) {
    const list = byGroup.get(entry.group) ?? []
    list.push(entry)
    byGroup.set(entry.group, list)
  }

  const groups: { label: string; items: NavEntry[] }[] = []
  for (const label of NAV_GROUP_ORDER) {
    const groupItems = byGroup.get(label)
    if (groupItems?.length) {
      groups.push({ label, items: groupItems })
      byGroup.delete(label)
    }
  }
  for (const [label, groupItems] of [...byGroup.entries()].sort(([a], [b]) => a.localeCompare(b))) {
    groups.push({ label, items: groupItems })
  }
  return groups
}

export function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { data: pages = [] } = usePages()
  const routeParam = parseInt(searchParams.get('page') ?? '0')
  const currentPage = resolvePageFromRouteParam(pages, routeParam)
  const { session, isReady } = useSession()

  const { mainNavGroups, setupNavItems } = useMemo(() => {
    const main: NavEntry[] = []
    const setup: NavEntry[] = []
    for (const item of session?.navItems ?? []) {
      // Desktop-only entries (e.g. Sync Queue) belong in Electron, not web.
      if (item.desktopOnly) continue
      const entry = toNavEntry(item)
      if (item.ribbonTab === 'Setup') setup.push(entry)
      else main.push(entry)
    }
    return {
      mainNavGroups: groupNavEntries(main),
      setupNavItems: setup,
    }
  }, [session?.navItems])

  const resolvePage = (pageName: string | null) => {
    if (!pageName) return undefined
    return pages.find((p) => p.Name === pageName)
  }

  const navigate = async (pageName: string | null) => {
    if (!pageName) {
      router.push('/dashboard')
      return
    }

    const pageMeta = resolvePage(pageName)
    if (!pageMeta) {
      toast.error(`Page "${pageName}" is not available`)
      return
    }

    if (isSetupSingletonCardPage(pageMeta)) {
      try {
        const systemId = await pageDataService.getSetupSolo(pageMeta.PageId)
        router.push(getCardRecordPath(pageMeta.PageId, systemId, pageMeta?.PageType))
      } catch (err) {
        toast.error(err instanceof Error ? err.message : 'Could not open page')
      }
      return
    }

    if (pageMeta.PageType === 'Card') {
      const listPage = resolveListPageForCard(pages, pageMeta)
      if (listPage) {
        router.push(listDashboardPath(listPage))
        return
      }
    }

    router.push(listDashboardPath(pageMeta))
  }

  const renderItem = ({ key, label, pageName, icon: Icon }: NavEntry) => {
    const pageMeta = resolvePage(pageName)
    const isActive =
      pageName === null
        ? routeParam === 0
        : !!pageMeta && currentPage?.PageId === pageMeta.PageId
    const isDisabled = !!pageName && !pageMeta

    if (collapsed) {
      return (
        <div key={key} className="relative group">
          <button
            onClick={() => navigate(pageName)}
            disabled={isDisabled}
            className={cn(
              'w-full flex justify-center items-center p-3 rounded-lg transition-colors',
              isActive
                ? 'bg-s1 text-white'
                : 'text-bodyText hover:bg-softBg hover:text-mainTextColor',
              isDisabled && 'opacity-40 cursor-not-allowed',
            )}
          >
            <Icon className="w-5 h-5 shrink-0" />
            <span className="sr-only">{label}</span>
          </button>
          <div className="absolute left-full ml-2 top-1/2 -translate-y-1/2 z-50 hidden group-hover:block pointer-events-none">
            <div className="bg-gray-900 text-white text-xs rounded px-2 py-1 whitespace-nowrap">
              {label}
            </div>
          </div>
        </div>
      )
    }

    return (
      <button
        key={key}
        onClick={() => navigate(pageName)}
        disabled={isDisabled}
        className={cn(
          'w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors focus:outline-none',
          isActive
            ? 'bg-s1 text-white'
            : 'text-bodyText hover:bg-softBg hover:text-mainTextColor',
          isDisabled && 'opacity-40 cursor-not-allowed',
        )}
        aria-current={isActive ? 'page' : undefined}
      >
        <Icon className="w-5 h-5 shrink-0" />
        <span className="truncate">{label}</span>
      </button>
    )
  }

  const renderNavSection = (items: NavEntry[]) => {
    if (items.length === 0) return null
    return items.map(renderItem)
  }

  const renderNavGroup = (
    { label, items }: { label: string; items: NavEntry[] },
    index: number,
  ) => (
    <div key={label}>
      {!collapsed && label !== 'General' && (
        <div className={cn('pb-1 px-3', index === 0 ? 'pt-1' : 'pt-3')}>
          <span className="text-[10px] font-semibold uppercase tracking-wider text-bodyText/50">
            {label}
          </span>
        </div>
      )}
      {collapsed && index > 0 && <div className="my-2 border-t border-strokeColor" />}
      {renderNavSection(items)}
    </div>
  )

  const showSession = isReady
  const userInitial =
    showSession && session?.user.fullName
      ? session.user.fullName.charAt(0).toUpperCase()
      : 'U'
  const userName =
    showSession && session?.user.fullName ? session.user.fullName : 'User'
  const userRole = showSession
    ? session?.profile?.description || session?.user.role || 'User'
    : 'User'

  return (
    <div
      className={cn(
        'flex h-full min-h-0 flex-col bg-white border-r border-strokeColor transition-all duration-300',
        collapsed ? 'w-16' : 'w-64',
      )}
    >
      <div
        className={cn(
          'flex shrink-0 border-b border-strokeColor',
          collapsed
            ? 'flex-col items-center gap-1 px-2 py-2'
            : 'h-16 items-center justify-between px-4',
        )}
      >
        {collapsed ? (
          <>
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-s1">
              <span className="text-sm font-bold text-white">Z</span>
            </div>
            <button
              onClick={onToggle}
              className="flex w-full justify-center rounded-lg p-2 transition-colors hover:bg-softBg"
              aria-label="Expand sidebar"
            >
              <ChevronRight className="h-4 w-4 text-bodyText" />
            </button>
          </>
        ) : (
          <>
            <div className="flex min-w-0 items-center gap-2">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-s1">
                <span className="text-sm font-bold text-white">Z</span>
              </div>
              <span className="truncate font-semibold text-mainTextColor">ZentroApp</span>
            </div>
            <button
              onClick={onToggle}
              className="shrink-0 rounded-lg p-2 transition-colors hover:bg-softBg"
              aria-label="Collapse sidebar"
            >
              <ChevronLeft className="h-4 w-4 text-bodyText" />
            </button>
          </>
        )}
      </div>

      <nav
        className={cn(
          'min-h-0 flex-1 overflow-y-auto py-4',
          collapsed ? 'px-2 space-y-1' : 'px-3 space-y-0.5',
        )}
        role="navigation"
        aria-label="Main navigation"
      >
        {!isReady && (
          <p className={cn('text-xs text-bodyText/60', collapsed ? 'text-center px-1' : 'px-3 py-2')}>
            {collapsed ? '…' : 'Loading navigation…'}
          </p>
        )}

        {isReady && mainNavGroups.length === 0 && setupNavItems.length === 0 && (
          <p className={cn('text-xs text-bodyText/60', collapsed ? 'text-center px-1' : 'px-3 py-2')}>
            {collapsed ? '—' : 'No navigation for your role. Set Role Centre in User settings.'}
          </p>
        )}

        {mainNavGroups.map(renderNavGroup)}

        {setupNavItems.length > 0 && !collapsed && (
          <div className="pt-3 pb-1 px-3">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-bodyText/50">
              Setup
            </span>
          </div>
        )}
        {setupNavItems.length > 0 && collapsed && <div className="my-2 border-t border-strokeColor" />}

        {renderNavSection(setupNavItems)}
      </nav>

      {!collapsed && (
        <div className="shrink-0 border-t border-strokeColor p-4">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-softBg2 text-s1 rounded-full flex items-center justify-center shrink-0">
              <span className="text-xs font-semibold">{userInitial}</span>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-mainTextColor truncate">{userName}</p>
              <p className="text-xs text-bodyText truncate">{userRole}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
