import type { PageControl } from '@/types/page'
import type { DataRecord } from '@/types/pagedata'

export interface FactBoxProps {
  control: PageControl
  parentKey: string | null
  recordReady: boolean
  readOnly?: boolean
  saveFirstHint?: string
  storageKey?: string
}

export interface FactBoxAsideProps {
  controls: PageControl[]
  data: DataRecord
  recordReady: boolean
  readOnly?: boolean
  saveFirstHint?: string
  /** Prefix for localStorage keys (pane + individual fact box collapse state). */
  storageKey?: string
}
