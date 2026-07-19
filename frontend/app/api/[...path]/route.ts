import { type NextRequest, NextResponse } from 'next/server'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

/** Headers that must not be forwarded to Django (esp. Cookie → 431). */
const SKIP_REQUEST_HEADERS = new Set([
  'connection',
  'content-length',
  'cookie',
  'host',
  'keep-alive',
  'proxy-authenticate',
  'proxy-authorization',
  'te',
  'trailers',
  'transfer-encoding',
  'upgrade',
])

const SKIP_RESPONSE_HEADERS = new Set([
  'connection',
  'content-encoding',
  'keep-alive',
  'transfer-encoding',
])

function backendBase(): string {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL?.trim()
  if (apiUrl) return apiUrl.replace(/\/$/, '')
  const host = process.env.NEXT_PUBLIC_API_REWRITE_HOST ?? '127.0.0.1'
  const port = process.env.NEXT_PUBLIC_API_PORT ?? '8002'
  return `http://${host}:${port}`
}

async function proxyToDjango(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
): Promise<NextResponse> {
  const { path } = await context.params
  const pathStr = path.join('/')
  const trailingSlash = request.nextUrl.pathname.endsWith('/') ? '/' : ''
  const target = `${backendBase()}/api/${pathStr}${trailingSlash}${request.nextUrl.search}`

  const headers = new Headers()
  request.headers.forEach((value, key) => {
    if (SKIP_REQUEST_HEADERS.has(key.toLowerCase())) return
    headers.set(key, value)
  })

  // Tenant resolution uses Origin/Referer when Host is a LAN IP (see TenantJWTMiddleware).
  const origin = request.headers.get('origin')
  if (origin && !headers.has('origin')) headers.set('origin', origin)
  const referer = request.headers.get('referer')
  if (referer && !headers.has('referer')) headers.set('referer', referer)

  const init: RequestInit = {
    method: request.method,
    headers,
    redirect: 'manual',
  }

  if (request.method !== 'GET' && request.method !== 'HEAD') {
    init.body = await request.arrayBuffer()
  }

  let upstream: Response
  try {
    upstream = await fetch(target, init)
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Upstream unreachable'
    return NextResponse.json(
      { detail: `API proxy failed: ${message}`, target },
      { status: 502 },
    )
  }

  const responseHeaders = new Headers()
  upstream.headers.forEach((value, key) => {
    if (SKIP_RESPONSE_HEADERS.has(key.toLowerCase())) return
    responseHeaders.set(key, value)
  })

  return new NextResponse(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: responseHeaders,
  })
}

export const GET = proxyToDjango
export const POST = proxyToDjango
export const PUT = proxyToDjango
export const PATCH = proxyToDjango
export const DELETE = proxyToDjango
export const OPTIONS = proxyToDjango
export const HEAD = proxyToDjango
