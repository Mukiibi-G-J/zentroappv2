'use client'

import { formatDecimalDisplay } from '@/lib/formatNumber'
import type { POSTrackingOption } from '@/types/pos'

interface POSTrackingDialogProps {
  open: boolean
  itemName: string
  options: POSTrackingOption[]
  loading?: boolean
  selectedLotNo?: string
  onClose: () => void
  onSelect: (lotNo: string) => void
}

export function POSTrackingDialog({
  open,
  itemName,
  options,
  loading,
  selectedLotNo,
  onClose,
  onSelect,
}: POSTrackingDialogProps) {
  if (!open) return null

  return (
    <div className="fixed inset-0 z-[60] flex items-end justify-center bg-black/40 p-4 sm:items-center">
      <div className="flex max-h-[85vh] w-full max-w-2xl flex-col rounded-2xl bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-strokeColor px-5 py-4">
          <div>
            <h2 className="text-lg font-semibold text-mainTextColor">Select lot</h2>
            <p className="text-sm text-bodyText">{itemName}</p>
          </div>
          <button type="button" onClick={onClose} className="text-sm text-bodyText hover:text-mainTextColor">
            Close
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-4">
          {loading ? (
            <p className="py-8 text-center text-sm text-bodyText">Loading available lots…</p>
          ) : options.length === 0 ? (
            <p className="py-8 text-center text-sm text-bodyText">
              No lots with remaining quantity are available for this item.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-strokeColor text-xs uppercase text-bodyText">
                    <th className="px-2 py-2">Lot no.</th>
                    <th className="px-2 py-2">Document</th>
                    <th className="px-2 py-2">Qty left</th>
                    <th className="px-2 py-2">Expiry</th>
                    <th className="px-2 py-2" />
                  </tr>
                </thead>
                <tbody>
                  {options.map((option, index) => {
                    const expiryDate = option.expiry_date ? new Date(option.expiry_date) : null
                    const isSelected = selectedLotNo === option.lot_no
                    return (
                      <tr
                        key={`${option.lot_no}-${index}`}
                        role="button"
                        tabIndex={0}
                        onClick={() => onSelect(option.lot_no)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault()
                            onSelect(option.lot_no)
                          }
                        }}
                        className={`cursor-pointer border-b border-strokeColor/60 transition-colors hover:bg-s1/5 ${
                          index === 0 ? 'bg-blue-50/60' : ''
                        } ${isSelected ? 'ring-1 ring-inset ring-s1' : ''}`}
                      >
                        <td className="px-2 py-3 font-medium text-mainTextColor">
                          {option.lot_no}
                          {index === 0 && (
                            <span className="ml-2 rounded bg-blue-100 px-1.5 py-0.5 text-[10px] font-semibold text-blue-800">
                              FIFO
                            </span>
                          )}
                        </td>
                        <td className="px-2 py-3 text-bodyText">{option.document_no || '—'}</td>
                        <td className="px-2 py-3 font-medium text-green-700">
                          {formatDecimalDisplay(option.remaining_quantity)}
                        </td>
                        <td className="px-2 py-3 text-bodyText">
                          {expiryDate ? expiryDate.toLocaleDateString() : '—'}
                        </td>
                        <td className="px-2 py-3 text-right">
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation()
                              onSelect(option.lot_no)
                            }}
                            className="rounded-lg bg-s1 px-3 py-1.5 text-xs font-semibold text-white hover:opacity-90"
                          >
                            Select
                          </button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
