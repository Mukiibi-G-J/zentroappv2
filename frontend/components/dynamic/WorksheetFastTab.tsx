'use client'

import { useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import SearchableRelationSelect from './SearchableRelationSelect'
import type { RelationOption } from '@/hooks/useRelationOptions'

interface Props {
  batchOptions: RelationOption[]
  activeBatch: string
  onBatchChange: (batchName: string) => void
}

export default function WorksheetFastTab({ batchOptions, activeBatch, onBatchChange }: Props) {
  const [expanded, setExpanded] = useState(true)

  return (
    <section className="rounded-xl border border-gray-200 bg-white overflow-hidden">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center gap-2 px-4 py-2.5 text-left bg-gray-50 border-b border-gray-200 hover:bg-gray-100/80 transition"
      >
        {expanded
          ? <ChevronDown size={16} className="text-bodyText" />
          : <ChevronRight size={16} className="text-bodyText" />}
        <span className="text-sm font-semibold text-mainTextColor">General</span>
      </button>

      {expanded && (
        <div className="flex items-center gap-4 px-4 py-3">
          <span className="text-sm font-medium text-bodyText shrink-0">Batch Name</span>
          <div className="flex-1 max-w-lg">
            <SearchableRelationSelect
              options={batchOptions}
              value={activeBatch}
              placeholder="Select batch…"
              onChange={onBatchChange}
            />
          </div>
        </div>
      )}
    </section>
  )
}
