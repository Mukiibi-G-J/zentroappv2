'use client'

import SearchableRelationSelect from './SearchableRelationSelect'
import type { RelationOption } from '@/hooks/useRelationOptions'

interface Props {
  definitionOptions: RelationOption[]
  activeDefinitionName: string
  onDefinitionChange: (name: string) => void
}

/** BC Account Schedule (104) header — Name selector only. */
export default function RowDefinitionWorksheetPanel({
  definitionOptions,
  activeDefinitionName,
  onDefinitionChange,
}: Props) {
  return (
    <section className="rounded-xl border border-gray-200 bg-white px-4 py-3">
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-sm font-medium text-bodyText shrink-0">Name</span>
        <div className="min-w-[12rem] max-w-md flex-1">
          <SearchableRelationSelect
            options={definitionOptions}
            value={activeDefinitionName}
            placeholder="Select row definition…"
            onChange={onDefinitionChange}
          />
        </div>
      </div>
    </section>
  )
}
