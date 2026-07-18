'use client'

import { useRouter } from 'next/navigation'
import { Package, Users } from 'lucide-react'
import { usePages } from '@/hooks/usePage'
import { getCardRecordPath, listDashboardPathByPageId } from '@/lib/pageRoutes'
import type { BrickCard, RoleCentreSection } from '@/types/page'

interface Props {
  section: RoleCentreSection
}

function BrickCardTile({
  card,
  icon: Icon,
}: {
  card: BrickCard
  icon: typeof Package
}) {
  const router = useRouter()
  const { data: pages = [] } = usePages()
  const cardPage = card.CardPageId ? pages.find((p) => p.PageId === card.CardPageId) : null

  const handleClick = () => {
    if (card.CardPageId && card.SystemId) {
      router.push(getCardRecordPath(card.CardPageId, card.SystemId, cardPage?.PageType ?? null))
      return
    }
    if (card.ListPageId) {
      router.push(listDashboardPathByPageId(pages, card.ListPageId))
    }
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      className="flex items-start gap-3 rounded-lg border border-strokeColor bg-white p-4 text-left hover:border-s1/40 hover:shadow-sm transition w-full"
    >
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-s1/10 text-s1">
        <Icon size={18} />
      </div>
      <div className="min-w-0">
        <p className="text-sm font-semibold text-mainTextColor truncate">{card.Title}</p>
        <p className="text-xs text-bodyText mt-0.5">{card.Subtitle}</p>
      </div>
    </button>
  )
}

export default function BrickSection({ section }: Props) {
  const bricks = section.Bricks
  if (!bricks) return null

  return (
    <div className="space-y-4">
      <div className="border-b border-strokeColor pb-2">
        <h3 className="text-sm font-semibold text-mainTextColor">{section.Caption}</h3>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="space-y-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-bodyText">Top Items</p>
          <div className="space-y-2">
            {bricks.Items.length === 0 ? (
              <p className="text-sm text-bodyText px-1">No items</p>
            ) : (
              bricks.Items.map((card) => (
                <BrickCardTile key={card.SystemId} card={card} icon={Package} />
              ))
            )}
          </div>
        </div>
        <div className="space-y-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-bodyText">Top Customers</p>
          <div className="space-y-2">
            {bricks.Customers.length === 0 ? (
              <p className="text-sm text-bodyText px-1">No customers</p>
            ) : (
              bricks.Customers.map((card) => (
                <BrickCardTile key={card.SystemId} card={card} icon={Users} />
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
