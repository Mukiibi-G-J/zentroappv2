'use client'

import { ChevronRight, PanelRightOpen } from 'lucide-react'
import FactBoxPanel from './FactBoxPanel'
import type { FactBoxAsideProps } from './factBoxes/types'
import { usePersistedBoolean } from '@/lib/usePersistedBoolean'
import { cn } from '@/lib/utils'

export default function FactBoxAside({
  controls,
  data,
  recordReady,
  readOnly,
  saveFirstHint,
  storageKey = 'factbox-pane',
}: FactBoxAsideProps) {
  const [paneOpen, setPaneOpen] = usePersistedBoolean(`${storageKey}:open`, true)

  if (controls.length === 0) return null

  if (!paneOpen) {
    return (
      <div className="flex shrink-0 items-start lg:sticky lg:top-4">
        <button
          type="button"
          onClick={() => setPaneOpen(true)}
          title="Show Fact Box"
          aria-label="Show Fact Box"
          className={cn(
            'flex min-h-[120px] flex-col items-center justify-center gap-2 rounded-l-lg border border-r-0 border-gray-200',
            'bg-white px-1.5 py-4 text-bodyText shadow-sm transition hover:bg-gray-50 hover:text-mainTextColor',
          )}
        >
          <PanelRightOpen size={16} className="shrink-0" />
          <span
            className="text-[10px] font-semibold uppercase tracking-wider [writing-mode:vertical-rl]"
            style={{ textOrientation: 'mixed' }}
          >
            Fact Box
          </span>
        </button>
      </div>
    )
  }

  return (
    <aside className="w-full shrink-0 space-y-4 lg:sticky lg:top-4 lg:w-72">
      <div className="flex items-center justify-between gap-2 px-1">
        <span className="text-[11px] font-semibold uppercase tracking-wide text-bodyText">
          Fact Box
        </span>
        <button
          type="button"
          onClick={() => setPaneOpen(false)}
          title="Hide Fact Box"
          aria-label="Hide Fact Box"
          className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-bodyText transition hover:bg-gray-100 hover:text-mainTextColor"
        >
          <span className="hidden sm:inline">Hide</span>
          <ChevronRight size={14} />
        </button>
      </div>

      {controls.map((control) => (
        <FactBoxPanel
          key={control.PageControlId}
          control={control}
          data={data}
          recordReady={recordReady}
          readOnly={readOnly}
          saveFirstHint={saveFirstHint}
          storageKey={`${storageKey}:${control.Name}`}
        />
      ))}
    </aside>
  )
}
