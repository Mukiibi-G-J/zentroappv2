'use client'

import { useMemo, useState } from 'react'
import { useRouter } from 'next/navigation'
import { Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { usePages } from '@/hooks/usePage'
import { isRibbonImageUrl, resolveRibbonIcon } from '@/lib/ribbonIcon'
import { listDashboardPath } from '@/lib/pageRoutes'
import { ConfirmDialog } from '@/components/ui/ConfirmDialog'
import type { PageAction } from '@/types/page'
import type { ReturnTypeUseSalesPOS } from '@/components/pos/posTypes'

interface POSActionBarProps {
  pageActions: PageAction[]
  pos: ReturnTypeUseSalesPOS
  disabled?: boolean
}

const CLIENT_ACTION_NAMES = new Set([
  'pos_charge',
  'pos_save_draft',
  'pos_resume_drafts',
  'pos_clear_cart',
  'pos_record_payment',
])

function ActionIcon({ action }: { action: PageAction }) {
  const imageUrl = action.ImageUrl?.trim()
  if (imageUrl && isRibbonImageUrl(imageUrl)) {
    return <img src={imageUrl} alt="" className="h-3.5 w-3.5 shrink-0 object-contain" />
  }
  const Icon = resolveRibbonIcon(imageUrl)
  return <Icon size={14} />
}

export function POSActionBar({ pageActions, pos, disabled }: POSActionBarProps) {
  const router = useRouter()
  const { data: pages = [] } = usePages()
  const [pendingAction, setPendingAction] = useState<PageAction | null>(null)

  const ribbonActions = useMemo(
    () => pageActions.filter((a) => a.Visible && (a.ActionType ?? 'Ribbon') !== 'NavItem'),
    [pageActions],
  )

  const tabActions = useMemo(() => ribbonActions, [ribbonActions])

  if (ribbonActions.length === 0) return null

  const runAction = (action: PageAction) => {
    const relativeUrl = (action.ActionRelativeUrl || '').trim()
    if (relativeUrl && !CLIENT_ACTION_NAMES.has(action.Name)) {
      if (relativeUrl.startsWith('/')) {
        router.push(relativeUrl)
        return
      }
      const target = pages.find((p) => p.Name === relativeUrl.split('?', 1)[0])
      if (target) {
        router.push(listDashboardPath(target))
        return
      }
    }

    switch (action.Name) {
      case 'pos_charge':
        pos.openCheckout()
        break
      case 'pos_save_draft':
        void pos.saveDraft()
        break
      case 'pos_resume_drafts':
        pos.openDrafts()
        break
      case 'pos_clear_cart':
        pos.clearCart()
        break
      case 'pos_record_payment':
        pos.openRecordPayment()
        break
      default:
        break
    }
  }

  const handleActionClick = (action: PageAction) => {
    if (action.RequiresConfirmation && action.ConfirmationMessage) {
      setPendingAction(action)
      return
    }
    runAction(action)
  }

  const confirmVariant =
    pendingAction?.Name === 'pos_clear_cart' ? ('danger' as const) : ('default' as const)

  const isBusy = Boolean(disabled)

  return (
    <>
      <div className="relative z-20 shrink-0 rounded-xl border border-strokeColor bg-white shadow-sm pointer-events-auto">
        <div className="relative z-20 flex flex-wrap items-stretch gap-1 px-2 py-2 pointer-events-auto">
          {tabActions.map((action) => {
            const chargeDisabled = action.Name === 'pos_charge' && !pos.cart.length
            const actionDisabled =
              isBusy ||
              chargeDisabled ||
              (action.Name === 'pos_save_draft' && pos.savingDraft) ||
              (action.Name === 'pos_charge' && pos.loadingCheckout)
            const isPending =
              (action.Name === 'pos_save_draft' && pos.savingDraft) ||
              (action.Name === 'pos_charge' && pos.loadingCheckout)

            return (
              <button
                key={action.ActionId}
                type="button"
                title={action.Tooltip ?? action.Caption}
                disabled={actionDisabled}
                onClick={() => handleActionClick(action)}
                className={cn(
                  'inline-flex min-w-[88px] cursor-pointer flex-col items-center justify-center gap-1 rounded-lg px-3 py-2 text-xs font-medium transition',
                  'text-mainTextColor hover:bg-s1/10 disabled:cursor-not-allowed disabled:opacity-50',
                )}
              >
                {isPending ? (
                  <Loader2 size={14} className="animate-spin" />
                ) : (
                  <ActionIcon action={action} />
                )}
                <span className="text-center leading-tight">{action.Caption}</span>
              </button>
            )
          })}
        </div>
      </div>

      <ConfirmDialog
        open={pendingAction != null}
        title={pendingAction?.Caption}
        message={pendingAction?.ConfirmationMessage ?? 'Proceed with this action?'}
        confirmLabel={pendingAction?.Caption ?? 'Confirm'}
        variant={confirmVariant}
        onConfirm={() => {
          if (pendingAction) runAction(pendingAction)
          setPendingAction(null)
        }}
        onCancel={() => setPendingAction(null)}
      />
    </>
  )
}
