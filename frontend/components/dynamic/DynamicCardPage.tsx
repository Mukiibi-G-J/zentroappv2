'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { ArrowLeft, ChevronDown, ChevronLeft, ChevronRight, Loader2, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { usePage, usePages } from '@/hooks/usePage'
import { usePageDataNeighbors, usePageDataRecord, useUpdateField, useDeleteRecord } from '@/hooks/usePageData'
import { useDocumentLines } from '@/hooks/useDocumentLines'
import { useSyncHeaderTotalFromLines } from '@/hooks/useSyncHeaderTotalFromLines'
import { useRelationOptions, type RelationOption } from '@/hooks/useRelationOptions'
import { DynamicListPart } from './DynamicListPart'
import DynamicField from './DynamicField'
import BooleanFieldRow from './BooleanFieldRow'
import DrillDownField from './DrillDownField'
import SearchableRelationSelect from './SearchableRelationSelect'
import RelationLookupModal from './RelationLookupModal'
import FactBoxAside from './FactBoxAside'
import CardRibbon from './CardRibbon'
import JournalPreviewDialog, { type JournalPreviewContent } from './JournalPreviewDialog'
import PasswordField from './PasswordField'
import CompanyLogoField from './CompanyLogoField'
import ErrorBanner from '@/components/ui/ErrorBanner'
import { buildCardActionUrl } from '@/lib/cardAction'
import { buildLookupDrillDownFilters } from '@/lib/relationLookupFilters'
import type { RelationMenuFooter } from '@/lib/relationMenuFooter'
import {
  getCardRecordPath,
  getPageRouteId,
  listDashboardPath,
  parseFromListPageId,
  resolveReturnListPage,
} from '@/lib/pageRoutes'
import { useSession } from '@/context/SessionContext'
import { pageDataService } from '@/services/pagedata.service'
import { pageService } from '@/services/page.service'
import { isFieldEditable } from '@/lib/fieldVisibility'
import { missingPrimaryKeyForCreate } from '@/lib/cardPage'
import type { Page, PageAction, PageControl, PageControlField } from '@/types/page'
import { extractErrorMessage } from '@/services/pagedata.service'
import { isSetupSingletonCardPage, SETUP_CARD_PAGE_NAMES } from '@/lib/setupPages'
import type { DataRecord } from '@/types/pagedata'
import { isItemTrackingLinesAction, ITEM_TRACKING_LINES_WORKSHEET_PAGE_NAME } from '@/lib/documentLineActions'
import { getItemByNo, itemRequiresTracking } from '@/services/items.service'
import type { PurchaseTrackingContext } from '@/types/tracking'
import DynamicTrackingModal from './DynamicTrackingModal'

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

