'use client'

import { usePage } from '@/hooks/usePage'
import { isCardPage } from '@/lib/isCardPage'
import DynamicCardPage from './DynamicCardPage'
import DynamicDetailPage from './DynamicDetailPage'

interface Props {
  pageId: number
  systemId: string
}

function RecordSkeleton() {
  return (
    <div className="flex flex-col w-full h-full space-y-6 animate-pulse">
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 bg-gray-200 rounded-lg shrink-0" />
        <div className="h-7 w-56 bg-gray-200 rounded" />
      </div>
      <div className="bg-white rounded-xl border border-gray-200 p-6 flex-1">
        <div className="h-4 w-full bg-gray-100 rounded" />
      </div>
    </div>
  )
}

export default function RecordPageRouter({ pageId, systemId }: Props) {
  const { data: page, isLoading } = usePage(pageId)

  if (isLoading) return <RecordSkeleton />

  if (isCardPage(page)) {
    return <DynamicCardPage pageId={pageId} systemId={systemId} />
  }

  return <DynamicDetailPage pageId={pageId} systemId={systemId} />
}
