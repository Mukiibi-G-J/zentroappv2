import type { PageControlField } from '@/types/page'
import type { DataRecord } from '@/types/pagedata'

const SERVICE_OR_NON_INVENTORY = new Set(['Service', 'Non-Inventory'])

export function isFieldEditable(
  field: PageControlField,
  data: DataRecord,
  pageName?: string,
): boolean {
  if (
    pageName === 'ItemCard' &&
    field.Name === 'unit_cost' &&
    SERVICE_OR_NON_INVENTORY.has(String(data.type ?? ''))
  ) {
    return true
  }

  if (!field.Editable) return false

  if (pageName === 'UsersCard' && field.Name === 'email' && data.SystemId && !String(data.email ?? '').includes('@zentro.pending')) {
    return false
  }

  return true
}
