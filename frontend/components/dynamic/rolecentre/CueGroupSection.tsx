'use client'

import CueTile from './CueTile'
import NormalCueGroupSection from './NormalCueGroupSection'
import type { RoleCentreSection } from '@/types/page'

interface Props {
  section: RoleCentreSection
  isLoading?: boolean
}

export default function CueGroupSection({ section, isLoading = false }: Props) {
  if (section.LayoutStyle === 'NormalCues') {
    return <NormalCueGroupSection section={section} />
  }

  const cues = section.Cues ?? []
  const gridClass =
    section.LayoutStyle === 'StandardCues'
      ? 'grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3'
      : 'grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3'

  return (
    <div className="space-y-4">
      <div className="border-b border-strokeColor pb-2">
        <h3 className="text-sm font-semibold text-mainTextColor">{section.Caption}</h3>
      </div>
      <div className={gridClass}>
        {isLoading
          ? [...Array(3)].map((_, i) => (
              <CueTile
                key={i}
                cue={{
                  ControlId: i,
                  Caption: '',
                  Value: null,
                  CueStyle: '',
                  DrillDownPageId: null,
                  ThresholdWarning: null,
                  ThresholdDanger: null,
                }}
                isLoading
              />
            ))
          : cues.map((cue) => (
              <CueTile key={cue.ControlId} cue={cue} isLoading={false} />
            ))}
      </div>
    </div>
  )
}
