'use client'

import type { ComponentType } from 'react'
import type { PageControl } from '@/types/page'
import type { DataRecord } from '@/types/pagedata'
import { resolveFactBoxParentKey } from '@/lib/factBoxUtils'
import ItemImagesFactBox from './factBoxes/ItemImagesFactBox'
import DocumentAttachmentsFactBox from './factBoxes/DocumentAttachmentsFactBox'
import FactBoxShell from './FactBoxShell'
import type { FactBoxProps } from './factBoxes/types'

interface Props {
  control: PageControl
  data: DataRecord
  recordReady: boolean
  readOnly?: boolean
  saveFirstHint?: string
  storageKey?: string
}

const FACT_BOX_REGISTRY: Record<string, ComponentType<FactBoxProps>> = {
  ItemImages: ItemImagesFactBox,
  DocumentAttachment: DocumentAttachmentsFactBox,
}

const FACT_BOX_BY_NAME: Record<string, ComponentType<FactBoxProps>> = {
  ItemAttachments: ItemImagesFactBox,
  PurchaseInvoiceAttachments: DocumentAttachmentsFactBox,
}

function resolveFactBoxComponent(control: PageControl): ComponentType<FactBoxProps> | null {
  return (
    FACT_BOX_REGISTRY[control.SourceTable] ??
    FACT_BOX_BY_NAME[control.Name] ??
    null
  )
}

export default function FactBoxPanel({
  control,
  data,
  recordReady,
  readOnly,
  saveFirstHint,
  storageKey,
}: Props) {
  const Component = resolveFactBoxComponent(control)
  const parentKey = resolveFactBoxParentKey(control, data)

  if (Component) {
    return (
      <Component
        control={control}
        parentKey={parentKey}
        recordReady={recordReady}
        readOnly={readOnly}
        saveFirstHint={saveFirstHint}
        storageKey={storageKey}
      />
    )
  }

  return (
    <FactBoxShell
      control={control}
      recordReady={recordReady}
      saveFirstHint={saveFirstHint}
      storageKey={storageKey}
    >
      <p className="p-4 text-xs text-bodyText">This fact box is not configured yet.</p>
    </FactBoxShell>
  )
}
