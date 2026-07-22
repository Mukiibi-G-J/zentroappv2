'use client'

import { useEffect, useState } from 'react'
import { formatDecimalDisplay } from '@/lib/formatNumber'
import type { POSTrackingOption } from '@/types/pos'

interface POSTrackingDialogProps {
  open: boolean
  itemName: string
  options: POSTrackingOption[]
  loading?: boolean
  mode?: 'lot' | 'serial'
  /** Required number of serials when mode=serial (usually cart line qty). */
  requiredCount?: number
  selectedLotNo?: string
  selectedSerialNos?: string[]
  onClose: () => void
  onSelectLot: (lotNo: string) => void
  onConfirmSerials: (serialNos: string[]) => void
}

export function POSTrackingDialog({
  open,
  itemName,
  options,
  loading,
  mode = 'lot',
  requiredCount = 1,
  selectedLotNo,
  selectedSerialNos = [],
  onClose,
  onSelectLot,
  onConfirmSerials,
}: POSTrackingDialogProps) {
  const [picked, setPicked] = useState<string[]>(selectedSerialNos)

  useEffect(() => {
    if (open) setPicked(selectedSerialNos)
  }, [open, selectedSerialNos])

  if (!open) return null

  const isSerial = mode === 'serial'
  const title = isSerial ? 'Select serial numbers' : 'Select lot'
  const emptyMsg = isSerial
    ? 'No serials with remaining quantity are available for this item.'
    : 'No lots with remaining quantity are available for this item.'

  const toggleSerial = (serial: string) => {
    setPicked((prev) => {
      if (prev.includes(serial)) return prev.filter((s) => s !== serial)
      if (prev.length >= requiredCount) return prev
      return [...prev, serial]
    })
  }

  return (
    <div className="fixed inset-0 z-[60] flex items-end justify-center bg-black/40 p-4 sm:items-center">
      <div className="flex max-h-[85vh] w-full max-w-2xl flex-col rounded-2xl bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-strokeColor px-5 py-4">
          <div>
            <h2 className="text-lg font-semibold text-mainTextColor">{title}</h2>
            <p className="text-sm text-bodyText">{itemName}</p>
            {isSerial ? (
              <p className="mt-1 text-xs text-bodyText">
                Select {requiredCount} serial{requiredCount === 1 ? '' : 's'} ({picked.length} selected)
              </p>
            ) : null}
          </div>
          <button type="button" onClick={onClose} className="text-sm text-bodyText hover:text-mainTextColor">
            Close
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-4">
          {loading ? (
            <p className="py-8 text-center text-sm text-bodyText">
              {isSerial ? 'Loading available serials…' : 'Loading available lots…'}
            </p>
          ) : options.length === 0 ? (
            <p className="py-8 text-center text-sm text-bodyText">{emptyMsg}</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-strokeColor text-xs uppercase text-bodyText">
                    <th className="px-2 py-2">{isSerial ? 'Serial no.' : 'Lot no.'}</th>
                    <th className="px-2 py-2">Document</th>
                    <th className="px-2 py-2">Qty left</th>
                    <th className="px-2 py-2">Expiry</th>
                    <th className="px-2 py-2" />
                  </tr>
                </thead>
                <tbody>
                  {options.map((option, index) => {
                    const code = isSerial ? option.serial_no! : option.lot_no!
                    const expiryDate = option.expiry_date ? new Date(option.expiry_date) : null
                    const isSelected = isSerial
                      ? picked.includes(code)
                      : selectedLotNo === code
                    return (
                      <tr
                        key={`${code}-${index}`}
                        role="button"
                        tabIndex={0}
                        onClick={() => {
                          if (isSerial) toggleSerial(code)
                          else onSelectLot(code)
                        }}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault()
                            if (isSerial) toggleSerial(code)
                            else onSelectLot(code)
                          }
                        }}
                        className={`cursor-pointer border-b border-strokeColor/60 transition-colors hover:bg-s1/5 ${
                          index === 0 && !isSerial ? 'bg-blue-50/60' : ''
                        } ${isSelected ? 'ring-1 ring-inset ring-s1' : ''}`}
                      >
                        <td className="px-2 py-3 font-medium text-mainTextColor">
                          {code}
                          {!isSerial && index === 0 && (
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
                              if (isSerial) toggleSerial(code)
                              else onSelectLot(code)
                            }}
                            className="rounded-lg bg-s1 px-3 py-1.5 text-xs font-semibold text-white hover:opacity-90"
                          >
                            {isSerial ? (isSelected ? 'Selected' : 'Select') : 'Select'}
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

        {isSerial ? (
          <div className="flex justify-end gap-2 border-t border-strokeColor px-5 py-3">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-gray-200 px-4 py-2 text-sm font-medium text-mainTextColor hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="button"
              disabled={picked.length !== requiredCount}
              onClick={() => onConfirmSerials(picked)}
              className="rounded-lg bg-s1 px-4 py-2 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50"
            >
              Confirm
            </button>
          </div>
        ) : null}
      </div>
    </div>
  )
}
