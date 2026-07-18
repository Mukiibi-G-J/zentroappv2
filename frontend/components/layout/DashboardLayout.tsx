'use client'

import { Suspense, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { Sidebar } from './Sidebar'
import { DashboardHeader } from './DashboardHeader'
import { POSFullscreenShell } from '@/components/pos/POSFullscreenShell'
import { BranchSelectModal } from '@/components/auth/BranchSelectModal'
import { usePages } from '@/hooks/usePage'
import { resolvePageFromRouteParam } from '@/lib/pageRoutes'
import { cn } from '@/lib/utils'

function SidebarFallback({ collapsed }: { collapsed?: boolean }) {
  return (
    <div
      className={cn(
        'flex h-full min-h-0 flex-col bg-white border-r border-strokeColor',
        collapsed ? 'w-16' : 'w-64',
      )}
    >
      <div className="h-16 border-b border-strokeColor" />
      <div className="flex-1 min-h-0 p-3 space-y-2">
        {[...Array(5)].map((_, i) => (
          <div
            key={i}
            className="h-9 bg-softBg rounded-lg animate-pulse"
            style={{ opacity: 1 - i * 0.15 }}
          />
        ))}
      </div>
    </div>
  )
}

interface DashboardLayoutProps {
  children: React.ReactNode
  title?: string
}

function DashboardLayoutInner({ children, title }: DashboardLayoutProps) {
  const searchParams = useSearchParams()
  const routeParam = parseInt(searchParams.get('page') ?? '0', 10)
  const { data: pages = [] } = usePages()
  const resolved = routeParam > 0 ? resolvePageFromRouteParam(pages, routeParam) : undefined
  const page = resolved ? pages.find((p) => p.PageId === resolved.PageId) : undefined
  const isFullscreenPos = page?.PageType === 'POS'

  if (isFullscreenPos) {
    return (
      <POSFullscreenShell title={page?.Caption ?? 'Point of Sale'}>{children}</POSFullscreenShell>
    )
  }

  return <StandardDashboardLayout title={title}>{children}</StandardDashboardLayout>
}

function StandardDashboardLayout({ children, title }: DashboardLayoutProps) {
  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)

  return (
    <div className="flex h-screen bg-softBg">
      <div className={cn('hidden h-full min-h-0 lg:flex', mobileOpen && 'lg:hidden')}>
        <Suspense fallback={<SidebarFallback collapsed={collapsed} />}>
          <Sidebar collapsed={collapsed} onToggle={() => setCollapsed((c) => !c)} />
        </Suspense>
      </div>

      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      <div
        className={cn(
          'fixed inset-y-0 left-0 z-50 w-64 transform transition-transform duration-300 ease-in-out lg:hidden',
          mobileOpen ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        <Suspense fallback={<SidebarFallback />}>
          <Sidebar collapsed={false} onToggle={() => setMobileOpen(false)} />
        </Suspense>
      </div>

      <div className="flex flex-1 flex-col overflow-hidden">
        <DashboardHeader title={title} onMenuToggle={() => setMobileOpen((o) => !o)} />
        <main className="flex min-h-0 flex-1 flex-col overflow-hidden">
          <div className="flex min-h-0 flex-1 flex-col overflow-hidden p-6">{children}</div>
        </main>
      </div>
    </div>
  )
}

function DashboardLayoutShellFallback({ children, title }: DashboardLayoutProps) {
  return <StandardDashboardLayout title={title}>{children}</StandardDashboardLayout>
}

export function DashboardLayout({ children, title }: DashboardLayoutProps) {
  return (
    <>
      <BranchSelectModal />
      <Suspense fallback={<DashboardLayoutShellFallback title={title}>{children}</DashboardLayoutShellFallback>}>
        <DashboardLayoutInner title={title}>{children}</DashboardLayoutInner>
      </Suspense>
    </>
  )
}
