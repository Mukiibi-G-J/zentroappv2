'use client'

import { useEffect, useMemo, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import { useInvokeAction } from '@/hooks/usePageAction'
import { isRibbonImageUrl, resolveRibbonIcon } from '@/lib/ribbonIcon'
import { actionsForRibbonTab, defaultRibbonTab, ribbonTabsFromActions } from '@/lib/ribbonTabs'
import { filterVisiblePageActions, isPageActionEnabled, pageActionDisabledReason } from '@/lib/pageActionVisibility'
import { ConfirmDialog } from '@/components/ui/ConfirmDialog'
import type { PageAction } from '@/types/page'
import type { DataRecord, ActionResult } from '@/types/pagedata'
import type { JournalPreviewContent } from './JournalPreviewDialog'

interface Props {
  pageId: number
  systemId: string
  controlId?: number
  pageActions: PageAction[]
  record?: DataRecord | null
  onNavigateAction: (action: PageAction) => void
  onPreview?: (preview: JournalPreviewContent) => void
  onServerActionSuccess?: (action: PageAction, response: ActionResult) => void
  actionLoading?: boolean
  disabled?: boolean
  /** When true, ribbon sits inside a card shell (no outer border/radius). */
  embedded?: boolean
  /** Return true to pause the action until onInterceptedAction calls proceed(). */
  shouldInterceptAction?: (action: PageAction) => boolean
  onInterceptedAction?: (action: PageAction, proceed: () => void) => void
}

function ActionIcon({ action, spinning }: { action: PageAction; spinning: boolean }) {
  if (spinning) return <Loader2 size={14} className="animate-spin" />

  const imageUrl = action.ImageUrl?.trim()
  if (imageUrl && isRibbonImageUrl(imageUrl)) {
    return <img src={imageUrl} alt="" className="h-3.5 w-3.5 shrink-0 object-contain" />
  }

  const Icon = resolveRibbonIcon(imageUrl)
  return <Icon size={14} />
}

function isNavigationAction(action: PageAction): boolean {
  return Boolean((action.ActionRelativeUrl || '').trim())
}

export default function CardRibbon({
  pageId,
  systemId,
  controlId,
  pageActions,
  record,
  onNavigateAction,
  onPreview,
  onServerActionSuccess,
  actionLoading,
  disabled,
  embedded = false,
  shouldInterceptAction,
  onInterceptedAction,
}: Props) {
  const invokeAction = useInvokeAction(pageId, controlId)
  const [pendingActionName, setPendingActionName] = useState<string | null>(null)
  const [pendingConfirmAction, setPendingConfirmAction] = useState<PageAction | null>(null)

  const visibleActions = useMemo(
    () => filterVisiblePageActions(pageActions, record),
    [pageActions, record],
  )

  const tabs = useMemo(() => ribbonTabsFromActions(visibleActions), [visibleActions])
  const [activeTab, setActiveTab] = useState(() => defaultRibbonTab(tabs))

  useEffect(() => {
    setActiveTab((prev) => (tabs.includes(prev) ? prev : defaultRibbonTab(tabs)))
  }, [tabs])

  const tabActions = useMemo(
    () => actionsForRibbonTab(visibleActions, activeTab),
    [visibleActions, activeTab],
  )

  const mutationPending = invokeAction.isPending
  const anyLoading = Boolean(actionLoading || mutationPending)

  const continueAction = (action: PageAction) => {
    if (action.RequiresConfirmation && action.ConfirmationMessage) {
      setPendingConfirmAction(action)
      return
    }
    runServerAction(action)
  }

  const runServerAction = (action: PageAction) => {
    setPendingActionName(action.Name)
    invokeAction.mutate(
      { actionId: action.Name, systemId },
      {
        onSuccess: (response) => {
          if (
            typeof response === 'object'
            && response !== null
            && 'Command' in response
            && response.Command === 'PREVIEW'
          ) {
            const content = 'Content' in response ? response.Content : null
            if (content && typeof content === 'object' && 'Entries' in content) {
              onPreview?.(content as JournalPreviewContent)
            } else {
              toast.error('Preview returned no entries')
            }
            return
          }

          if (
            typeof response === 'object'
            && response !== null
            && 'ok' in response
            && response.ok
          ) {
            onServerActionSuccess?.(action, response as ActionResult)
          }
        },
        onSettled: () => setPendingActionName(null),
      },
    )
  }

  const handleAction = (action: PageAction) => {
    if (isNavigationAction(action)) {
      onNavigateAction(action)
      return
    }

    if (shouldInterceptAction?.(action)) {
      onInterceptedAction?.(action, () => continueAction(action))
      return
    }

    continueAction(action)
  }

  if (visibleActions.length === 0) return null

  return (
    <>
    <div
      className={cn(
        'bg-white',
        embedded ? 'border-b border-gray-200' : 'rounded-lg border border-gray-200 shadow-sm',
      )}
    >
      <div className="flex items-center gap-1 px-2 pt-2 border-b border-gray-200 bg-gray-50/80">
        {tabs.map((tab) => (
          <button
            key={tab}
            type="button"
            onClick={() => setActiveTab(tab)}
            className={cn(
              'px-3 py-1.5 text-xs font-medium rounded-t-md transition',
              activeTab === tab
                ? 'bg-white text-s1 border border-b-white border-gray-200 -mb-px'
                : 'text-bodyText hover:text-mainTextColor',
            )}
          >
            {tab}
          </button>
        ))}
      </div>

      <div className="flex flex-wrap items-stretch gap-1 px-2 py-2 min-h-[52px] bg-white">
        {tabActions.length === 0 ? (
          <p className="px-2 py-2 text-sm text-bodyText italic">No actions on this tab.</p>
        ) : (
          tabActions.map((action) => {
            const actionEnabled = isPageActionEnabled(action, record)
            const isDisabled = disabled || anyLoading || !actionEnabled
            const isThisPending = pendingActionName === action.Name && mutationPending
            const disabledReason = pageActionDisabledReason(action, record)

            return (
              <button
                key={action.ActionId}
                type="button"
                onClick={() => {
                  if (!actionEnabled) return
                  handleAction(action)
                }}
                disabled={isDisabled}
                title={disabledReason ?? action.Tooltip ?? action.Caption}
                className={cn(
                  'inline-flex flex-col items-center justify-center gap-1 min-w-[88px] px-2 py-1.5 text-xs font-medium rounded-md',
                  'text-mainTextColor hover:bg-s1/10 transition disabled:opacity-50 disabled:cursor-not-allowed',
                )}
              >
                <ActionIcon action={action} spinning={isThisPending} />
                <span className="text-center leading-tight">{action.Caption}</span>
              </button>
            )
          })
        )}
      </div>
    </div>

    <ConfirmDialog
      open={pendingConfirmAction != null}
      title={pendingConfirmAction?.Caption}
      message={pendingConfirmAction?.ConfirmationMessage ?? 'Proceed with this action?'}
      confirmLabel={pendingConfirmAction?.Caption ?? 'Confirm'}
      onConfirm={() => {
        const action = pendingConfirmAction
        setPendingConfirmAction(null)
        if (action) runServerAction(action)
      }}
      onCancel={() => setPendingConfirmAction(null)}
    />
    </>
  )
}
