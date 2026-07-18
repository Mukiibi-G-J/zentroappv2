export function extractApiErrorMessage(err: unknown): string {
  if (!err || typeof err !== 'object') return 'Something went wrong'

  const resp = (err as { response?: { data?: unknown } }).response?.data
  if (!resp) {
    if (err instanceof Error) return err.message
    return 'Something went wrong'
  }

  if (typeof resp === 'string') return resp

  if (typeof resp === 'object') {
    const r = resp as Record<string, unknown>
    for (const key of ['error', 'message', 'detail']) {
      if (typeof r[key] === 'string') return r[key] as string
    }
    if (Array.isArray(r.errors) && r.errors.length > 0) {
      const first = r.errors[0]
      if (typeof first === 'string') return first
      if (typeof first === 'object' && first !== null) {
        const msg = (first as Record<string, unknown>).message ?? (first as Record<string, unknown>).detail
        if (typeof msg === 'string') return msg
      }
    }
    // Collect all field-level messages
    const messages: string[] = []
    for (const [k, v] of Object.entries(r)) {
      if (Array.isArray(v)) messages.push(`${k}: ${v.join(', ')}`)
      else if (typeof v === 'string') messages.push(`${k}: ${v}`)
    }
    if (messages.length) return messages.join(' | ')
  }

  return 'Something went wrong'
}
