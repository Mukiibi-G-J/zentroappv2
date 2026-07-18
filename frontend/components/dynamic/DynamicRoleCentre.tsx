'use client'

import { RefreshCw } from 'lucide-react'
import { useRoleCentre } from '@/hooks/useRoleCentre'
import HeadlineSection from './rolecentre/HeadlineSection'
import CueGroupSection from './rolecentre/CueGroupSection'
import RoleCentrePart from './rolecentre/RoleCentrePart'
import BrickSection from './rolecentre/BrickSection'
import AssistanceSection from './rolecentre/AssistanceSection'
import ReportsSection from './rolecentre/ReportsSection'
import type { RoleCentreSection } from '@/types/page'

interface Props {
  pageId: number
}

function SectionRenderer({ section }: { section: RoleCentreSection }) {
  switch (section.ControlType) {
    case 'Headline':
      return <HeadlineSection section={section} />
    case 'CueGroup':
      return <CueGroupSection section={section} />
    case 'Part':
      return <RoleCentrePart section={section} />
    case 'Brick':
      return <BrickSection section={section} />
    case 'Assistance':
      return <AssistanceSection section={section} />
    case 'Reports':
      return <ReportsSection section={section} />
    default:
      return null
  }
}

function RoleCentreSkeleton() {
  return (
    <div className="space-y-6">
      <div className="h-8 w-56 bg-gray-100 rounded animate-pulse" />
      {/* Headline skeleton */}
      <div className="rounded-xl border border-strokeColor bg-white px-6 py-5 space-y-2">
        <div className="h-3 w-32 bg-gray-100 rounded animate-pulse" />
        <div className="h-6 w-3/4 bg-gray-100 rounded animate-pulse" />
      </div>
      {/* CueGroup skeleton */}
      <div className="space-y-4">
        <div className="border-b border-strokeColor pb-2">
          <div className="h-4 w-36 bg-gray-100 rounded animate-pulse" />
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          {[...Array(5)].map((_, i) => (
            <div
              key={i}
              className="relative rounded-lg border border-s1/20 bg-s1/10 p-4 min-h-[120px] overflow-hidden"
            >
              <div className="h-3 w-2/3 bg-white/40 rounded animate-pulse mb-3" />
              <div className="h-9 w-1/2 bg-white/40 rounded animate-pulse mt-auto" />
              <div className="absolute bottom-0 left-0 right-0 h-1.5 bg-s1/20 animate-pulse" />
            </div>
          ))}
        </div>
      </div>
      {/* Part skeleton */}
      <div className="rounded-xl border border-strokeColor bg-white overflow-hidden">
        <div className="px-5 py-3 border-b border-gray-100 flex justify-between">
          <div className="h-4 w-40 bg-gray-100 rounded animate-pulse" />
          <div className="h-4 w-16 bg-gray-100 rounded animate-pulse" />
        </div>
        {[...Array(5)].map((_, i) => (
          <div key={i} className="px-5 py-3 border-b border-gray-50 flex gap-4">
            {[...Array(4)].map((_, j) => (
              <div key={j} className="h-4 flex-1 bg-gray-100 rounded animate-pulse" />
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}

export default function DynamicRoleCentre({ pageId }: Props) {
  const { data, isLoading, isError, error, refetch, isFetching } = useRoleCentre(pageId)

  if (isLoading) return <RoleCentreSkeleton />

  if (isError) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 px-5 py-4 flex items-start gap-3">
        <div className="flex-1">
          <p className="text-sm font-medium text-red-700">Failed to load Role Centre</p>
          <p className="text-xs text-red-600 mt-0.5">
            {error instanceof Error ? error.message : 'Unknown error'}
          </p>
        </div>
        <button
          type="button"
          onClick={() => refetch()}
          className="text-xs font-medium text-red-600 hover:text-red-700 underline"
        >
          Retry
        </button>
      </div>
    )
  }

  if (!data) return null

  return (
    <div className="flex-1 min-h-0 overflow-y-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-mainTextColor">{data.Caption}</h1>
        <button
          type="button"
          onClick={() => refetch()}
          title="Refresh Role Centre"
          className="p-2 rounded-lg hover:bg-softBg text-bodyText transition"
        >
          <RefreshCw size={16} className={isFetching ? 'animate-spin' : ''} />
        </button>
      </div>

      {data.Sections.map((section) => (
        <SectionRenderer key={section.ControlId} section={section} />
      ))}
    </div>
  )
}
