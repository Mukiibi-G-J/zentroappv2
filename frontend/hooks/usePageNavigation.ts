'use client'

import { useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { toast } from 'sonner'
import { usePages } from '@/hooks/usePage'
import { pageDataService } from '@/services/pagedata.service'
import { getCardRecordPath, listDashboardPath, resolveListPageForCard } from '@/lib/pageRoutes'
import { isSetupSingletonCardPage } from '@/lib/setupPages'
import type { Page } from '@/types/page'

export function usePageNavigation() {
  const router = useRouter()
  const { data: pages = [] } = usePages()

  const resolvePage = useCallback(
    (pageName: string) => pages.find((p) => p.Name === pageName),
    [pages],
  )

  const navigateToPageName = useCallback(
    async (pageName: string) => {
      const pageMeta = resolvePage(pageName)
      if (!pageMeta) {
        toast.error(`Page "${pageName}" is not available`)
        return false
      }

      const pageId = pageMeta.PageId

      if (pageMeta.PageType === 'RoleCenter') {
        router.push(listDashboardPath(pageMeta))
        return true
      }

      if (isSetupSingletonCardPage(pageMeta)) {
        try {
          const systemId = await pageDataService.getSetupSolo(pageId)
          router.push(getCardRecordPath(pageId, systemId, pageMeta.PageType))
        } catch (err) {
          toast.error(err instanceof Error ? err.message : 'Could not open page')
          return false
        }
        return true
      }

      if (pageMeta.Name === 'UserSettingsCard') {
        try {
          const systemId = await pageDataService.getSetupSolo(pageId)
          router.push(getCardRecordPath(pageId, systemId, pageMeta.PageType))
        } catch (err) {
          toast.error(err instanceof Error ? err.message : 'Could not open page')
          return false
        }
        return true
      }

      if (pageMeta.PageType === 'Card') {
        const listPage = resolveListPageForCard(pages, pageMeta)
        if (listPage) {
          router.push(listDashboardPath(listPage))
          return true
        }
      }

      router.push(listDashboardPath(pageMeta))
      return true
    },
    [resolvePage, router],
  )

  return { navigateToPageName, resolvePage }
}
