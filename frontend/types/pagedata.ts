export type DataRecord = Record<string, unknown> & {
  SystemId: string
  [key: string]: unknown
}

export interface UpdateFieldResponse {
  ok: boolean
  Created: boolean
  record: DataRecord
}

export interface ActionResult {
  ok: boolean
  ActionId: string
  record: DataRecord
}
