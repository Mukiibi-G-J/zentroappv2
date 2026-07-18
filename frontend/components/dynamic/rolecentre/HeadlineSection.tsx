'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import { useRouter } from 'next/navigation'
import { cn } from '@/lib/utils'
import { buildCueDrillDownUrl } from '@/lib/cueDrillDown'
import { usePages } from '@/hooks/usePage'
import type { HeadlineItem, RoleCentreSection } from '@/types/page'

interface Props {
  section: RoleCentreSection
}

const ROTATE_MS = 8000
const VALUE_PATTERN = /UGX\s[\d,]+(\.\d+)?|\d[\d,]*(\.\d+)?(%|\s?[A-Z]{3})?/

function splitHeadline(text: string): { prefix: string; value: string; suffix: string } | null {
  const match = VALUE_PATTERN.exec(text)
  if (!match) return null
  return {
    prefix: text.slice(0, match.index),
    value: match[0],
    suffix: text.slice(match.index + match[0].length),
  }
}

function headlineDrillDownUrl(
  item: HeadlineItem,
  pages: Parameters<typeof buildCueDrillDownUrl>[1],
): string | null {
  if (!item.DrillDownPageId) return null
  return buildCueDrillDownUrl({
    ControlId: item.ControlId,
    Caption: item.Title,
    Value: null,
    CueStyle: '',
    DrillDownPageId: item.DrillDownPageId,
    DrillDownQuery: item.DrillDownQuery ?? '',
    ThresholdWarning: null,
    ThresholdDanger: null,
  }, pages)
}

function HeadlineBody({ text }: { text: string }) {
  const parts = splitHeadline(text)
  if (parts) {
    return (
      <p className="text-xl sm:text-2xl font-semibold text-mainTextColor leading-snug">
        {parts.prefix}
        <span className="text-s1 font-bold">{parts.value}</span>
        {parts.suffix}
      </p>
    )
  }
  return (
    <p className="text-xl sm:text-2xl font-semibold text-mainTextColor leading-snug">
      {text || '—'}
    </p>
  )
}

export default function HeadlineSection({ section }: Props) {
  const router = useRouter()
  const { data: pages = [] } = usePages()
  const headlines = useMemo(() => {
    if (section.Headlines?.length) return section.Headlines
    if (section.Value) {
      return [{
        ControlId: section.ControlId,
        Title: section.Caption || 'Insight',
        Text: section.Value,
      }]
    }
    return []
  }, [section])

  const [activeIndex, setActiveIndex] = useState(0)

  useEffect(() => {
    setActiveIndex(0)
  }, [headlines.length, section.ControlId])

  useEffect(() => {
    if (headlines.length <= 1) return undefined
    const timer = window.setInterval(() => {
      setActiveIndex((prev) => (prev + 1) % headlines.length)
    }, ROTATE_MS)
    return () => window.clearInterval(timer)
  }, [headlines.length])

  const active = headlines[activeIndex]
  const drillDownUrl = active ? headlineDrillDownUrl(active, pages) : null

  const goTo = useCallback((index: number) => {
    setActiveIndex(index)
  }, [])

  const onActivate = useCallback(() => {
    if (drillDownUrl) router.push(drillDownUrl)
  }, [drillDownUrl, router])

  if (!active) return null

  return (
    <div
      className={cn(
        'rounded-lg border border-strokeColor bg-white px-6 py-5 shadow-sm',
        drillDownUrl && 'cursor-pointer hover:border-s1/40 transition-colors',
      )}
      role={drillDownUrl ? 'button' : undefined}
      tabIndex={drillDownUrl ? 0 : undefined}
      onClick={drillDownUrl ? onActivate : undefined}
      onKeyDown={
        drillDownUrl
          ? (e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault()
                onActivate()
              }
            }
          : undefined
      }
    >
      <p className="text-[11px] font-semibold text-bodyText uppercase tracking-[0.12em] mb-3">
        {active.Title || section.Caption || 'Headline'}
      </p>

      <div className="min-h-[3.5rem]">
        <HeadlineBody text={active.Text} />
      </div>

      {headlines.length > 1 && (
        <div className="mt-4 flex items-center gap-2" aria-label="Headline pagination">
          {headlines.map((item, index) => (
            <button
              key={item.ControlId}
              type="button"
              aria-label={`Show headline ${index + 1}`}
              aria-current={index === activeIndex ? 'true' : undefined}
              onClick={(e) => {
                e.stopPropagation()
                goTo(index)
              }}
              className={cn(
                'h-2 w-2 rounded-full transition-colors',
                index === activeIndex
                  ? 'bg-mainTextColor'
                  : 'bg-gray-300 hover:bg-gray-400',
              )}
            />
          ))}
        </div>
      )}
    </div>
  )
}
