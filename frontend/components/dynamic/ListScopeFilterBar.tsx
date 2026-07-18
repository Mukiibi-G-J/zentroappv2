'use client'

import { useMemo } from 'react'
import { usePathname, useRouter, useSearchParams } from 'next/navigation'
import { cn } from '@/lib/utils'
import { buildListPageActionUrl } from '@/lib/listPageAction'
import { isListScopeActionActive } from '@/lib/listPageFilters'
import { buildListReturnPath } from '@/lib/pageRoutes'
import type { Page, PageAction } from '@/types/page'

interface Props {
  page: Page
  actions: PageAction[]
  allPages: Page[]
}

export default function ListScopeFilterBar({ page, actions, allPages }: Props) {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()

  const sortedActions = useMemo(
    () => [...actions].sort((a, b) => a.ActionId - b.ActionId),
    [actions],
  )

  const returnUrl = useMemo(
    () => buildListReturnPath(page, searchParams, pathname),
    [page, searchParams, pathname],
  )

  return (
    <div className="shrink-0 flex flex-wrap items-center gap-2">
      <span className="text-xs font-medium uppercase tracking-wide text-bodyText mr-1">
        Period
      </span>
      {sortedActions.map((action) => {
        const href = buildListPageActionUrl(
          '/dashboard',
          action.ActionRelativeUrl!,
          allPages,
          returnUrl,
        )
        const active = isListScopeActionActive(action.ActionRelativeUrl!, searchParams)

        return (
          <button
            key={action.ActionId}
            type="button"
            disabled={!href}
            title={action.Tooltip ?? action.Caption}
            onClick={() => {
              if (href) router.push(href)
            }}
            className={cn(
              'px-3 py-1.5 text-sm rounded-full border transition',
              active
                ? 'bg-s1 text-white border-s1 shadow-sm'
                : 'bg-white text-bodyText border-strokeColor hover:border-s1/40 hover:bg-[#eef5f5]',
              !href && 'opacity-50 cursor-not-allowed',
            )}
          >
            {action.Caption}
          </button>
        )
      })}
    </div>
  )
}
