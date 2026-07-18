'use client'

import dynamic from 'next/dynamic'
import { useMemo } from 'react'
import { usePage } from '@/hooks/usePage'
import { useSalesPOS } from '@/hooks/useSalesPOS'
import { useIsMobilePos } from '@/hooks/useMediaQuery'
import { POSDesktop } from '@/components/pos/POSDesktop'
import { POSMobile } from '@/components/pos/POSMobile'

const pageLoading = () => <div className="h-32 animate-pulse rounded-xl bg-gray-100" />

const RestaurantPOSPage = dynamic(
  () => import('@/components/restaurant/RestaurantPOSPage'),
  { loading: pageLoading },
)
const MenuBuilderPage = dynamic(
  () => import('@/components/restaurant/MenuBuilderPage'),
  { loading: pageLoading },
)
const KitchenDisplayPage = dynamic(
  () => import('@/components/restaurant/KitchenDisplayPage'),
  { loading: pageLoading },
)

interface DynamicPOSPageProps {
  pageId: number
}

export default function DynamicPOSPage({ pageId }: DynamicPOSPageProps) {
  const { data: page, isLoading } = usePage(pageId)
  const isMobile = useIsMobilePos()

  if (isLoading) {
    return <div className="h-32 animate-pulse rounded-xl bg-gray-100" />
  }

  if (page?.Name === 'RestaurantPOS') {
    return <RestaurantPOSPage />
  }

  if (page?.Name === 'MenuBuilder') {
    return <MenuBuilderPage />
  }

  if (page?.Name === 'KitchenDisplay') {
    return <KitchenDisplayPage />
  }

  return <SalesPOSPage pageId={pageId} isMobile={isMobile} />
}

function SalesPOSPage({ pageId, isMobile }: { pageId: number; isMobile: boolean }) {
  const { data: page } = usePage(pageId)

  const productPart = useMemo(
    () => page?.PageControls?.find((c) => c.Name === 'POSProductGrid'),
    [page?.PageControls],
  )
  const itemListPageId = productPart?.PartPageId ?? undefined
  const itemListControlId = productPart?.PartPage?.PageControls?.find(
    (c) => c.ControlType === 'Repeater',
  )?.PageControlId

  const pos = useSalesPOS(itemListPageId ?? undefined, itemListControlId ?? undefined)
  const pageActions = page?.PageActions ?? []

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-hidden">
      {isMobile ? (
        <POSMobile pos={pos} pageActions={pageActions} />
      ) : (
        <POSDesktop pos={pos} pageActions={pageActions} />
      )}
    </div>
  )
}
