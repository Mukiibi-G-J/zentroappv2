import fs from 'fs'
import path from 'path'

const file = path.join('c:/PROJECTS/zentroapp-webV2/frontend/components/dynamic/DynamicDocumentPage.tsx')
const lines = fs.readFileSync(file, 'utf8').split(/\r?\n/)

const head = lines.slice(0, 69)
const tail = lines.slice(1629) // DocumentSkeleton onwards

const importLine = "import DynamicListPart from './DynamicListPart'"

// Clean up imports in head - remove list-part-only imports
const cleanedHead = head.filter((line) => {
  const drop = [
    "import { Check, ChevronRight",
    "import { useWorksheetGridKeyboard }",
    "import { isLineFieldEditable",
    "import DynamicTrackingModal",
    "import SearchableRelationSelect",
    "import WorksheetRowMenu",
    "import DocumentLinesRibbon",
    "import DynamicWorksheetModal",
    "import { ConfirmDialog }",
    "import { worksheetFrozenFieldProps",
    "import { buildLineNavigateHref }",
    "import { applyEntriesPartyKind",
    "import type { ApplyPaymentContext }",
    "import { resolveRibbonIcon }",
    "import { getItemByNo",
    "import type { PurchaseTrackingContext }",
    "import { useQueryClient }",
    "import { usePathname }",
    "import { pageService }",
    "import { buildRelationRecordValues",
    "import { listFieldValuesEqual",
    "import { formatRelationDisplay",
    "import { mapTableRelationValue",
  ]
  if (drop.some((p) => line.includes(p))) return false
  if (line.includes('APPLY_CUSTOMER_ENTRIES_PAGE_NAME')) return false
  if (line.includes('ITEM_TRACKING_LINES_WORKSHEET_PAGE_NAME')) return false
  if (line.includes('visibleItemTrackingLinePageActions')) return false
  if (line.includes('visibleLinePageActions')) return false
  if (line.includes('visibleNavigateLinePageActions')) return false
  if (line.includes('buildApplyEntriesContext')) return false
  if (line.includes('isItemTrackingLinesAction')) return false
  return true
})

// Fix lucide import
const lucideIdx = cleanedHead.findIndex((l) => l.includes("from 'lucide-react'"))
if (lucideIdx >= 0) {
  cleanedHead[lucideIdx] = "import { ArrowLeft, Loader2 } from 'lucide-react'"
}

// Fix PageAction import if unused
const pageTypeIdx = cleanedHead.findIndex((l) => l.includes("from '@/types/page'"))
if (pageTypeIdx >= 0) {
  cleanedHead[pageTypeIdx] = "import type { Page, PageControl, PageControlField } from '@/types/page'"
}

const body = [...cleanedHead, importLine, '', ...tail]
  .join('\n')
  .replace(/DocumentLinesSection/g, 'DynamicListPart')

fs.writeFileSync(file, body)
console.log('Trimmed', file, 'to', body.split('\n').length, 'lines')
