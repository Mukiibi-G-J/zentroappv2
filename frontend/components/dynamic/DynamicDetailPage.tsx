'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { ArrowLeft, Loader2, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { usePage, usePages } from '@/hooks/usePage'
import { usePageDataRecord, useUpdateField, useDeleteRecord } from '@/hooks/usePageData'
import { useRelationOptions } from '@/hooks/useRelationOptions'
import DynamicField from './DynamicField'
import BooleanFieldRow from './BooleanFieldRow'
import DrillDownField from './DrillDownField'
import SearchableRelationSelect from './SearchableRelationSelect'
import FactBoxAside from './FactBoxAside'
import CardRibbon from './CardRibbon'
import DynamicCardPage from './DynamicCardPage'
import { isCardPage } from '@/lib/isCardPage'
import PasswordField from './PasswordField'
import ErrorBanner from '@/components/ui/ErrorBanner'
import { buildCardActionUrl } from '@/lib/cardAction'
import {
  getCardRecordPath,
  listDashboardPath,
  parseFromListPageId,
  resolveReturnListPage,
} from '@/lib/pageRoutes'
import { isFieldEditable } from '@/lib/fieldVisibility'
import { missingPrimaryKeyForCreate } from '@/lib/cardPage'
import { isSetupSingletonCardPage } from '@/lib/setupPages'
import type { Page, PageAction, PageControl, PageControlField } from '@/types/page'
import type { DataRecord } from '@/types/pagedata'

function isCardFieldEditable(
  field: PageControlField,
  control: PageControl,
  opts: { readOnly: boolean; isNew: boolean; insertAllowed: boolean; pageName?: string; data: DataRecord },
): boolean {
  if (opts.readOnly) return false
  if (opts.isNew && !opts.insertAllowed) return false
  if (!opts.isNew && control.Editable === false) return false
  return isFieldEditable(field, opts.data, opts.pageName)
}

interface Props {
  pageId: number
  systemId: string
}

