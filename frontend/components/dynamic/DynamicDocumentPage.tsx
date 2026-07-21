'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { ArrowLeft, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { usePage, usePages } from '@/hooks/usePage'
import { usePageDataRecord, useUpdateField } from '@/hooks/usePageData'
import { useDocumentLines } from '@/hooks/useDocumentLines'
import { useSyncHeaderTotalFromLines } from '@/hooks/useSyncHeaderTotalFromLines'
import { useRelationOptions } from '@/hooks/useRelationOptions'
import DynamicField from './DynamicField'
import BooleanFieldRow from './BooleanFieldRow'
import SearchableRelationSelect from './SearchableRelationSelect'
import CardRibbon from './CardRibbon'
import FactBoxAside from './FactBoxAside'
import JournalPreviewDialog, { type JournalPreviewContent } from './JournalPreviewDialog'
import PaymentMethodPickDialog from './PaymentMethodPickDialog'
import ErrorBanner from '@/components/ui/ErrorBanner'
import { isFieldEditable } from '@/lib/fieldVisibility'
import { isDocumentReadOnly } from '@/lib/recordStatus'
import {
  getCardRecordPath,
  getPageRouteId,
  listDashboardPath,
  parseFromListPageId,
  resolveReturnListPage,
} from '@/lib/pageRoutes'
import { buildCardActionUrl } from '@/lib/cardAction'
import {
  APPLY_CUSTOMER_ENTRIES_PAGE_NAME,
  APPLY_VENDOR_ENTRIES_PAGE_NAME,
} from '@/lib/documentLineActions'
import { DynamicListPart } from './DynamicListPart'
import { PaymentJournalReceiptDialog } from '@/components/payments/PaymentJournalReceiptDialog'
import {
  isPaymentJournalPrintAction,
} from '@/lib/paymentJournalPrint'
import type { Page, PageAction, PageControl, PageControlField } from '@/types/page'
import type { ActionResult, DataRecord } from '@/types/pagedata'

interface Props {
  pageId: number
  systemId: string
}


function recordHasPaymentMethod(record: DataRecord): boolean {
  const value = record.payment_method
  return value != null && value !== ''
}

function paymentMethodCode(record: DataRecord): string {
  const value = record.payment_method
  if (value == null || value === '') return ''
  return String(value).trim().toUpperCase()
}

const PAYMENT_METHOD_LABELS: Record<string, string> = {
  NOT_PAID: 'Pay later',
  CASH: 'Cash',
  MOBILE_MONEY: 'Mobile Money',
  BANK: 'Bank',
}

function friendlyPaymentMethodLabel(code: string): string {
  const key = code.trim().toUpperCase()
  return PAYMENT_METHOD_LABELS[key] ?? key.replace(/_/g, ' ')
}

