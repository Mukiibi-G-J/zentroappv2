import fs from 'fs'
import path from 'path'

const root = path.resolve('c:/PROJECTS/zentroapp-webV2/frontend')
const dir = path.join(root, 'components', 'dynamic')
const srcPath = path.join(dir, 'DynamicDocumentPage.tsx')
const outPath = path.join(dir, 'DynamicListPart.tsx')

const lines = fs.readFileSync(srcPath, 'utf8').split(/\r?\n/)

// Helpers (formatLineValue + column constants) + DocumentLinesSection + LineRow only
const helperBlock = lines.slice(69, 95) // lines 70-95
const listPartBlock = lines.slice(496, 1629) // lines 497-1629

let body = [...helperBlock, '', ...listPartBlock].join('\n')

body = body.replace(
  'export function DocumentLinesSection({',
  `export interface DynamicListPartProps {
  caption?: string
  partPage: PartSummary
  repeaterControl: PageControl
  lines: UseDocumentLinesReturn
  recordReady: boolean
  linesReadOnly: boolean
  saveFirstHint: string
  applyEntriesEnabled?: boolean
  applyVendorEntriesPage?: Page
  applyCustomerEntriesPage?: Page
  paymentHeader?: DataRecord
  documentHeader?: DataRecord
  onHeaderRefresh?: () => void
}

export function DynamicListPart({`,
)

body = body.replace('caption: _caption,\n', '')
body = body.replace(
  /}: \{\n  caption: string\n  partPage: PartSummary[\s\S]*?onHeaderRefresh\?: \(\) => void\n\}\) \{/,
  '}: DynamicListPartProps) {',
)

const header = `'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useRouter, useSearchParams, usePathname } from 'next/navigation'
import { Check, ChevronRight } from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import { usePage, usePages } from '@/hooks/usePage'
import type { UseDocumentLinesReturn } from '@/hooks/useDocumentLines'
import { mapTableRelationValue, type RelationOption } from '@/hooks/useRelationOptions'
import { formatRelationDisplay, resolveRelationSelectValue } from '@/lib/relationDisplay'
import { useWorksheetGridKeyboard } from '@/hooks/useWorksheetGridKeyboard'
import {
  isLineFieldEditable,
  moveGridActiveCell,
  readActiveCellCommitValue,
  type GridActiveCell,
} from '@/lib/worksheetGridKeyboard'
import { listFieldValuesEqual, normalizeListFieldSaveValue } from '@/lib/listFieldValue'
import { pageService } from '@/services/page.service'
import {
  buildRelationRecordValues,
  collectContextValuesFromRecords,
  contextRelationCacheKey,
  getDependentRelationFields,
  hasContextRelation,
} from '@/lib/contextRelations'
import { getItemByNo, itemRequiresTracking } from '@/services/items.service'
import type { PurchaseTrackingContext } from '@/types/tracking'
import DynamicTrackingModal from './DynamicTrackingModal'
import DynamicField from './DynamicField'
import SearchableRelationSelect from './SearchableRelationSelect'
import WorksheetRowMenu from './WorksheetRowMenu'
import DocumentLinesRibbon from './DocumentLinesRibbon'
import DynamicWorksheetModal from './DynamicWorksheetModal'
import ErrorBanner from '@/components/ui/ErrorBanner'
import { ConfirmDialog } from '@/components/ui/ConfirmDialog'
import { worksheetFrozenFieldProps, colWidthPx } from '@/lib/worksheetColumns'
import { buildLineNavigateHref } from '@/lib/cardAction'
import {
  applyEntriesPartyKind,
  ITEM_TRACKING_LINES_WORKSHEET_PAGE_NAME,
  buildApplyEntriesContext,
  isItemTrackingLinesAction,
  visibleItemTrackingLinePageActions,
  visibleLinePageActions,
  visibleNavigateLinePageActions,
} from '@/lib/documentLineActions'
import type { ApplyPaymentContext } from '@/lib/applyEntriesContext'
import { resolveRibbonIcon } from '@/lib/ribbonIcon'
import type { Page, PageAction, PageControl, PageControlField, PartSummary } from '@/types/page'
import type { DataRecord } from '@/types/pagedata'

`

const footer = `

/** @deprecated Use DynamicListPart — kept for existing imports */
export const DocumentLinesSection = DynamicListPart
`

fs.writeFileSync(outPath, header + body + footer)
console.log('Wrote', outPath, 'lines:', (header + body + footer).split('\n').length)
