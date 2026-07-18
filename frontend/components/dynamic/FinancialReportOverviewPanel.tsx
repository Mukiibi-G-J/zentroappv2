'use client'

import { useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import SearchableRelationSelect from './SearchableRelationSelect'
import DynamicField from './DynamicField'
import FinancialReportDateFilters from './FinancialReportDateFilters'
import type { RelationOption } from '@/hooks/useRelationOptions'
import type { Page, PageControlField } from '@/types/page'
import { getRecordFieldValue } from '@/lib/recordFieldValue'
import type { DataRecord } from '@/types/pagedata'

interface Props {
  headerPage?: Page
  reportRecord?: DataRecord
  reportOptions: RelationOption[]
  activeReportName: string
  onReportChange: (name: string) => void
  onFieldSave: (field: PageControlField, value: unknown) => void
  startDate: string
  endDate: string
  onStartDateChange: (value: string) => void
  onEndDateChange: (value: string) => void
  readOnly?: boolean
}

const OPTIONS_FIELDS = new Set(['period_type', 'show_all_lines'])

const DIMENSION_FIELDS = new Set(['dimension_1_filter'])

function CollapsibleSection({
  title,
  defaultOpen = true,
  children,
}: {
  title: string
  defaultOpen?: boolean
  children: React.ReactNode
}) {
  const [expanded, setExpanded] = useState(defaultOpen)

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
        <span className="text-sm font-semibold text-mainTextColor">{title}</span>
      </button>
      {expanded && <div className="px-4 py-3">{children}</div>}
    </section>
  )
}

function FieldGrid({
  fields,
  reportRecord,
  readOnly,
  onFieldSave,
}: {
  fields: PageControlField[]
  reportRecord?: DataRecord
  readOnly?: boolean
  onFieldSave: (field: PageControlField, value: unknown) => void
}) {
  if (!reportRecord) {
    return <p className="text-sm text-bodyText">Select a financial report.</p>
  }

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {fields.map((field) => {
        const value = getRecordFieldValue(reportRecord, field.Name)
        const editable = !readOnly && field.Editable

        return (
          <div key={field.PageControlFieldId} className="space-y-1.5">
            <label className="block text-xs font-medium text-bodyText">{field.Caption}</label>
            <DynamicField
              field={{ ...field, Editable: editable }}
              value={value}
              disabled={!editable}
              onBlur={(next) => onFieldSave(field, next)}
            />
          </div>
        )
      })}
    </div>
  )
}

export default function FinancialReportOverviewPanel({
  headerPage,
  reportRecord,
  reportOptions,
  activeReportName,
  onReportChange,
  onFieldSave,
  startDate,
  endDate,
  onStartDateChange,
  onEndDateChange,
  readOnly = false,
}: Props) {
  const headerFields =
    headerPage?.PageControls.find((c) => c.ControlType === 'Group')?.Fields.filter((f) => f.Visible) ?? []

  const optionFields = headerFields
    .filter((f) => OPTIONS_FIELDS.has(f.Name))
    .sort((a, b) => a.TabIndex - b.TabIndex)
  const dimensionFields = headerFields.filter((f) => DIMENSION_FIELDS.has(f.Name))

  return (
    <div className="space-y-3">
      <section className="rounded-xl border border-gray-200 bg-white px-4 py-3">
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-sm font-medium text-bodyText shrink-0">Financial Report</span>
          <div className="min-w-[12rem] max-w-md flex-1">
            <SearchableRelationSelect
              options={reportOptions}
              value={activeReportName}
              placeholder="Select report…"
              onChange={onReportChange}
            />
          </div>
        </div>
      </section>

      <CollapsibleSection title="Options">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {optionFields.map((field) => {
            if (!reportRecord) return null
            const value = getRecordFieldValue(reportRecord, field.Name)
            const editable = !readOnly && field.Editable
            return (
              <div key={field.PageControlFieldId} className="space-y-1.5">
                <label className="block text-xs font-medium text-bodyText">{field.Caption}</label>
                <DynamicField
                  field={{ ...field, Editable: editable }}
                  value={value}
                  disabled={!editable}
                  onBlur={(next) => onFieldSave(field, next)}
                />
              </div>
            )
          })}
          <FinancialReportDateFilters
            startDate={startDate}
            endDate={endDate}
            onStartDateChange={onStartDateChange}
            onEndDateChange={onEndDateChange}
            disabled={readOnly || !reportRecord}
          />
        </div>
        {!reportRecord ? (
          <p className="mt-2 text-sm text-bodyText">Select a financial report.</p>
        ) : null}
      </CollapsibleSection>

      {dimensionFields.length > 0 && (
        <CollapsibleSection title="Dimensions">
          <FieldGrid
            fields={dimensionFields}
            reportRecord={reportRecord}
            readOnly={readOnly}
            onFieldSave={onFieldSave}
          />
        </CollapsibleSection>
      )}
    </div>
  )
}
