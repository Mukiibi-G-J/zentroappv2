import type { PageActionResponse } from '@/types/page'

export function isPreviewActionResponse(response: unknown): response is PageActionResponse {
  return (
    typeof response === 'object'
    && response !== null
    && 'Command' in response
    && (response as PageActionResponse).Command === 'PREVIEW'
  )
}

export function isDownloadActionResponse(response: unknown): response is PageActionResponse {
  return (
    typeof response === 'object'
    && response !== null
    && 'Command' in response
    && (response as PageActionResponse).Command === 'DOWNLOAD'
  )
}