export default function DynamicDetailPage({ pageId, systemId }: Props) {
  const router = useRouter()
  const searchParams = useSearchParams()
  const isNew = systemId === 'new'

  const listPageIdFromUrl = parseFromListPageId(searchParams.get('fromList'))

  const { data: page, isLoading: pageLoading } = usePage(pageId)
  const { data: allPages = [] } = usePages()

  const listPage = useMemo(
    () => resolveReturnListPage(allPages, pageId, listPageIdFromUrl),
    [allPages, pageId, listPageIdFromUrl],
  )

  const navigateBack = () => {
    if (listPage) {
      router.push(listDashboardPath(listPage))
      return
    }
    if (listPageIdFromUrl != null) {
      router.push(`/dashboard?page=${listPageIdFromUrl}`)
      return
    }
    if (isSetupSingletonCardPage(page)) router.push('/dashboard')
    else router.back()
  }

  const groups = page?.PageControls.filter((c) => c.ControlType === 'Group') ?? []
  const factBoxes = page?.PageControls.filter((c) => c.ControlType === 'FactBox') ?? []
  const cardControl = groups[0]

  const {
    data: record,
    isLoading: recordLoading,
    isError: recordError,
    error: recordFetchError,
    refetch: refetchRecord,
  } = usePageDataRecord(pageId, cardControl?.PageControlId, isNew ? undefined : systemId)

  const [localRecord, setLocalRecord] = useState<DataRecord | null>(null)
  const [pendingId] = useState(() => (isNew ? crypto.randomUUID() : systemId))
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [recordCreated, setRecordCreated] = useState(!isNew)
  const hasCreatedRef = useRef(!isNew)
  const [actionLoading, setActionLoading] = useState(false)

  useEffect(() => {
    if (record) setLocalRecord(record)
  }, [record])

  // Document pages (header + lines subform) live on /document/, not /record/.
  useEffect(() => {
    if (page?.PageType === 'Document') {
      const fromList = searchParams.get('fromList')
      router.replace(
        getCardRecordPath(
          pageId,
          systemId,
          'Document',
          fromList ? { fromList } : undefined,
        ),
      )
    }
  }, [page?.PageType, pageId, systemId, router, searchParams])

  const updateField = useUpdateField(pageId, cardControl?.PageControlId)
  const deleteRecord = useDeleteRecord(pageId, cardControl?.PageControlId ?? 0)

  const currentData: DataRecord = {
    ...(localRecord ?? record ?? {}),
    SystemId: pendingId,
  }

  const title = useMemo(() => {
    if (isNew) return `New ${page?.Caption ?? ''}`
    const tf = page?.TitleField
    if (tf && currentData[tf]) return String(currentData[tf])
    return page?.Caption ?? '—'
  }, [page, currentData, isNew])

  const handleFieldBlur = (control: PageControl, field: PageControlField, value: unknown) => {
    const editable = isCardFieldEditable(field, control, {
      readOnly: !page?.ModifyAllowed && !isNew,
      isNew,
      insertAllowed: page?.InsertAllowed ?? false,
      pageName: page?.Name,
      data: currentData,
    })
    if (!editable) return

    if (!isNew && value === (localRecord ?? record)?.[field.Name]) return

    let normalized = value
    if (page?.Name === 'UsersCard') {
      if (field.Name === 'full_name' && typeof value === 'string') {
        normalized = value.trim().toUpperCase()
      }
      if (field.Name === 'email' && typeof value === 'string') {
        normalized = value.trim().toLowerCase()
      }
    }

    const isFirstSave = isNew && !hasCreatedRef.current
    if (isFirstSave) {
      const missingPk = missingPrimaryKeyForCreate(page, currentData, field, normalized)
      if (missingPk) {
        setLocalRecord({
          ...currentData,
          SystemId: pendingId,
          [field.Name]: normalized,
        })
        toast.error(`Enter ${missingPk.Caption || 'Code'} before creating the record.`)
        return
      }
      hasCreatedRef.current = true
      setRecordCreated(true)
    }

    updateField.mutate(
      {
        systemId: pendingId,
        field,
        value: normalized,
        recordValues: {
          ...currentData,
          [field.Name]: normalized,
        },
      },
      {
        onSuccess: (response) => {
          if (response.record) {
            setLocalRecord(response.record)
          }
          if (isFirstSave) {
            router.replace(`/record/${pageId}/${pendingId}`)
          }
        },
        onError: (err: unknown) => {
          if (isFirstSave) {
            hasCreatedRef.current = false
            setRecordCreated(false)
          }
          toast.error(err instanceof Error ? err.message : 'Failed to save')
        },
      },
    )
  }

  const handleDeleteConfirm = () => {
    setShowDeleteConfirm(false)
    deleteRecord.mutate(systemId, {
      onSuccess: () => {
        toast.success('Record deleted')
        navigateBack()
      },
      onError: (err: unknown) => {
        toast.error(err instanceof Error ? err.message : 'Failed to delete')
      },
    })
  }

  const cardFields = useMemo(
    () => groups.flatMap((g) => g.Fields),
    [groups],
  )

  const returnUrl = getCardRecordPath(pageId, pendingId, page?.PageType)

  const runCardAction = async (action: PageAction) => {
    const relativeUrl = (action.ActionRelativeUrl || '').trim()
    if (!relativeUrl) return

    if (isNew) {
      toast.error('Save the record before using this action.')
      return
    }

    setActionLoading(true)
    try {
      const href = buildCardActionUrl(
        '/dashboard',
        relativeUrl,
        allPages,
        currentData,
        cardFields,
        returnUrl,
      )
      if (!href) {
        toast.error('Could not open the linked page.')
        return
      }
      router.push(href)
    } finally {
      setActionLoading(false)
    }
  }

  const pageActions = (page?.PageActions ?? []).filter((a) => a.Visible)

  if (page?.PageType === 'Document') {
    return <DetailSkeleton />
  }

  if (!pageLoading && isCardPage(page)) {
    return <DynamicCardPage pageId={pageId} systemId={systemId} />
  }

  if (pageLoading || (!isNew && recordLoading)) return <DetailSkeleton />

  const isSaving = updateField.isPending
  const recordReady = recordCreated
  const saveFirstHint = page?.Caption
    ? `Save ${page.Caption.toLowerCase()} first`
    : 'Save the record first'

  const errorMessage =
    recordFetchError instanceof Error ? recordFetchError.message : 'Failed to load record'

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-1 min-h-0 flex-col overflow-y-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={navigateBack}
            className="p-2 rounded-lg hover:bg-gray-100 text-bodyText transition"
            title="Back to list"
          >
            <ArrowLeft size={16} />
          </button>
          <h2 className="text-xl font-semibold text-mainTextColor">{title}</h2>
        </div>

        <div className="flex items-center gap-2">
          {isSaving && (
            <span className="flex items-center gap-1 text-xs text-bodyText">
              <Loader2 size={12} className="animate-spin" /> Saving…
            </span>
          )}
          {page?.DeleteAllowed && !isNew && (
            <button
              onClick={() => setShowDeleteConfirm(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-red-600 text-white text-sm rounded-lg hover:bg-red-700 transition"
            >
              <Trash2 size={14} /> Delete
            </button>
          )}
        </div>
      </div>

      {pageActions.length > 0 && (
        <CardRibbon
          pageId={pageId}
          systemId={pendingId}
          controlId={cardControl?.PageControlId}
          pageActions={pageActions}
          onNavigateAction={runCardAction}
          actionLoading={actionLoading}
          disabled={isNew}
        />
      )}

      {recordError && !isNew ? (
        <ErrorBanner
          variant="card"
          message={errorMessage}
          onRetry={() => refetchRecord()}
          onBack={navigateBack}
        />
      ) : (
        <>
          {/* Field groups + fact boxes */}
          <div className="flex flex-col lg:flex-row gap-6 items-start">
            <div className="flex-1 min-w-0 w-full space-y-6">
              {groups.map((control) => (
                <ControlSection
                  key={control.PageControlId}
                  page={page}
                  pageId={pageId}
                  control={control}
                  data={currentData}
                  readOnly={!page?.ModifyAllowed && !isNew}
                  isNew={isNew}
                  systemId={pendingId}
                  onFieldBlur={(field, value) => handleFieldBlur(control, field, value)}
                />
              ))}
            </div>

            <FactBoxAside
              controls={factBoxes}
              data={currentData}
              recordReady={recordReady}
              readOnly={!page?.ModifyAllowed && !isNew}
              saveFirstHint={saveFirstHint}
              storageKey={`factbox:${page?.Name ?? pageId}`}
            />
          </div>
        </>
      )}

      {/* Delete confirm */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="rounded-xl bg-white p-6 shadow-xl max-w-sm w-full mx-4">
            <h3 className="text-base font-semibold text-mainTextColor">Delete record?</h3>
            <p className="mt-1 text-sm text-bodyText">This action cannot be undone.</p>
            <div className="mt-5 flex justify-end gap-3">
              <button
                onClick={() => setShowDeleteConfirm(false)}
                className="rounded-lg border border-gray-200 px-4 py-2 text-sm font-medium text-bodyText hover:bg-gray-50 transition"
              >
                Cancel
              </button>
              <button
                onClick={handleDeleteConfirm}
                disabled={deleteRecord.isPending}
                className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-60 transition"
              >
                {deleteRecord.isPending ? 'Deleting…' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ─── Control Section ──────────────────────────────────────────────────────────

function ControlSection({
  page,
  pageId,
  control,
  data,
  readOnly,
  isNew,
  systemId,
  onFieldBlur,
}: {
  page?: Page
  pageId: number
  control: PageControl
  data: DataRecord
  readOnly: boolean
  isNew: boolean
  systemId: string
  onFieldBlur: (field: PageControlField, value: unknown) => void
}) {
  const visible = control.Fields.filter((f) => f.Visible)
  const relationOptions = useRelationOptions(pageId, visible, systemId === 'new' ? null : systemId)

  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
      {control.ShowCaption && control.Caption && (
        <div className="px-6 py-3 bg-gray-50 border-b border-gray-100">
          <h3 className="text-sm font-medium text-bodyText">{control.Caption}</h3>
        </div>
      )}
      <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-5">
        {visible.map((field) => {
          const isDisabled = !isCardFieldEditable(field, control, {
            readOnly,
            isNew,
            insertAllowed: page?.InsertAllowed ?? false,
            pageName: page?.Name,
            data,
          })
          const isBoolean = field.FieldType === 'Boolean'
          const opts = field.HasTableRelation
            ? (relationOptions[field.PageControlFieldId] ?? null)
            : null

          if (isBoolean) {
            return (
              <div key={field.PageControlFieldId}>
                <BooleanFieldRow
                  caption={field.Caption}
                  value={data[field.Name]}
                  disabled={isDisabled}
                  required={field.Required}
                  className="rounded-lg border border-gray-100 bg-white px-3 py-1.5"
                  onChange={(v) => onFieldBlur(field, v)}
                />
              </div>
            )
          }

          return (
            <div key={field.PageControlFieldId} className="space-y-1.5">
              <label className="block text-xs font-medium text-bodyText">
                {field.Caption}
                {field.Required && <span className="text-red-500 ml-0.5">*</span>}
              </label>

              {/* Relation select */}
              {opts !== null ? (
                <SearchableRelationSelect
                  options={opts}
                  value={String(data[field.Name] ?? '')}
                  disabled={isDisabled}
                  placeholder="Search…"
                  onChange={(val) => onFieldBlur(field, val)}
                />
              ) : field.HasDrillDownPage && !field.Editable ? (
                <div className="px-3 py-1.5 text-sm border border-gray-200 rounded-lg bg-gray-50">
                  <DrillDownField
                    field={field}
                    value={data[field.Name]}
                    record={data}
                    sourcePage={page}
                    sourceFields={visible}
                    sourcePageId={pageId}
                    sourceSystemId={systemId}
                  />
                </div>
              ) : field.FieldType === 'Password' ? (
                <PasswordField
                  value={data[field.Name] as string | null}
                  disabled={isDisabled || isNew}
                  saveFirstHint={page?.Caption ? `Save ${page.Caption.toLowerCase()} first` : undefined}
                  onSave={async (password) => {
                    await onFieldBlur(field, password)
                  }}
                />
              ) : (
                <DynamicField
                  field={{ ...field, Editable: !isDisabled }}
                  value={data[field.Name]}
                  disabled={isDisabled}
                  onBlur={(v) => onFieldBlur(field, v)}
                />
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ─── Skeleton ─────────────────────────────────────────────────────────────────

function DetailSkeleton() {
  return (
    <div className="flex flex-col w-full h-full space-y-6">
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 bg-gray-200 rounded-lg animate-pulse shrink-0" />
        <div className="h-7 w-56 bg-gray-200 rounded animate-pulse" />
      </div>
      <div className="bg-white rounded-xl border border-gray-200 p-6 flex-1">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-5">
          {[...Array(10)].map((_, i) => (
            <div key={i} className="space-y-1.5">
              <div className="h-3 w-24 bg-gray-100 rounded animate-pulse" />
              <div className="h-9 bg-gray-100 rounded-lg animate-pulse" style={{ opacity: 1 - i * 0.07 }} />
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
