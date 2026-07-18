'use client'

import { useState } from 'react'
import type { CoversChoice } from '@/types/restaurant'

interface Props {
  open: boolean
  tableLabel: string
  onCancel: () => void
  onConfirm: (covers: CoversChoice) => void
}

export function CoversPickerDialog({ open, tableLabel, onCancel, onConfirm }: Props) {
  const [value, setValue] = useState('2')

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-sm rounded-xl bg-white p-5 shadow-xl">
        <h3 className="text-lg font-semibold text-mainTextColor">Guest count</h3>
        <p className="mt-1 text-sm text-bodyText">How many covers for {tableLabel}?</p>
        <input
          type="number"
          min={1}
          max={99}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          className="mt-4 w-full rounded-lg border border-strokeColor px-3 py-2 text-sm"
        />
        <div className="mt-4 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => onConfirm(null)}
            className="rounded-lg border border-strokeColor px-3 py-2 text-sm hover:bg-softBg"
          >
            No covers
          </button>
          <button
            type="button"
            onClick={onCancel}
            className="ml-auto rounded-lg border border-strokeColor px-4 py-2 text-sm"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => {
              const n = parseInt(value, 10)
              onConfirm(Number.isFinite(n) && n > 0 ? n : 2)
            }}
            className="rounded-lg bg-s1 px-4 py-2 text-sm font-medium text-white"
          >
            Start check
          </button>
        </div>
      </div>
    </div>
  )
}
