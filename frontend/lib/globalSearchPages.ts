import type { AuthNavItem } from '@/types/auth'
import type { Page } from '@/types/page'
import type { ApiGlobalSearchSection, GlobalSearchItem, GlobalSearchSection } from '@/types/search'

const QUICK_ACCESS_LIMIT = 8

const SEARCHABLE_PAGE_TYPES = new Set(['List', 'Worksheet', 'Document', 'Card', 'RoleCenter'])

/** Extra keywords so users can find pages by common phrases (not just page Name). */
const PAGE_SEARCH_ALIASES: Record<string, string[]> = {
  InventoryAdjustmentJournalList: [
    'inventory adjustment',
    'adjust inventory',
    'item journal',
    'stock adjustment',
  ],
  PermissionSetsList: [
    'permission set',
    'permission sets',
    'permissions',
    'security',
    'access control',
  ],
  UserGroupsList: [
    'user group',
    'user groups',
    'security group',
    'security groups',
  ],
  OpeningBalanceJournalList: [
    'opening balance',
    'opening balance journal',
    'opening stock',
    'initial stock',
  ],
  FinancialReportList: ['financial report', 'financial reports', 'account schedule', 'p&l', 'income statement'],
  FinancialReportOverview: ['financial report overview', 'acc schedule overview', 'run report'],
  FinancialReportRowGroupList: ['row definition', 'account schedule line'],
  FinancialReportRowDefinition: ['row definition', 'account schedule', 'acc schedule'],
  FinancialReportColumnGroupList: ['column definition'],
  ItemJournalCard: ['item journal'],
}

function matchesQuery(query: string, parts: Array<string | undefined | null>): boolean {
  const q = query.trim().toLowerCase()
  if (!q) return true
  const haystack = parts.filter(Boolean).join(' ').toLowerCase()
  return haystack.includes(q)
}

export function searchNavPages(
  query: string,
  navItems: AuthNavItem[],
  pages: Page[],
): GlobalSearchSection[] {
  const items: GlobalSearchItem[] = []
  const seen = new Set<string>()

  for (const nav of navItems) {
    if (nav.desktopOnly) continue
    const pageName = nav.targetPageName?.trim()
    if (!pageName || seen.has(pageName)) continue

    const page = pages.find((p) => p.Name === pageName)
    const title = nav.caption?.trim() || page?.Caption || pageName
    const description =
      page?.Caption && page.Caption !== title
        ? page.Caption
        : page?.SourceTable?.replace(/_/g, ' ')

    if (
      !matchesQuery(query, [
        title,
        pageName,
        page?.Caption,
        page?.SourceTable,
        nav.ribbonTab,
      ])
    ) {
      continue
    }

    seen.add(pageName)
    items.push({
      id: `page:${pageName}`,
      kind: 'page',
      title,
      description,
      categoryTitle: nav.ribbonTab?.trim() || 'Navigation',
      pageName,
      imageUrl: nav.imageUrl,
    })

    if (!query.trim() && items.length >= QUICK_ACCESS_LIMIT) break
  }

  // Also search the full page catalog (not only current Role Centre nav).
  const q = query.trim()
  if (q) {
    for (const page of pages) {
      const pageName = page.Name?.trim()
      if (!pageName || seen.has(pageName)) continue
      if (!SEARCHABLE_PAGE_TYPES.has(page.PageType ?? '')) continue

      const aliases = PAGE_SEARCH_ALIASES[pageName] ?? []
      if (
        !matchesQuery(q, [
          pageName,
          page.Caption,
          page.SourceTable,
          ...aliases,
        ])
      ) {
        continue
      }

      seen.add(pageName)
      items.push({
        id: `page:${pageName}`,
        kind: 'page',
        title: page.Caption?.trim() || pageName,
        description: page.SourceTable?.replace(/_/g, ' '),
        categoryTitle: 'Pages',
        pageName,
      })
    }
  }

  if (items.length === 0) return []

  return [
    {
      title: query.trim() ? 'Pages' : 'Quick access',
      items,
    },
  ]
}

export function mapApiRecordSections(
  sections: ApiGlobalSearchSection[],
): GlobalSearchSection[] {
  return sections
    .map((section) => ({
      title: section.title,
      items: section.data
        .filter((row) => row.pageName)
        .map((row, index) => ({
          id: `record:${row.pageName}:${row.systemId ?? row.title}:${index}`,
          kind: 'record' as const,
          title: row.title,
          description: row.description,
          categoryTitle: row.categoryTitle ?? section.title,
          pageName: row.pageName!,
          systemId: row.systemId,
          iconKey: row.icon,
        })),
    }))
    .filter((section) => section.items.length > 0)
}

export function flattenSections(sections: GlobalSearchSection[]): GlobalSearchItem[] {
  return sections.flatMap((section) => section.items)
}
