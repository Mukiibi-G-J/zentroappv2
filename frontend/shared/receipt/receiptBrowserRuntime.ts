import { buildReceiptDocument } from './buildDocument'
import { compileDocumentToBrowserHtml } from './compileToBrowserHtml'
import type { ReceiptBranding, ReceiptBuildPayload, ResolvedReceiptTemplate } from './types'

export function buildAndCompileBrowserHtml(
  payload: ReceiptBuildPayload,
  template: ResolvedReceiptTemplate,
  branding: ReceiptBranding,
): string {
  const document = buildReceiptDocument(payload, template, branding)
  return compileDocumentToBrowserHtml(document)
}
