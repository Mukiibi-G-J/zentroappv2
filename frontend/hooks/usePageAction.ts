'use client'

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { pageService } from '@/services/page.service'
import { extractErrorMessage } from '@/services/pagedata.service'
import type { DataRecord } from '@/types/pagedata'
import type { PageActionResponse } from '@/types/page'
import { isPreviewActionResponse } from '@/lib/pageActionResponse'

export function useInvokeAction(pageId: number, controlId?: number) {
  const qc = useQueryClient()

  return useMutation({
    mutationFn: ({ actionId, systemId }: { actionId: string; systemId: string }) =>
      pageService.invokeAction(pageId, actionId, systemId),
    onSuccess: (response, { systemId }) => {
      if (isPreviewActionResponse(response)) return

      if (!('ok' in response) || !response.ok) return

      if (response.record) {
        if (controlId !== undefined) {
          qc.setQueryData<DataRecord>(
            ['pagedata', 'record', pageId, controlId, systemId],
            response.record,
          )
        }
        qc.setQueryData<DataRecord>(
          ['pagedata', 'record', pageId, 'card', systemId],
          response.record,
        )
      }
      qc.invalidateQueries({ queryKey: ['pagedata', 'record', pageId] })
      qc.invalidateQueries({ queryKey: ['pagedata', 'infinite'] })
      const label =
        response.ActionId === 'post_item_journal' || response.ActionId === 'post_payment_journal'
          ? 'Journal posted'
          : response.ActionId === 'post_purchase_invoice'
            ? 'Purchase invoice posted'
            : response.ActionId === 'post_sales_invoice'
              ? 'Sales invoice posted'
              : `${response.ActionId} completed`
      toast.success(`${label} successfully`)
    },
    onError: (err: unknown) => {
      toast.error(extractErrorMessage(err))
    },
  })
}
