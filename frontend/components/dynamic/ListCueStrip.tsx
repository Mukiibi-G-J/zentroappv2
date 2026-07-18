'use client'

import CueGroupSection from '@/components/dynamic/rolecentre/CueGroupSection'
import type { RoleCentreSection } from '@/types/page'

interface Props {
  groups: RoleCentreSection[]
  isLoading?: boolean
}

export default function ListCueStrip({ groups, isLoading = false }: Props) {
  if (!isLoading && groups.length === 0) return null

  return (
    <div className="shrink-0 space-y-4">
      {isLoading
        ? (
            <CueGroupSection
              section={{
                ControlId: 0,
                ControlType: 'CueGroup',
                Caption: 'Sales overview',
                LayoutStyle: 'StandardCues',
                Cues: [],
              }}
              isLoading
            />
          )
        : groups.map((section) => (
            <CueGroupSection key={section.ControlId} section={section} />
          ))}
    </div>
  )
}
