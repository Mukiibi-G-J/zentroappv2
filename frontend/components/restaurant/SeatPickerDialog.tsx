'use client'

import type { CoversChoice } from '@/types/restaurant'

interface Props {
  open: boolean
  itemLabel?: string
  covers: CoversChoice
  onPickTable: () => void
  onPickSeat: (seat: number) => void
  onAddSeat: () => void
  onCancel: () => void
}

export function SeatPickerDialog({
  open,
  itemLabel,
  covers,
  onPickTable,
  onPickSeat,
  onAddSeat,
  onCancel,
}: Props) {
  if (!open) return null

  const seatCount = covers != null && covers >= 1 ? covers : 0

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-sm rounded-xl bg-white p-5 shadow-xl">
        <h3 className="text-lg font-semibold text-mainTextColor">Assign to seat</h3>
        {itemLabel ? (
          <p className="mt-1 text-sm text-bodyText line-clamp-2">{itemLabel}</p>
        ) : null}
        <p className="mt-2 text-xs text-bodyText">
          Table = shared for everyone. Seats match your cover count; use Add seat if you need
          another guest.
        </p>

        <div className="mt-4 space-y-2">
          <button
            type="button"
            onClick={onPickTable}
            className="w-full rounded-lg bg-s1 px-4 py-2.5 text-sm font-medium text-white"
          >
            Table (shared)
          </button>

          {seatCount > 0 ? (
            <div className="grid grid-cols-4 gap-2">
              {Array.from({ length: seatCount }, (_, i) => i + 1).map((n) => (
                <button
                  key={n}
                  type="button"
                  onClick={() => onPickSeat(n)}
                  className="rounded-lg border border-strokeColor bg-softBg py-3 text-center text-sm font-semibold text-mainTextColor hover:border-s1 hover:bg-white"
                >
                  Seat {n}
                </button>
              ))}
            </div>
          ) : (
            <p className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
              No seats yet. Use <strong>Add seat</strong> to set cover count to 1, or assign to{' '}
              <strong>Table</strong>.
            </p>
          )}

          <button
            type="button"
            onClick={onAddSeat}
            className="w-full rounded-lg border border-sky-300 bg-sky-50 px-4 py-2 text-sm font-medium text-sky-900"
          >
            Add seat
          </button>
          <button
            type="button"
            onClick={onCancel}
            className="w-full rounded-lg border border-strokeColor px-4 py-2 text-sm hover:bg-softBg"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  )
}
