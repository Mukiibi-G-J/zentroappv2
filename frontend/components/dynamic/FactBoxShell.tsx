'use client'

import type { ReactNode } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import type { PageControl } from '@/types/page'
import { usePersistedBoolean } from '@/lib/usePersistedBoolean'
import { cn } from '@/lib/utils'

interface Props {
  control: PageControl
  recordReady: boolean
  saveFirstHint?: string
  storageKey?: string
  children: ReactNode
}

export default function FactBoxShell({
  control,
  recordReady,
  saveFirstHint,
  storageKey,
  children,
}: Props) {
  const collapseKey = storageKey ?? `factbox-expanded:${control.Name}`
  const [expanded, setExpanded] = usePersistedBoolean(collapseKey, true)

  return (
    <div className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
      {control.ShowCaption ? (
        <button
          type="button"
          onClick={() => setExpanded((open) => !open)}
          className={cn(
            'flex w-full items-center gap-2 border-b border-gray-100 bg-gray-50 px-4 py-2.5 text-left transition hover:bg-gray-100/80',
            !expanded && 'border-b-0',
          )}
          aria-expanded={expanded}
        >
          {expanded ? (
            <ChevronDown size={14} className="shrink-0 text-bodyText" />
          ) : (
            <ChevronRight size={14} className="shrink-0 text-bodyText" />
          )}
          <h3 className="min-w-0 flex-1 truncate text-xs font-semibold uppercase tracking-wide text-bodyText">
            {control.Caption}
          </h3>
        </button>
      ) : null}

      {!recordReady && saveFirstHint && expanded && (
        <div className="border-b border-amber-100 bg-amber-50 px-4 py-2 text-[11px] text-amber-800">
          {saveFirstHint}
        </div>
      )}

      {expanded ? children : null}
    </div>
  )
}
