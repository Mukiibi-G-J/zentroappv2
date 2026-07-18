'use client'

import { useRouter } from 'next/navigation'
import { cn } from '@/lib/utils'
import { buildCueDrillDownUrl } from '@/lib/cueDrillDown'
import { usePages } from '@/hooks/usePage'
import type { CueData, RoleCentreSection } from '@/types/page'

interface Props {
  section: RoleCentreSection
}

function underlineClass(style: string): string {
  const normalized = style.toLowerCase()
  if (normalized === 'unfavorable') return 'bg-red-500'
  if (normalized === 'ambiguous') return 'bg-s3'
  if (normalized === 'favorable') return 'bg-p1'
  return 'bg-s1'
}

function NormalCueTile({ cue }: { cue: CueData }) {
  const router = useRouter()
  const { data: pages = [] } = usePages()
  const display = cue.FormattedValue ?? (cue.Value !== null ? String(cue.Value) : '—')

  const handleLink = () => {
    const href = buildCueDrillDownUrl(cue, pages)
    if (href) router.push(href)
  }

  return (
    <div className="flex flex-col min-w-0">
      <p className="text-xs font-medium text-bodyText mb-1">{cue.Caption}</p>
      <p className="text-2xl sm:text-3xl font-bold text-mainTextColor tabular-nums truncate">
        {display}
      </p>
      <div className={cn('h-1 w-full rounded-full mt-3', underlineClass(cue.CueStyle))} />
      {cue.LinkCaption && cue.DrillDownPageId ? (
        <button
          type="button"
          onClick={handleLink}
          className="mt-2 text-left text-xs font-medium text-s1 hover:underline"
        >
          {cue.LinkCaption}
        </button>
      ) : null}
    </div>
  )
}

export default function NormalCueGroupSection({ section }: Props) {
  const cues = section.Cues ?? []

  return (
    <div className="space-y-4">
      <div className="border-b border-strokeColor pb-2">
        <h3 className="text-sm font-semibold text-mainTextColor">{section.Caption}</h3>
      </div>
      <div className="rounded-xl border border-strokeColor bg-white px-6 py-5">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-8">
          {cues.map((cue) => (
            <NormalCueTile key={cue.ControlId} cue={cue} />
          ))}
        </div>
      </div>
    </div>
  )
}