export default function DynamicDocumentPage({ pageId, systemId }: Props) {
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
    router.back()
  }

  const groups = page?.PageControls.filter((c) => c.ControlType === 'Group') ?? []
  const partControl = page?.PageControls.find((c) => c.ControlType === 'Part')
  const partPageIdToFetch =
    partControl?.PartPageId &&
    (!partControl.PartPage || !partControl.PartPage.PageControls?.length)
      ? partControl.PartPageId
      : undefined
  const { data: fetchedPartPage, isLoading: partPageLoading } = usePage(partPageIdToFetch)

  const partPage =
    partControl?.PartPage?.PageControls?.length
      ? partControl.PartPage
      : fetchedPartPage ?? undefined
  const repeaterControl = partPage?.PageControls.find(
    (c) => c.ControlType === 'Repeater' || c.ControlType === 'Group',
  )
  const factBoxes = page?.PageControls.filter((c) => c.ControlType === 'FactBox') ?? []
  const headerGroup = groups[0]

  const [pendingId] = useState(() => (isNew ? crypto.randomUUID() : systemId))
  const [recordCreated, setRecordCreated] = useState(!isNew)
  const hasCreatedRef = useRef(!isNew)

  const recordFetchId = isNew && !recordCreated ? undefined : pendingId

  const {
    data: record,
    isLoading: recordLoading,
    isError: recordError,
    error: recordFetchError,
    refetch: refetchRecord,
  } = usePageDataRecord(
    pageId,
    headerGroup?.PageControlId,
    // After soft-create, props.systemId stays "new" — fetch by pendingId once saved.
    recordFetchId,
  )

  const [localRecord, setLocalRecord] = useState<DataRecord | null>(null)
  const [postingPreview, setPostingPreview] = useState<JournalPreviewContent | null>(null)
  const [actionLoading, setActionLoading] = useState(false)
  const [paymentPickOpen, setPaymentPickOpen] = useState(false)
  const [paymentPickReason, setPaymentPickReason] = useState<'missing' | 'confirm'>('missing')
  const [pendingPostProceed, setPendingPostProceed] = useState<(() => void) | null>(null)
  const [paymentPickSaving, setPaymentPickSaving] = useState(false)
  const [receiptDialogSystemId, setReceiptDialogSystemId] = useState<string | null>(null)

  useEffect(() => {
    if (record) setLocalRecord(record)
  }, [record])

  const headerSystemId = recordCreated ? pendingId : null

  const updateField = useUpdateField(pageId, headerGroup?.PageControlId)
  const lines = useDocumentLines({
    partPageId: partPage?.PageId ?? 0,
    repeaterControlId: repeaterControl?.PageControlId ?? 0,
    linkField: partControl?.LinkField ?? '',
    headerSystemId,
    onMutate: () => {
      if (recordFetchId) void refetchRecord()
    },
  })

  useSyncHeaderTotalFromLines(setLocalRecord, {
    lineTotal: lines.total,
    linesLoading: lines.isLoading,
    recordReady: recordCreated,
    headerGroups: groups,
  })

  const applyVendorEntriesPage = useMemo(
    () => allPages.find((p) => p.Name === APPLY_VENDOR_ENTRIES_PAGE_NAME),
    [allPages],
  )
  const applyCustomerEntriesPage = useMemo(
    () => allPages.find((p) => p.Name === APPLY_CUSTOMER_ENTRIES_PAGE_NAME),
    [allPages],
  )

  const currentData: DataRecord = {
    ...(localRecord ?? record ?? {}),
    SystemId: pendingId,
  }

  const isPosted = isDocumentReadOnly(currentData, page?.Name)
  const headerReadOnly = isPosted || (!page?.ModifyAllowed && recordCreated)
  // After first save we keep this instance mounted; only the URL/title change.
  const showAsNew = isNew && !recordCreated

  const title = useMemo(() => {
    if (showAsNew) return `New ${page?.Caption ?? ''}`
    const tf = page?.TitleField
    if (tf && currentData[tf]) return String(currentData[tf])
    return page?.Caption ?? '—'
  }, [page, currentData, showAsNew])

  const cardFields = useMemo(() => groups.flatMap((g) => g.Fields), [groups])
  const paymentMethodField = useMemo(
    () => cardFields.find((field) => field.Name === 'payment_method'),
    [cardFields],
  )
  const returnUrl = getCardRecordPath(pageId, pendingId, page?.PageType, listPageIdFromUrl
    ? { fromList: String(listPageIdFromUrl) }
    : undefined)

  const syncCreatedRecordUrl = useCallback(() => {
    const path = getCardRecordPath(
      pageId,
      pendingId,
      page?.PageType,
      listPageIdFromUrl ? { fromList: String(listPageIdFromUrl) } : undefined,
    )
    // Avoid router.replace — that remounts the document and reloads relations.
    window.history.replaceState(window.history.state ?? {}, '', path)
  }, [listPageIdFromUrl, page?.PageType, pageId, pendingId])

  const handleFieldBlur = (control: PageControl, field: PageControlField, value: unknown) => {
    if (headerReadOnly) return
    if (isNew && !page?.InsertAllowed) return
    if (recordCreated && control.Editable === false) return
    if (!isFieldEditable(field, currentData, page?.Name)) return
    if (recordCreated && value === (localRecord ?? record)?.[field.Name]) return

    const isFirstSave = isNew && !hasCreatedRef.current
    if (isFirstSave) {
      hasCreatedRef.current = true
      setRecordCreated(true)
    }

    updateField.mutate(
      { systemId: pendingId, field, value },
      {
        onSuccess: (response) => {
          if (response.record) setLocalRecord(response.record)
          if (isFirstSave) syncCreatedRecordUrl()
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

  const runDocumentNavigateAction = useCallback(
    async (action: PageAction) => {
      const relativeUrl = (action.ActionRelativeUrl || '').trim()
      if (!relativeUrl) return

      if (
        page?.Name === 'PaymentJournalCard'
        && isPaymentJournalPrintAction(action.Name, relativeUrl)
      ) {
        if (showAsNew) {
          toast.error('Save the payment before printing a receipt.')
          return
        }
        setReceiptDialogSystemId(pendingId)
        return
      }

      if (relativeUrl.startsWith('/')) {
        router.push(relativeUrl)
        return
      }

      if (showAsNew) {
        toast.error('Save the document before using this action.')
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
    },
    [allPages, cardFields, currentData, showAsNew, page?.Name, pendingId, returnUrl, router],
  )

  const paymentPickSubtitle = useMemo(() => {
    if (paymentPickReason === 'missing') {
      return 'Choose how you paid before posting.'
    }
    const label = friendlyPaymentMethodLabel(paymentMethodCode(currentData))
    return `You selected ${label}. Tap it again to continue, or choose a different payment method.`
  }, [currentData, paymentPickReason])

  const shouldInterceptDocumentPost = useCallback(
    (action: PageAction) => {
      if (page?.Name === 'PurchaseInvoice') {
        if (action.Name === 'preview_purchase_invoice') {
          return !recordHasPaymentMethod(currentData)
        }
        if (action.Name === 'post_purchase_invoice') {
          return true
        }
      }
      if (page?.Name === 'SalesInvoice') {
        if (action.Name === 'preview_sales_invoice') {
          return !recordHasPaymentMethod(currentData)
        }
        if (action.Name === 'post_sales_invoice') {
          return true
        }
      }
      if (page?.Name === 'PaymentJournalCard') {
        if (action.Name === 'preview_payment_journal') {
          return !recordHasPaymentMethod(currentData)
        }
        if (action.Name === 'post_payment_journal') {
          return true
        }
      }
      return false
    },
    [currentData, page?.Name],
  )

  const handleInterceptedPostAction = useCallback(
    (action: PageAction, proceed: () => void) => {
      const hasMethod = recordHasPaymentMethod(currentData)
      const isPostAction =
        action.Name === 'post_purchase_invoice'
        || action.Name === 'post_sales_invoice'
        || action.Name === 'post_payment_journal'
      setPaymentPickReason(isPostAction && hasMethod ? 'confirm' : 'missing')
      setPendingPostProceed(() => proceed)
      setPaymentPickOpen(true)
    },
    [currentData],
  )

  const handleServerActionSuccess = useCallback(
    (action: PageAction, _response: ActionResult) => {
      if (page?.Name !== 'PaymentJournalCard') return
      if (action.Name !== 'post_payment_journal') return
      setReceiptDialogSystemId(pendingId)
    },
    [page?.Name, pendingId],
  )

  const handleNavigateCommand = useCallback(
    (content: { PageName?: string; SystemId?: string; Message?: string }) => {
      const pageName = (content.PageName || '').trim()
      const targetSystemId = (content.SystemId || '').trim()
      if (!pageName || !targetSystemId) {
        toast.error('Credit memo was created but could not be opened.')
        return
      }
      const target = allPages.find((p) => p.Name === pageName)
      if (!target) {
        toast.error(`Page ${pageName} is not available. Re-run seed_pages.`)
        return
      }
      router.push(
        getCardRecordPath(
          getPageRouteId(target),
          targetSystemId,
          target.PageType,
        ),
      )
    },
    [allPages, router],
  )

  const handlePaymentMethodPick = useCallback(
    async (code: string) => {
      const currentCode = paymentMethodCode(currentData)
      const unchanged = currentCode === code.trim().toUpperCase()

      if (unchanged) {
        setPaymentPickOpen(false)
        const proceed = pendingPostProceed
        setPendingPostProceed(null)
        proceed?.()
        return
      }

      if (!paymentMethodField || !headerGroup) {
        toast.error('Payment method field is not configured on this page.')
        return
      }
      setPaymentPickSaving(true)
      try {
        const response = await updateField.mutateAsync({
          systemId: pendingId,
          field: paymentMethodField,
          value: code,
        })
        if (response.record) setLocalRecord(response.record)
        setPaymentPickOpen(false)
        const proceed = pendingPostProceed
        setPendingPostProceed(null)
        proceed?.()
      } catch (err: unknown) {
        toast.error(err instanceof Error ? err.message : 'Failed to save payment method')
      } finally {
        setPaymentPickSaving(false)
      }
    },
    [currentData, headerGroup, paymentMethodField, pendingId, pendingPostProceed, updateField],
  )

  const pageActions = (page?.PageActions ?? []).filter((a) => a.Visible)
  const recordErrorMessage =
    recordFetchError instanceof Error ? recordFetchError.message : 'Failed to load record'

  const saveFirstHint = page?.Caption
    ? `Save ${page.Caption.toLowerCase()} fields first to add lines`
    : 'Save header fields first to add lines'

  if (pageLoading || partPageLoading || (!isNew && recordLoading)) return <DocumentSkeleton />

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-1 min-h-0 flex-col overflow-y-auto space-y-6 pb-6">
      <div className="flex items-center justify-between shrink-0">
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
        {updateField.isPending && (
          <span className="flex items-center gap-1 text-xs text-bodyText">
            <Loader2 size={12} className="animate-spin" /> Saving…
          </span>
        )}
      </div>

      {pageActions.length > 0 && (
        <CardRibbon
          pageId={pageId}
          systemId={pendingId}
          controlId={headerGroup?.PageControlId}
          pageActions={pageActions}
          record={currentData}
          onNavigateAction={runDocumentNavigateAction}
          onPreview={setPostingPreview}
          onServerActionSuccess={handleServerActionSuccess}
          onNavigateCommand={handleNavigateCommand}
          actionLoading={actionLoading}
          disabled={showAsNew || isPosted}
          shouldInterceptAction={shouldInterceptDocumentPost}
          onInterceptedAction={handleInterceptedPostAction}
        />
      )}

      {recordError && !showAsNew ? (
        <ErrorBanner
          variant="card"
          message={recordErrorMessage}
          onRetry={() => refetchRecord()}
          onBack={navigateBack}
        />
      ) : (
        <div className="flex flex-col lg:flex-row gap-6 items-start">
          <div className="flex-1 min-w-0 space-y-4">
            {groups.map((group) => (
              <HeaderGroupSection
                key={group.PageControlId}
                page={page}
                pageId={pageId}
                control={group}
                data={currentData}
                readOnly={headerReadOnly}
                isNew={showAsNew}
                systemId={pendingId}
                onFieldBlur={(field, value) => handleFieldBlur(group, field, value)}
              />
            ))}

            {partControl && partPage && repeaterControl ? (
              <DynamicListPart
                caption={partControl.Caption}
                partPage={partPage}
                repeaterControl={repeaterControl}
                lines={lines}
                recordReady={recordCreated}
                linesReadOnly={isPosted}
                saveFirstHint={saveFirstHint}
                applyEntriesEnabled={
                  page?.Name === 'PaymentJournalCard'
                  && (!!applyVendorEntriesPage || !!applyCustomerEntriesPage)
                }
                applyVendorEntriesPage={applyVendorEntriesPage}
                applyCustomerEntriesPage={applyCustomerEntriesPage}
                paymentHeader={page?.Name === 'PaymentJournalCard' ? currentData : undefined}
                documentHeader={
                  page?.Name === 'PurchaseInvoice'
                  || page?.Name === 'PostedPurchaseInvoice'
                  || page?.Name === 'PurchaseCreditMemo'
                  || page?.Name === 'SalesInvoice'
                  || page?.Name === 'PostedSalesInvoice'
                  || page?.Name === 'SalesCreditMemo'
                    ? currentData
                    : undefined
                }
                onHeaderRefresh={() => void refetchRecord()}
              />
            ) : partControl ? (
              <div className="rounded-xl border border-amber-200 bg-amber-50 px-6 py-8 text-center text-sm text-amber-900">
                <p className="font-medium">Lines subform is not configured for this document.</p>
                <p className="mt-1 text-amber-800">
                  {partControl.PartPageId
                    ? `Subform page #${partControl.PartPageId} could not be loaded.`
                    : 'Part control has no linked subform page.'}{' '}
                  Re-run:{' '}
                  <code className="text-xs">python manage.py seed_pages --schema &lt;tenant&gt;</code>
                </p>
              </div>
            ) : null}
          </div>

          <FactBoxAside
            controls={factBoxes}
            data={currentData}
            recordReady={recordCreated}
            readOnly={headerReadOnly}
            saveFirstHint={
              page?.Caption
                ? `Save the ${page.Caption.toLowerCase()} first`
                : 'Save the document first'
            }
            storageKey={`factbox:${page?.Name ?? pageId}`}
          />
        </div>
      )}

      <JournalPreviewDialog
        open={postingPreview !== null}
        preview={postingPreview}
        onClose={() => setPostingPreview(null)}
      />

      <PaymentMethodPickDialog
        open={paymentPickOpen}
        saving={paymentPickSaving}
        subtitle={paymentPickSubtitle}
        selectedCode={paymentMethodCode(currentData) || undefined}
        onClose={() => {
          if (paymentPickSaving) return
          setPaymentPickOpen(false)
          setPendingPostProceed(null)
        }}
        onSelect={handlePaymentMethodPick}
      />

      <PaymentJournalReceiptDialog
        open={receiptDialogSystemId != null}
        systemId={receiptDialogSystemId}
        onClose={() => setReceiptDialogSystemId(null)}
      />
    </div>
  )
}

function HeaderGroupSection({
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
  const relationOptions = useRelationOptions(pageId, visible, isNew ? null : systemId)

  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
      {control.ShowCaption && control.Caption && (
        <div className="px-6 py-3 bg-gray-50 border-b border-gray-100">
          <h3 className="text-sm font-medium text-bodyText">{control.Caption}</h3>
        </div>
      )}
      <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-5">
        {visible.map((field) => {
          const isDisabled =
            readOnly ||
            (isNew && !page?.InsertAllowed) ||
            (!isNew && control.Editable === false) ||
            !isFieldEditable(field, data, page?.Name)
          const opts = field.HasTableRelation
            ? (relationOptions[field.PageControlFieldId] ?? null)
            : null

          return (
            <div key={field.PageControlFieldId} className="space-y-1.5">
              {field.FieldType === 'Boolean' ? (
                <BooleanFieldRow
                  caption={field.Caption}
                  value={data[field.Name]}
                  disabled={isDisabled}
                  required={field.Required}
                  onChange={(val) => onFieldBlur(field, val)}
                />
              ) : (
                <>
                  <label className="block text-xs font-medium text-bodyText">
                    {field.Caption}
                    {field.Required && <span className="text-red-500 ml-0.5">*</span>}
                  </label>
                  {opts !== null ? (
                    <SearchableRelationSelect
                      options={opts}
                      value={String(data[field.Name] ?? '')}
                      disabled={isDisabled}
                      placeholder="Search…"
                      onChange={(val) => onFieldBlur(field, val)}
                    />
                  ) : (
                    <DynamicField
                      field={{ ...field, Editable: !isDisabled }}
                      value={data[field.Name]}
                      disabled={isDisabled}
                      singleLine
                      onBlur={(v) => onFieldBlur(field, v)}
                    />
                  )}
                </>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

function DocumentSkeleton() {
  return (
    <div className="w-full flex-1 min-h-0 overflow-y-auto">
      <div className="flex flex-col gap-4 pb-6">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-gray-200 rounded-lg animate-pulse shrink-0" />
          <div className="h-7 w-56 bg-gray-200 rounded animate-pulse" />
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-5">
            {[...Array(8)].map((_, i) => (
              <div key={i} className="space-y-1.5">
                <div className="h-3 w-24 bg-gray-100 rounded animate-pulse" />
                <div className="h-9 bg-gray-100 rounded-lg animate-pulse" />
              </div>
            ))}
          </div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200">
          <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
            <div className="h-4 w-12 bg-gray-100 rounded animate-pulse" />
            <div className="h-8 w-24 bg-gray-100 rounded-lg animate-pulse" />
          </div>
          <div className="p-4 space-y-3">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-10 bg-gray-100 rounded-lg animate-pulse" style={{ opacity: 1 - i * 0.2 }} />
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
