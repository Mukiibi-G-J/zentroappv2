'use client'

import { Suspense } from 'react'
import { useSearchParams } from 'next/navigation'
import { usePage, usePages } from '@/hooks/usePage'
import { resolvePageFromRouteParam, resolveListPageForCard } from '@/lib/pageRoutes'
import { useSession } from '@/context/SessionContext'
import DynamicListPage from '@/components/dynamic/DynamicListPage'
import DynamicWorksheetPage from '@/components/dynamic/DynamicWorksheetPage'
import DynamicRoleCentre from '@/components/dynamic/DynamicRoleCentre'
import DynamicPOSPage from '@/components/dynamic/DynamicPOSPage'
import DocumentDashboardRouter from '@/components/dynamic/DocumentDashboardRouter'
import KitchenDisplayPage from '@/components/restaurant/KitchenDisplayPage'

function PageRouter({ pageId }: { pageId: number }) {
  const { data: page, isLoading } = usePage(pageId)
  const { data: pages = [] } = usePages()

  if (isLoading) return <div className="h-32 animate-pulse rounded-xl bg-gray-100" />

  if (page?.Name === 'KitchenDisplayList') {
    return <KitchenDisplayPage />
  }

  if (page?.PageType === 'Card') {
    const listPage = resolveListPageForCard(pages, page)
    if (listPage) {
      return <DynamicListPage pageId={listPage.PageId} />
    }
  }

  switch (page?.PageType) {
    case 'Document':
      return <DocumentDashboardRouter pageId={pageId} />
    case 'Worksheet':
      return <DynamicWorksheetPage pageId={pageId} />
    case 'RoleCenter':
      return <DynamicRoleCentre pageId={pageId} />
    case 'POS':
      return <DynamicPOSPage pageId={pageId} />
    default:
      return <DynamicListPage pageId={pageId} />
  }
}

function HomeOrRoleCentre() {
  const { session, isReady } = useSession()
  const { data: pages = [], isLoading } = usePages()

  if (!isReady || isLoading) {
    return <div className="h-32 animate-pulse rounded-xl bg-gray-100" />
  }

  const rcPageId = session?.roleCentrePageId
  if (rcPageId) {
    return <DynamicRoleCentre pageId={rcPageId} />
  }

  const rcPage = pages.find((p) => p.PageType === 'RoleCenter')
  if (rcPage) return <DynamicRoleCentre pageId={rcPage.PageId} />
  return <HomeDashboard />
}

function PageContent() {
  const searchParams = useSearchParams()
  const { data: pages = [], isLoading } = usePages()
  const routeParam = parseInt(searchParams.get('page') ?? '0')

  if (routeParam > 0) {
    if (isLoading) {
      return <div className="h-32 animate-pulse rounded-xl bg-gray-100" />
    }
    const resolved = resolvePageFromRouteParam(pages, routeParam)
    return <PageRouter pageId={resolved?.PageId ?? routeParam} />
  }
  return <HomeOrRoleCentre />
}

export default function DashboardPage() {
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <Suspense fallback={<div className="h-32 animate-pulse rounded-xl bg-gray-100" />}>
        <PageContent />
      </Suspense>
    </div>
  )
}

function HomeDashboard() {
  return (
    <div className="flex-1 min-h-0 overflow-y-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-mainTextColor">Dashboard</h1>
        <p className="text-sm text-bodyText mt-1">Welcome to ZentroApp</p>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {['Items', 'Customers', 'Vendors'].map((module) => (
          <div key={module} className="rounded-xl bg-white border border-strokeColor p-5 shadow-sm">
            <p className="text-sm font-medium text-bodyText">{module}</p>
            <p className="mt-1 text-2xl font-semibold text-mainTextColor">—</p>
          </div>
        ))}
      </div>
    </div>
  )
}
