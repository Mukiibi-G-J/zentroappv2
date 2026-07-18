'use client'

import { useEffect, useMemo, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { usePage, usePages } from '@/hooks/usePage'
import {
  getCardRecordPath,
  getPageRouteId,
  listDashboardPath,
  resolveListPageForDocument,
} from '@/lib/pageRoutes'
import { pageDataService } from '@/services/pagedata.service'

interface Props {
  pageId: number
}

/**
 * Document pages must not render as DynamicListPage on /dashboard.
 * Legacy drill-down URLs used ?page=<docObjectId>&ctx=<no>; resolve those to /document/…
 * or send the user to the linked list page.
 */
export default function DocumentDashboardRouter({ pageId }: Props) {
  const router = useRouter()
  const searchParams = useSearchParams()
  const ctx = searchParams.get('ctx')
  const { data: page, isLoading: pageLoading } = usePage(pageId)
  const { data: pages = [] } = usePages()
  const [lookupFailed, setLookupFailed] = useState(false)

  const listPage = useMemo(
    () => (page ? resolveListPageForDocument(pages, page) : undefined),
    [page, pages],
  )

  const listControlId = useMemo(() => {
    const control =
      page?.PageControls.find((c) => c.ControlType === 'Group' || c.ControlType === 'Repeater')
    return control?.PageControlId
  }, [page?.PageControls])

  useEffect(() => {
    if (pageLoading || !page) return

    if (ctx && page.TitleField && listControlId) {
      let cancelled = false
      ;(async () => {
        try {
          const rows = await pageDataService.list(
            pageId,
            listControlId,
            undefined,
            2,
            { [page.TitleField!]: ctx },
          )
          if (cancelled) return
          const match = rows[0]
          if (match?.SystemId) {
            const query: Record<string, string> = {}
            if (listPage) {
              query.fromList = String(getPageRouteId(listPage))
            }
            const returnPath = searchParams.get('return')
            if (returnPath) {
              query.return = returnPath
            }
            router.replace(
              getCardRecordPath(pageId, String(match.SystemId), 'Document', query),
            )
            return
          }
          setLookupFailed(true)
        } catch {
          if (!cancelled) setLookupFailed(true)
        }
      })()
      return () => {
        cancelled = true
      }
    }

    if (listPage) {
      const params = new URLSearchParams(searchParams.toString())
      params.set('page', String(getPageRouteId(listPage)))
      params.delete('ctx')
      params.delete('ctxLabel')
      const qs = params.toString()
      router.replace(qs ? `/dashboard?${qs}` : listDashboardPath(listPage))
    }
  }, [
    ctx,
    listControlId,
    listPage,
    page,
    pageId,
    pageLoading,
    router,
    searchParams,
  ])

  if (lookupFailed) {
    return (
      <div className="rounded-xl border border-strokeColor bg-white p-6 text-sm text-bodyText">
        Could not open document{ctx ? ` "${ctx}"` : ''}.{' '}
        {listPage ? (
          <button
            type="button"
            className="font-medium text-s1 underline underline-offset-2"
            onClick={() => router.push(listDashboardPath(listPage))}
          >
            Back to list
          </button>
        ) : null}
      </div>
    )
  }

  return <div className="h-32 animate-pulse rounded-xl bg-gray-100" />
}
