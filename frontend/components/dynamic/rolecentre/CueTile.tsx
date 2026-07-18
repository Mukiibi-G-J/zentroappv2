'use client'

import { useRouter } from 'next/navigation'
import { ChevronRight } from 'lucide-react'
import { cn } from '@/lib/utils'
import { buildCueDrillDownUrl } from '@/lib/cueDrillDown'
import { usePages } from '@/hooks/usePage'
import type { CueData } from '@/types/page'

interface Props {
  cue: CueData
  isLoading: boolean
}

type TileVariant = 'favorable' | 'unfavorable' | 'ambiguous' | 'subordinate' | 'normal'

function getTileVariant(value: number | null, cue: CueData): TileVariant {
  const style = cue.CueStyle?.toLowerCase()
  if (style === 'subordinate') return 'subordinate'
  if (style === 'favorable') return 'favorable'
  if (style === 'unfavorable') return 'unfavorable'
  if (style === 'ambiguous') return 'ambiguous'
  if (value === null) return 'normal'
  if (cue.ThresholdDanger !== null && cue.ThresholdDanger !== undefined && value >= cue.ThresholdDanger) {
    return 'unfavorable'
  }
  if (cue.ThresholdWarning !== null && cue.ThresholdWarning !== undefined && value >= cue.ThresholdWarning) {
    return 'ambiguous'
  }
  if (style === 'normal' || !style) return 'favorable'
  return 'normal'
}

function formatCueValue(value: number): string {
  if (Number.isInteger(value)) return value.toLocaleString()
  return value.toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 })
}

const TILE_CLASSES: Record<
  TileVariant,
  { card: string; label: string; value: string; bar: string | null; chevron: string }
> = {
  favorable: {
    card: 'bg-s1 border-s1 hover:brightness-110 hover:shadow-md',
    label: 'text-white/80',
    value: 'text-white',
    bar: 'bg-p1',
    chevron: 'text-white/60',
  },
  unfavorable: {
    card: 'bg-red-600 border-red-600 hover:brightness-110 hover:shadow-md',
    label: 'text-white/80',
    value: 'text-white',
    bar: null,
    chevron: 'text-white/60',
  },
  ambiguous: {
    card: 'bg-s1 border-s1 hover:brightness-110 hover:shadow-md',
    label: 'text-white/80',
    value: 'text-white',
    bar: 'bg-s3',
    chevron: 'text-white/60',
  },
  subordinate: {
    card: 'bg-gray-200 border-gray-200 hover:bg-gray-300',
    label: 'text-gray-600',
    value: 'text-gray-700',
    bar: null,
    chevron: 'text-gray-500',
  },
  normal: {
    card: 'bg-s1 border-s1 hover:brightness-110 hover:shadow-md',
    label: 'text-white/80',
    value: 'text-white',
    bar: 'bg-p1',
    chevron: 'text-white/60',
  },
}

export default function CueTile({ cue, isLoading }: Props) {
  const router = useRouter()
  const { data: pages = [] } = usePages()
  const variant = isLoading ? 'normal' : getTileVariant(cue.Value, cue)
  const styles = TILE_CLASSES[variant]
  const clickable = !!cue.DrillDownPageId

  const handleClick = () => {
    const href = buildCueDrillDownUrl(cue, pages)
    if (href) router.push(href)
  }

  if (isLoading) {
    return (
      <div className="relative flex flex-col rounded-lg border border-s1/20 bg-s1/10 overflow-hidden p-4 min-h-[120px]">
        <div className="h-3 w-2/3 bg-white/40 rounded animate-pulse mb-3" />
        <div className="h-9 w-1/2 bg-white/40 rounded animate-pulse mt-auto" />
        <div className="absolute bottom-0 left-0 right-0 h-1.5 bg-s1/20 animate-pulse" />
      </div>
    )
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={!clickable}
      className={cn(
        'group relative flex flex-col rounded-lg border overflow-hidden p-4 pb-5 text-left transition-all duration-150 min-h-[120px]',
        styles.card,
        clickable ? 'cursor-pointer' : 'cursor-default',
      )}
    >
      <p className={cn('text-xs font-medium leading-tight pr-6', styles.label)}>{cue.Caption}</p>
      <p className={cn('text-3xl font-bold tabular-nums mt-auto', styles.value)}>
        {cue.Value !== null && cue.Value !== undefined ? formatCueValue(cue.Value) : '—'}
      </p>

      {clickable && (
        <ChevronRight
          size={16}
          className={cn(
            'absolute bottom-3 right-3 transition-transform group-hover:translate-x-0.5',
            styles.chevron,
          )}
          aria-hidden
        />
      )}

      {styles.bar && (
        <div className={cn('absolute bottom-0 left-0 right-0 h-1.5', styles.bar)} aria-hidden />
      )}
    </button>
  )
}
