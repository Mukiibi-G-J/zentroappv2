const DEV_FRONTEND_PORT = process.env.NEXT_PUBLIC_DEV_FRONT_PORT ?? '3000'
/** V2 live frontend apex (tenant URLs are `{slug}.{APP_HOST}`). */
const PROD_APP_HOST = process.env.NEXT_PUBLIC_APP_HOST ?? 'zentroapp.uncodedsolutions.com'
/** V2 live API apex (tenant API is `{slug}.{API_HOST}`). */
const PROD_API_HOST = process.env.NEXT_PUBLIC_API_HOST ?? 'zentroapp-api.uncodedsolutions.com'

/** Normalize user input to a tenant subdomain slug (schema name). */
export function slugifyCompanyInput(raw: string): string {
  return raw
    .trim()
    .toLowerCase()
    .replace(/\s+/g, '')
    .replace(/[^a-z0-9_]/g, '')
}

export function isMainAppHost(hostname: string): boolean {
  if (!hostname || hostname === 'localhost') return true
  const parts = hostname.split('.')
  if (parts.length === 1) return true
  if (parts.length === 2 && parts[0] === 'localhost' && parts[1] === 'localhost') return true
  if (hostname === PROD_APP_HOST || hostname === `www.${PROD_APP_HOST}`) return true
  return false
}

export function isTenantSubdomain(hostname: string): boolean {
  if (!hostname || isMainAppHost(hostname)) return false
  const parts = hostname.split('.')
  if (parts.length >= 2 && parts[1] === 'localhost') {
    return parts[0] !== 'www' && parts[0] !== 'localhost'
  }
  if (hostname.endsWith(`.${PROD_APP_HOST}`) && hostname !== `www.${PROD_APP_HOST}`) {
    return true
  }
  // Legacy V1 host pattern (kept for local/docs samples).
  return (
    parts.length > 2 &&
    parts[0] !== 'www' &&
    parts[1] === 'zentroapp' &&
    parts[2] === 'app'
  )
}

export function tenantSlugFromHostname(hostname: string): string | null {
  if (!isTenantSubdomain(hostname)) return null
  return hostname.split('.')[0] ?? null
}

export function getFrontendPort(): string {
  if (typeof window !== 'undefined' && window.location.port) {
    return window.location.port
  }
  return process.env.NODE_ENV === 'development' ? DEV_FRONTEND_PORT : ''
}

export function buildTenantAppUrl(
  slug: string,
  path = '/login',
  opts?: { protocol?: string; port?: string },
): string {
  const normalized = slugifyCompanyInput(slug)
  if (!normalized) return ''

  const isDev = process.env.NODE_ENV === 'development'
  const protocol =
    opts?.protocol ??
    (typeof window !== 'undefined' ? window.location.protocol : 'http:')
  const port = opts?.port ?? (isDev ? getFrontendPort() : '')
  const portSuffix = port ? `:${port}` : ''
  const host = isDev ? `${normalized}.localhost` : `${normalized}.${PROD_APP_HOST}`

  return `${protocol}//${host}${portSuffix}${path.startsWith('/') ? path : `/${path}`}`
}

export function buildMainAppUrl(path = '/'): string {
  const isDev = process.env.NODE_ENV === 'development'
  const port = isDev ? getFrontendPort() : ''
  const portSuffix = port ? `:${port}` : ''
  const host = isDev ? 'localhost' : PROD_APP_HOST
  const protocol = typeof window !== 'undefined' ? window.location.protocol : 'http:'
  return `${protocol}//${host}${portSuffix}${path.startsWith('/') ? path : `/${path}`}`
}

export function buildTenantApiBaseUrl(slug: string): string {
  const normalized = slugifyCompanyInput(slug)
  if (!normalized) return ''

  const port = process.env.NEXT_PUBLIC_API_PORT ?? '8002'
  const isDev = process.env.NODE_ENV === 'development'
  if (isDev) {
    return `http://${normalized}.localhost:${port}/api`
  }
  return `https://${normalized}.${PROD_API_HOST}/api`
}

export function buildTenantPreviewHost(slug: string): string {
  const normalized = slugifyCompanyInput(slug)
  if (!normalized) return 'your-company.localhost'

  const isDev = process.env.NODE_ENV === 'development'
  const port = isDev ? getFrontendPort() : ''
  const portSuffix = port ? `:${port}` : ''
  return isDev
    ? `${normalized}.localhost${portSuffix}`
    : `${normalized}.${PROD_APP_HOST}`
}
