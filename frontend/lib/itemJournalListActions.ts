import type { Page, PageAction } from '@/types/page'
import type { DataRecord } from '@/types/pagedata'
import type {
  JournalPreviewContent,
  PreviewDetailRow,
  PreviewRelatedEntry,
} from '@/components/dynamic/JournalPreviewDialog'

export const ITEM_JOURNAL_LIST_PAGES = new Set([
  'OpeningBalanceJournalList',
  'InventoryAdjustmentJournalList',
])

export const SELECT_MORE_ACTION = '#select-more'
export const PREVIEW_ITEM_JOURNAL = 'preview_item_journal'
export const POST_ITEM_JOURNAL = 'post_item_journal'

export function isItemJournalListPage(page: Pick<Page, 'Name'> | null | undefined): boolean {
  return Boolean(page?.Name && ITEM_JOURNAL_LIST_PAGES.has(page.Name))
}

export function isSelectMoreAction(action: PageAction): boolean {
  return (action.ActionRelativeUrl || '').trim() === SELECT_MORE_ACTION
}

export function isItemJournalServerAction(action: PageAction): boolean {
  return action.Name === PREVIEW_ITEM_JOURNAL || action.Name === POST_ITEM_JOURNAL
}

export function recordIsOpen(record: DataRecord | null | undefined): boolean {
  if (!record) return false
  return String(record.status ?? '').trim().toLowerCase() === 'open'
}

/** Merge multiple journal preview payloads into one dialog model. */
export function mergeJournalPreviews(previews: JournalPreviewContent[]): JournalPreviewContent {
  if (previews.length === 0) {
    return { Entries: [] }
  }
  if (previews.length === 1) {
    return previews[0]
  }

  const entries: JournalPreviewContent['Entries'] = []
  let line = 1
  const relatedMap = new Map<string, PreviewRelatedEntry>()
  const entrySets: Record<string, PreviewDetailRow[]> = {}

  for (const preview of previews) {
    for (const entry of preview.Entries ?? []) {
      entries.push({ ...entry, Line: line++ })
    }
    for (const related of preview.RelatedEntries ?? []) {
      const existing = relatedMap.get(related.TableKey)
      if (existing) {
        existing.NoOfEntries += related.NoOfEntries
      } else {
        relatedMap.set(related.TableKey, { ...related })
      }
    }
    if (preview.EntrySets) {
      for (const [key, rows] of Object.entries(preview.EntrySets)) {
        entrySets[key] = [...(entrySets[key] ?? []), ...rows]
      }
    }
  }

  return {
    Entries: entries,
    RelatedEntries: [...relatedMap.values()],
    EntrySets: Object.keys(entrySets).length > 0 ? entrySets : undefined,
    Message: `Preview of ${previews.length} journals`,
    BatchName: undefined,
  }
}
