'use client'

import DatePicker from '@/components/ui/DatePicker'

interface Props {
  startDate: string
  endDate: string
  onStartDateChange: (value: string) => void
  onEndDateChange: (value: string) => void
  disabled?: boolean
  compact?: boolean
}

export default function FinancialReportDateFilters({
  startDate,
  endDate,
  onStartDateChange,
  onEndDateChange,
  disabled = false,
  compact = false,
}: Props) {
  const invalid = Boolean(startDate && endDate && startDate > endDate)

  return (
    <div className={compact ? 'flex flex-wrap items-end gap-3' : 'contents'}>
      <div className={compact ? 'space-y-1.5 min-w-[10rem]' : 'space-y-1.5'}>
        <label className="block text-xs font-medium text-bodyText">From</label>
        <DatePicker value={startDate} onChange={onStartDateChange} disabled={disabled} />
      </div>
      <div className={compact ? 'space-y-1.5 min-w-[10rem]' : 'space-y-1.5'}>
        <label className="block text-xs font-medium text-bodyText">To</label>
        <DatePicker value={endDate} onChange={onEndDateChange} disabled={disabled} />
      </div>
      {invalid ? (
        <p className={compact ? 'w-full text-sm text-red-600' : 'sm:col-span-2 lg:col-span-3 text-sm text-red-600'}>
          Start date must be on or before end date.
        </p>
      ) : null}
    </div>
  )
}