export default function DynamicCardPage({ pageId, systemId }: Props) {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { refreshSession } = useSession()
  const isNew = systemId === 'new'
  const isSetupCard = (name?: string) => isSetupSingletonCardPage(name ? { Name: name } : undefined)

  const listPageIdFromUrl = parseFromListPageId(searchParams.get('fromList'))
  const returnPath = searchParams.get('return')

  const { data: page, isLoading: pageLoading } = usePage(pageId)
  const { data: allPages = [] } = usePages()

  const listPage = useMemo(
    () => resolveReturnListPage(allPages, pageId, listPageIdFromUrl),
    [allPages, pageId, listPageIdFromUrl],
  )

  const navigateBack = () => {
    // Explicit return (e.g. POS) wins; otherwise prefer the list we came from.
    if (returnPath?.startsWith('/')) {
      router.push(returnPath)
      return
    }
    if (listPage) {
      router.push(listDashboardPath(listPage))
      return
    }
    if (listPageIdFromUrl != null) {
      router.push(`/dashboard?page=${listPageIdFromUrl}`)
      return
    }
    if (isSetupCard(page?.Name)) router.push('/dashboard')
    else router.back()
  }

  const groups = useMemo(
    () =>
      (page?.PageControls.filter((c) => c.ControlType === 'Group') ?? [])
        .filter((c) => c.Fields.some((f) => f.Visible))
        .sort((a, b) => (a.TabIndex ?? 0) - (b.TabIndex ?? 0)),
    [page?.PageControls],
  )
  const partControl = page?.PageControls.find(
    (c) =>
      c.ControlType === 'Part' &&
      c.Visible !== false &&
      !(page?.Name === 'ItemCard' && c.Name === 'ItemUnitOfMeasurePart'),
  )
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
  const ribbonControlId = groups[0]?.PageControlId

  const {
    data: record,
    isLoading: recordLoading,
    isError: recordError,
    error: recordFetchError,
    refetch: refetchRecord,
  } = usePageDataRecord(pageId, ribbonControlId, isNew ? undefined : systemId, { cardPage: true })

  const showRecordNav =
    !isNew && !isSetupCard(page?.Name) && listPage != null && systemId !== 'new'
  const { data: neighbors } = usePageDataNeighbors(
    showRecordNav ? listPage?.PageId : undefined,
    showRecordNav ? systemId : undefined,
    showRecordNav,
  )
  const [postingPreview, setPostingPreview] = useState<JournalPreviewContent | null>(null)

  const navigateToNeighbor = useCallback(
    (targetSystemId: string | null | undefined) => {
      if (!targetSystemId || !page) return
      const fromList =
        searchParams.get('fromList') ??
        (listPage ? String(getPageRouteId(listPage)) : undefined)
      const returnParam = searchParams.get('return')
      router.push(
        getCardRecordPath(pageId, targetSystemId, page.PageType, {
          ...(fromList ? { fromList } : {}),
          ...(returnParam ? { return: returnParam } : {}),
        }),
      )
    },
    [listPage, page, pageId, router, searchParams],
  )

  useEffect(() => {
    if (!showRecordNav) return
    const onKeyDown = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement | null)?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return
      if ((e.target as HTMLElement | null)?.isContentEditable) return
      if (e.altKey && e.key === 'ArrowLeft') {
        e.preventDefault()
        navigateToNeighbor(neighbors?.previousSystemId)
      } else if (e.altKey && e.key === 'ArrowRight') {
        e.preventDefault()
        navigateToNeighbor(neighbors?.nextSystemId)
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [navigateToNeighbor, neighbors?.nextSystemId, neighbors?.previousSystemId, showRecordNav])

  const [localRecord, setLocalRecord] = useState<DataRecord | null>(null)
  const [pendingId] = useState(() => (isNew ? crypto.randomUUID() : systemId))
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [recordCreated, setRecordCreated] = useState(!isNew)
  const hasCreatedRef = useRef(!isNew)
  const ctxPrefillStartedRef = useRef(false)
  const [actionLoading, setActionLoading] = useState(false)
  const [lookupModal, setLookupModal] = useState<{
    field: PageControlField
    autoNew: boolean
  } | null>(null)
  const [trackingOpen, setTrackingOpen] = useState(false)
  const [trackingContext, setTrackingContext] = useState<PurchaseTrackingContext | null>(null)
  const [trackingWorksheetPage, setTrackingWorksheetPage] = useState<Page | null>(null)

  useEffect(() => {
    if (record) setLocalRecord(record)
  }, [record])

  // New cards must start blank — never keep Parent Category (or other fields) from a prior record.
  useEffect(() => {
    if (!isNew) return
    setLocalRecord(null)
    setRecordCreated(false)
    hasCreatedRef.current = false
    ctxPrefillStartedRef.current = false
  }, [isNew, systemId])

  useEffect(() => {
    if (page?.PageType === 'Document') {
      router.replace(getCardRecordPath(pageId, systemId, 'Document'))
    }
  }, [page?.PageType, pageId, systemId, router])

  const updateField = useUpdateField(pageId, ribbonControlId, {
    cardPage: true,
    listPageId: listPageIdFromUrl,
  })
  const deleteRecord = useDeleteRecord(pageId, ribbonControlId ?? 0)

  const ctxValue = searchParams.get('ctx')
  const ctxLabel = searchParams.get('ctxLabel')

  // Prefill + create new card from ctx (e.g. Bring in Opening Balance from Item Card).
  useEffect(() => {
    if (!isNew || !page || !ctxValue || ctxPrefillStartedRef.current) return
    if (!ribbonControlId) return

    const ctxField = (listPage?.ContextFilterField || '').trim()
    const relationField = ctxField
      ? ctxField.includes('__')
        ? ctxField.split('__')[0]
        : ctxField
      : page.SourceTable === 'ItemJournal'
        ? 'item'
        : null
    if (!relationField) return

    const itemField = groups
      .flatMap((g) => g.Fields)
      .find((f) => f.Name === relationField && f.HasTableRelation)
    if (!itemField) return

    ctxPrefillStartedRef.current = true
    hasCreatedRef.current = true
    setRecordCreated(true)
    setLocalRecord({
      SystemId: pendingId,
      [relationField]: ctxValue,
      ...(ctxLabel && relationField === 'item' ? { description: ctxLabel } : {}),
    })

    let cancelled = false
    void (async () => {
      try {
        const response = await updateField.mutateAsync({
          systemId: pendingId,
          field: itemField,
          value: ctxValue,
        })
        if (cancelled) return
        if (response.record) setLocalRecord(response.record)
        const query: Record<string, string> = {}
        if (listPageIdFromUrl) query.fromList = String(listPageIdFromUrl)
        const returnParam = searchParams.get('return')
        if (returnParam) query.return = returnParam
        router.replace(
          getCardRecordPath(
            pageId,
            pendingId,
            page.PageType,
            Object.keys(query).length ? query : undefined,
          ),
        )
      } catch (err: unknown) {
        if (cancelled) return
        ctxPrefillStartedRef.current = false
        hasCreatedRef.current = false
        setRecordCreated(false)
        toast.error(extractErrorMessage(err))
      }
    })()

    return () => {
      cancelled = true
    }
    // Intentionally omit updateField — mutateAsync is stable; listing it re-fires Strict Mode races.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    isNew,
    page,
    ctxValue,
    ctxLabel,
    listPage?.ContextFilterField,
    ribbonControlId,
    groups,
    pendingId,
    listPageIdFromUrl,
    pageId,
  ])

  const headerSystemId = recordCreated ? pendingId : null
  const lines = useDocumentLines({
    partPageId: partPage?.PageId ?? 0,
    repeaterControlId: repeaterControl?.PageControlId ?? 0,
    linkField: partControl?.LinkField ?? '',
    headerSystemId,
    sourceTable: partPage?.SourceTable,
    onMutate: () => { void refetchRecord() },
  })

  useSyncHeaderTotalFromLines(setLocalRecord, {
    lineTotal: lines.total,
    linesLoading: lines.isLoading,
    recordReady: recordCreated,
    headerGroups: groups,
  })

  const currentData: DataRecord = {
    ...(localRecord ?? record ?? {}),
    SystemId: pendingId,
  }

  const isPosted = String(currentData.status ?? '') === 'Posted'
  const viewMode = searchParams.get('mode') === 'view'
  const cardReadOnly = viewMode || isPosted || (!page?.ModifyAllowed && !isNew)

  const title = useMemo(() => {
    if (isSetupCard(page?.Name)) return page?.Caption ?? '—'
    if (isNew) return `New ${page?.Caption ?? ''}`
    const tf = page?.TitleField
    const base =
      tf && currentData[tf] ? String(currentData[tf]) : (page?.Caption ?? '—')
    return viewMode ? `${base} (View)` : base
  }, [page, currentData, isNew, viewMode])

  const handleFieldBlur = (control: PageControl, field: PageControlField, value: unknown) => {
    const editable = isCardFieldEditable(field, control, {
      readOnly: cardReadOnly,
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
        onSuccess: async (response) => {
          if (response.record) setLocalRecord(response.record)
          if (isFirstSave) {
            const query: Record<string, string> = {}
            if (listPageIdFromUrl) query.fromList = String(listPageIdFromUrl)
            const returnParam = searchParams.get('return')
            if (returnParam) query.return = returnParam
            router.replace(
              getCardRecordPath(
                pageId,
                pendingId,
                page?.PageType,
                Object.keys(query).length ? query : undefined,
              ),
            )
          }
          if (field.Name === 'role' && page?.Name === 'UserSettingsCard') {
            await refreshSession()
            toast.success('Role Centre updated')
            router.push('/dashboard')
          }
          if (page?.Name === 'CompanyCard') {
            await refreshSession()
          }
        },
        onError: (err: unknown) => {
          if (isFirstSave) {
            hasCreatedRef.current = false
            setRecordCreated(false)
          }
          toast.error(extractErrorMessage(err))
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

  const cardFields = useMemo(() => groups.flatMap((g) => g.Fields), [groups])
  const returnUrl = getCardRecordPath(pageId, pendingId, page?.PageType)
  const partRefs = useRef<Map<string, HTMLDivElement>>(new Map())
  const saveFirstHint = useMemo(
    () =>
      page?.Caption
        ? `Save ${page.Caption.toLowerCase()} first`
        : 'Save the record first',
    [page?.Caption],
  )

  const getRelationMenuFooter = useCallback(
    (field: PageControlField, currentValue: unknown): RelationMenuFooter | undefined => {
      if (!field.RelationLookupFooter) {
        return undefined
      }

      const lookupPage =
        field.HasLookupPage && field.LookupPageId
          ? allPages.find((p) => p.PageId === field.LookupPageId)
          : undefined

      const drillFilters = lookupPage
        ? buildLookupDrillDownFilters(lookupPage, currentData, cardFields, field)
        : {}
      const ctxKey = (lookupPage?.ContextFilterField || '').trim()
      const requiresParentContext = Boolean(ctxKey)
      const contextReady = !requiresParentContext || Boolean(drillFilters[ctxKey])
      const parentContextBlocked =
        requiresParentContext && (!recordCreated || !contextReady)

      const openLookupModal = (autoNew: boolean) => {
        if (!lookupPage) return
        if (parentContextBlocked) {
          if (!recordCreated) {
            toast.error(saveFirstHint)
            return
          }
          toast.error(
            'Save the record and ensure its number is assigned before opening the full list.',
          )
          return
        }
        setLookupModal({ field, autoNew })
      }

      return {
        onNew: lookupPage ? () => openLookupModal(true) : undefined,
        newDisabled: cardReadOnly || parentContextBlocked,
        onSelectFromFullList: lookupPage ? () => openLookupModal(false) : undefined,
        fullListDisabled: cardReadOnly || parentContextBlocked,
        onShowDetails: lookupPage ? () => openLookupModal(false) : undefined,
        showDetailsDisabled:
          currentValue === null || currentValue === undefined || currentValue === '',
      }
    },
    [
      recordCreated,
      cardReadOnly,
      saveFirstHint,
      allPages,
      cardFields,
      currentData,
    ],
  )

  const lookupModalPage = useMemo(
    () =>
      lookupModal?.field.HasLookupPage && lookupModal.field.LookupPageId
        ? allPages.find((p) => p.PageId === lookupModal.field.LookupPageId)
        : undefined,
    [lookupModal, allPages],
  )

  const lookupModalFilters = useMemo(
    () =>
      lookupModalPage && lookupModal
        ? buildLookupDrillDownFilters(
            lookupModalPage,
            currentData,
            cardFields,
            lookupModal.field,
          )
        : {},
    [lookupModalPage, lookupModal, currentData, cardFields],
  )

  const runCardAction = async (action: PageAction) => {
    if (isItemTrackingLinesAction(action) && page?.SourceTable === 'ItemJournal') {
      if (isNew) {
        toast.error('Save the journal before entering tracking details')
        return
      }
      const itemNo = String(currentData.item ?? '').trim()
      if (!itemNo) {
        toast.error('Select an item first')
        return
      }
      let journalId = Number(currentData.id) || 0
      if (!journalId && systemId && systemId !== 'new') {
        // Older payloads omitted ItemJournal.id — reload once so tracking can open.
        try {
          const fresh = await pageDataService.getRecord(pageId, undefined, systemId)
          journalId = Number(fresh?.id) || 0
          if (fresh) setLocalRecord(fresh)
        } catch {
          /* fall through to toast below */
        }
      }
      if (!journalId) {
        toast.error('Save the journal before entering tracking details')
        return
      }
      setActionLoading(true)
      try {
        const item = await getItemByNo(itemNo)
        if (!item?.tracking_code || !itemRequiresTracking(item.tracking_code)) {
          toast.error('This item does not use item tracking')
          return
        }
        let worksheetPage = allPages.find((p) => p.Name === ITEM_TRACKING_LINES_WORKSHEET_PAGE_NAME) ?? null
        if (!worksheetPage?.PageId) {
          const fresh = await pageService.getPages()
          worksheetPage = fresh.find((p) => p.Name === ITEM_TRACKING_LINES_WORKSHEET_PAGE_NAME) ?? null
        }
        if (!worksheetPage?.PageId) {
          toast.error('Run seed_pages to configure Item Tracking Lines worksheet')
          return
        }
        const expectedQuantity = (Number(currentData.quantity) || 0)
          * (Number(currentData.item_unit_of_measure__quantity_per_unit ?? 1) || 1)
        setTrackingWorksheetPage(worksheetPage)
        setTrackingContext({
          mode: 'open',
          itemJournalId: journalId,
          itemNo: item.no,
          itemName: item.item_name,
          trackingCode: item.tracking_code,
          expectedQuantity: expectedQuantity || Number(currentData.quantity) || 1,
        })
        setTrackingOpen(true)
      } catch (err) {
        toast.error(extractErrorMessage(err))
      } finally {
        setActionLoading(false)
      }
      return
    }

    const relativeUrl = (action.ActionRelativeUrl || '').trim()
    if (!relativeUrl) return

    if (relativeUrl.startsWith('/')) {
      router.push(relativeUrl)
      return
    }

    if (isNew) {
      toast.error('Save the record before using this action.')
      return
    }

    setActionLoading(true)
    try {
      const pageName = relativeUrl.split('?', 1)[0]
      const targetPage = allPages.find((p) => p.Name === pageName)

      if (
        targetPage?.PageType === 'Card' &&
        SETUP_CARD_PAGE_NAMES.has(targetPage.Name)
      ) {
        const soloId = await pageDataService.getSetupSolo(targetPage.PageId)
        router.push(
          getCardRecordPath(targetPage.PageId, soloId, targetPage.PageType, {
            return: returnUrl,
          }),
        )
        return
      }

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
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not open the linked page.')
    } finally {
      setActionLoading(false)
    }
  }

  const pageActions = (page?.PageActions ?? []).filter((a) => a.Visible)

  if (page?.PageType === 'Document') return <CardSkeleton />

  if (pageLoading || partPageLoading || (!isNew && recordLoading)) return <CardSkeleton />

  const isSaving = updateField.isPending
  const recordReady = recordCreated
  const errorMessage =
    recordFetchError instanceof Error ? recordFetchError.message : 'Failed to load record'
  const hideDelete = isSetupCard(page?.Name) || !page?.DeleteAllowed || isNew || isPosted

  return (
    <div className="relative mx-auto flex w-full max-w-7xl flex-1 min-h-0 flex-col gap-6 overflow-y-auto">
      {showRecordNav ? (
        <>
          <button
            type="button"
            disabled={!neighbors?.previousSystemId}
            onClick={() => navigateToNeighbor(neighbors?.previousSystemId)}
            title={neighbors?.previousSystemId ? 'Previous record (Alt+←)' : 'No previous record'}
            aria-label="Previous record"
            className="fixed left-3 top-1/2 z-40 flex h-11 w-11 -translate-y-1/2 items-center justify-center rounded-full bg-[#505c6d] text-white shadow-lg transition hover:bg-[#3f4a58] disabled:cursor-default disabled:opacity-30 md:left-[17.5rem]"
          >
            <ChevronLeft size={24} strokeWidth={2.25} />
          </button>
          <button
            type="button"
            disabled={!neighbors?.nextSystemId}
            onClick={() => navigateToNeighbor(neighbors?.nextSystemId)}
            title={neighbors?.nextSystemId ? 'Next record (Alt+→)' : 'No next record'}
            aria-label="Next record"
            className="fixed right-3 top-1/2 z-40 flex h-11 w-11 -translate-y-1/2 items-center justify-center rounded-full bg-[#505c6d] text-white shadow-lg transition hover:bg-[#3f4a58] disabled:cursor-default disabled:opacity-30"
          >
            <ChevronRight size={24} strokeWidth={2.25} />
          </button>
        </>
      ) : null}

      <div className="flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <button
            onClick={navigateBack}
            className="p-2 rounded-lg hover:bg-gray-100 text-bodyText transition"
            title="Back"
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
          {!hideDelete && (
            <button
              onClick={() => setShowDeleteConfirm(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-red-600 text-white text-sm rounded-lg hover:bg-red-700 transition"
            >
              <Trash2 size={14} /> Delete
            </button>
          )}
        </div>
      </div>

      {recordError && !isNew ? (
        <ErrorBanner
          variant="card"
          message={errorMessage}
          onRetry={() => refetchRecord()}
          onBack={navigateBack}
        />
      ) : (
        <>
          {pageActions.length > 0 && (
            <CardRibbon
              pageId={pageId}
              systemId={pendingId}
              controlId={ribbonControlId}
              pageActions={pageActions}
              record={currentData}
              onNavigateAction={runCardAction}
              onPreview={setPostingPreview}
              onServerActionSuccess={(action) => {
                toast.success(`${action.Caption} completed`)
                void refetchRecord()
              }}
              actionLoading={actionLoading}
              disabled={isNew && !isSetupCard(page?.Name)}
            />
          )}

          <div className="flex flex-col lg:flex-row gap-6 items-start">
            <div className="flex-1 min-w-0 w-full space-y-6">
              {groups.map((control) => (
                <CardFastTab
                  key={control.PageControlId}
                  page={page}
                  pageId={pageId}
                  control={control}
                  data={currentData}
                  readOnly={cardReadOnly}
                  isNew={isNew}
                  systemId={pendingId}
                  setupStyle={isSetupCard(page?.Name)}
                  onFieldBlur={(field, value) => handleFieldBlur(control, field, value)}
                  onLogoUploaded={() => {
                    void refetchRecord()
                    void refreshSession()
                  }}
                  getRelationMenuFooter={getRelationMenuFooter}
                />
              ))}

              {partControl && partPage && repeaterControl ? (
                <div
                  ref={(el) => {
                    if (el) partRefs.current.set(partControl.Name, el)
                    else partRefs.current.delete(partControl.Name)
                  }}
                >
                  <DynamicListPart
                  caption={partControl.Caption}
                  partPage={partPage}
                  repeaterControl={repeaterControl}
                  lines={lines}
                  recordReady={recordReady}
                  linesReadOnly={cardReadOnly || page?.Name === 'UsersCard'}
                  saveFirstHint={saveFirstHint}
                  documentHeader={page?.Name === 'PurchaseInvoice' ? currentData : undefined}
                  onHeaderRefresh={() => void refetchRecord()}
                />
                </div>
              ) : null}
            </div>

            <FactBoxAside
              controls={factBoxes}
              data={currentData}
              recordReady={recordReady}
              readOnly={cardReadOnly}
              saveFirstHint={saveFirstHint}
              storageKey={`factbox:${page?.Name ?? pageId}`}
            />
          </div>
        </>
      )}

      {lookupModal && lookupModalPage ? (
        <RelationLookupModal
          open
          lookupPage={lookupModalPage}
          targetField={lookupModal.field}
          drillDownFilters={lookupModalFilters}
          autoNew={lookupModal.autoNew}
          onClose={() => setLookupModal(null)}
          onConfirm={(value) => {
            const field = lookupModal.field
            const control =
              groups.find((g) =>
                g.Fields.some((f) => f.PageControlFieldId === field.PageControlFieldId),
              ) ?? groups[0]
            if (control) handleFieldBlur(control, field, value)
            setLookupModal(null)
          }}
        />
      ) : null}

      <DynamicTrackingModal
        open={trackingOpen}
        context={trackingContext}
        worksheetPage={trackingWorksheetPage}
        onClose={() => {
          setTrackingOpen(false)
          setTrackingContext(null)
          setTrackingWorksheetPage(null)
        }}
      />

      <JournalPreviewDialog
        open={postingPreview !== null}
        preview={postingPreview}
        onClose={() => setPostingPreview(null)}
      />

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

function CardFastTab({
  page,
  pageId,
  control,
  data,
  readOnly,
  isNew,
  systemId,
  setupStyle,
  onFieldBlur,
  onLogoUploaded,
  getRelationMenuFooter,
}: {
  page?: Page
  pageId: number
  control: PageControl
  data: DataRecord
  readOnly: boolean
  isNew: boolean
  systemId: string
  setupStyle?: boolean
  onFieldBlur: (field: PageControlField, value: unknown) => void
  onLogoUploaded?: () => void
  getRelationMenuFooter?: (field: PageControlField, currentValue: unknown) => RelationMenuFooter | undefined
}) {
  const [collapsed, setCollapsed] = useState(false)
  const visible = control.Fields.filter((f) => f.Visible)
  const relationRecordValues = useMemo(
    () => ({
      ...data,
      no: data.no ?? data.item,
      item: data.item ?? data.no,
      SystemId: data.SystemId,
    }),
    [data],
  )
  const relationOptions = useRelationOptions(
    pageId,
    visible,
    systemId === 'new' ? null : systemId,
    relationRecordValues,
  )

  if (visible.length === 0) return null

  if (setupStyle) {
    const isCompanyGeneral =
      page?.Name === 'CompanyCard' && control.Name === 'CompanyGeneralGroup'
    const logoField = isCompanyGeneral ? visible.find((f) => f.Name === 'logo') : undefined
    const bodyFields = logoField ? visible.filter((f) => f.Name !== 'logo') : visible

    return (
      <section className="relative overflow-hidden rounded-xl border border-gray-200 bg-white">
        {control.ShowCaption && control.Caption ? (
          <div className="border-b border-gray-200 bg-[#eef6f7] px-5 py-2.5">
            <h3 className="text-sm font-semibold text-s1">{control.Caption}</h3>
          </div>
        ) : null}
        {isCompanyGeneral && logoField ? (
          <div className="grid grid-cols-1 gap-6 px-5 py-4 lg:grid-cols-[minmax(0,1fr)_180px]">
            <div className="space-y-0">
              {bodyFields.map((field) => (
                <CardFieldRow
                  key={field.PageControlFieldId}
                  page={page}
                  pageId={pageId}
                  control={control}
                  field={field}
                  data={data}
                  readOnly={readOnly}
                  isNew={isNew}
                  systemId={systemId}
                  setupStyle
                  relationOptions={relationOptions[field.PageControlFieldId]}
                  onFieldBlur={onFieldBlur}
                  onLogoUploaded={onLogoUploaded}
                  getRelationMenuFooter={getRelationMenuFooter}
                />
              ))}
            </div>
            <div className="flex items-start justify-center lg:justify-end pt-1">
              <CardFieldRow
                page={page}
                pageId={pageId}
                control={control}
                field={logoField}
                data={data}
                readOnly={readOnly}
                isNew={isNew}
                systemId={systemId}
                setupStyle
                pictureOnly
                relationOptions={relationOptions[logoField.PageControlFieldId]}
                onFieldBlur={onFieldBlur}
                onLogoUploaded={onLogoUploaded}
                getRelationMenuFooter={getRelationMenuFooter}
              />
            </div>
          </div>
        ) : (
          <div className="space-y-0 px-5 py-4">
            {visible.map((field) => (
              <CardFieldRow
                key={field.PageControlFieldId}
                page={page}
                pageId={pageId}
                control={control}
                field={field}
                data={data}
                readOnly={readOnly}
                isNew={isNew}
                systemId={systemId}
                setupStyle
                relationOptions={relationOptions[field.PageControlFieldId]}
                onFieldBlur={onFieldBlur}
                onLogoUploaded={onLogoUploaded}
              />
            ))}
          </div>
        )}
      </section>
    )
  }

  return (
    <section className="overflow-hidden rounded-xl border border-gray-200 bg-white">
      {control.ShowCaption && control.Caption ? (
        <button
          type="button"
          onClick={() => setCollapsed((v) => !v)}
          className="flex w-full items-center gap-2 border-b border-gray-100 bg-gray-50 px-6 py-3 text-left transition hover:bg-gray-50/80"
        >
          {collapsed ? (
            <ChevronRight size={14} className="shrink-0 text-bodyText" />
          ) : (
            <ChevronDown size={14} className="shrink-0 text-bodyText" />
          )}
          <span className="text-sm font-medium text-bodyText">{control.Caption}</span>
        </button>
      ) : null}

      {!collapsed && (
        <div className="grid grid-cols-1 gap-x-8 gap-y-5 p-6 md:grid-cols-2">
          {visible.map((field) => (
            <CardFieldRow
              key={field.PageControlFieldId}
              page={page}
              pageId={pageId}
              control={control}
              field={field}
              data={data}
              readOnly={readOnly}
              isNew={isNew}
              systemId={systemId}
              relationOptions={relationOptions[field.PageControlFieldId]}
              onFieldBlur={onFieldBlur}
              onLogoUploaded={onLogoUploaded}
              getRelationMenuFooter={getRelationMenuFooter}
            />
          ))}
        </div>
      )}
    </section>
  )
}

function CardFieldRow({
  page,
  pageId,
  control,
  field,
  data,
  readOnly,
  isNew,
  systemId,
  setupStyle,
  pictureOnly,
  relationOptions,
  onFieldBlur,
  onLogoUploaded,
  getRelationMenuFooter,
}: {
  page?: Page
  pageId: number
  control: PageControl
  field: PageControlField
  data: DataRecord
  readOnly: boolean
  isNew: boolean
  systemId: string
  setupStyle?: boolean
  pictureOnly?: boolean
  relationOptions: RelationOption[] | undefined
  onFieldBlur: (field: PageControlField, value: unknown) => void
  onLogoUploaded?: () => void
  getRelationMenuFooter?: (field: PageControlField, currentValue: unknown) => RelationMenuFooter | undefined
}) {
  const isDisabled = !isCardFieldEditable(field, control, {
    readOnly,
    isNew,
    insertAllowed: page?.InsertAllowed ?? false,
    pageName: page?.Name,
    data,
  })
  const isBoolean = field.FieldType === 'Boolean'

  const relationLoaded = !field.HasTableRelation || relationOptions !== undefined

  const fieldControl =
    field.HasTableRelation ? (
      <SearchableRelationSelect
        options={relationOptions ?? []}
        value={String(data[field.Name] ?? '')}
        disabled={isDisabled}
        compact={setupStyle}
        isLoading={!relationLoaded}
        placeholder="Search…"
        menuFooter={getRelationMenuFooter?.(field, data[field.Name])}
        onChange={(val) => onFieldBlur(field, val)}
      />
    ) : field.HasDrillDownPage && !field.Editable ? (
      <div className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-1.5 text-sm">
        <DrillDownField
          field={field}
          value={data[field.Name]}
          record={data}
          sourcePage={page}
          sourceFields={control.Fields}
          sourcePageId={pageId}
          sourceSystemId={systemId}
        />
      </div>
    ) : field.FieldType === 'Image' && page?.Name === 'CompanyCard' && field.Name === 'logo' ? (
      <CompanyLogoField
        logoUrl={typeof data[field.Name] === 'string' ? (data[field.Name] as string) : null}
        onUploaded={() => onLogoUploaded?.()}
      />
    ) : field.FieldType === 'Password' ? (
      <PasswordField
        value={data[field.Name] as string | null}
        disabled={isDisabled || isNew}
        saveFirstHint={page?.Caption ? `Save ${page.Caption.toLowerCase()} first` : undefined}
        onSave={async (password) => {
          await onFieldBlur(field, password)
        }}
      />
    ) : isBoolean ? (
      setupStyle ? (
        <BooleanFieldRow
          caption={field.Caption}
          value={data[field.Name]}
          disabled={isDisabled}
          required={field.Required}
          onChange={(v) => onFieldBlur(field, v)}
        />
      ) : (
        <BooleanFieldRow
          caption={field.Caption}
          value={data[field.Name]}
          disabled={isDisabled}
          required={field.Required}
          className="rounded-lg border border-gray-100 bg-white px-3 py-1.5"
          onChange={(v) => onFieldBlur(field, v)}
        />
      )
    ) : (
      <DynamicField
        field={{ ...field, Editable: !isDisabled }}
        value={data[field.Name]}
        disabled={isDisabled}
        singleLine={!(page?.Name === 'CompanyCard' && field.Name === 'address')}
        onBlur={(v) => onFieldBlur(field, v)}
      />
    )

  if (setupStyle) {
    if (pictureOnly) {
      return (
        <div className="min-w-0">
          {fieldControl}
        </div>
      )
    }
    if (isBoolean) {
      return (
        <div className="border-b border-gray-100 py-1.5 last:border-b-0">
          {fieldControl}
        </div>
      )
    }
    return (
      <div className="grid min-h-[40px] grid-cols-[minmax(180px,220px)_1fr] items-center gap-x-4 border-b border-gray-100 py-1.5 last:border-b-0">
        <label className="text-sm text-bodyText" title={field.Caption}>
          {field.Caption}
          {field.Required && <span className="ml-0.5 text-red-500">*</span>}
        </label>
        <div className="min-w-0 max-w-lg">{fieldControl}</div>
      </div>
    )
  }

  return (
    <div className="min-w-0">
      {isBoolean ? (
        fieldControl
      ) : (
        <div className="space-y-1.5">
          <label className="block text-xs font-medium text-bodyText" title={field.Caption}>
            {field.Caption}
            {field.Required && <span className="ml-0.5 text-red-500">*</span>}
          </label>
          <div className="min-w-0">{fieldControl}</div>
        </div>
      )}
    </div>
  )
}

function CardSkeleton() {
  return (
    <div className="mx-auto flex w-full max-w-7xl flex-1 min-h-0 flex-col gap-6">
      <div className="flex shrink-0 items-center gap-3">
        <div className="h-8 w-8 shrink-0 animate-pulse rounded-lg bg-gray-200" />
        <div className="h-7 w-56 animate-pulse rounded bg-gray-200" />
      </div>
      <div className="flex-1 min-h-0 overflow-hidden rounded-xl border border-gray-200 bg-white">
        <div className="h-11 animate-pulse border-b border-gray-100 bg-gray-50" />
        <div className="grid grid-cols-1 gap-x-8 gap-y-5 p-6 md:grid-cols-2">
          {[...Array(8)].map((_, i) => (
            <div key={i} className="space-y-1.5">
              <div className="h-3 w-24 animate-pulse rounded bg-gray-100" />
              <div className="h-9 animate-pulse rounded-lg bg-gray-100" style={{ opacity: 1 - i * 0.07 }} />
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
