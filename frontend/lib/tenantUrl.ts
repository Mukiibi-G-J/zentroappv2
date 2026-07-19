const DEV_FRONTEND_PORT = process.env.NEXT_PUBLIC_DEV_FRONT_PORT ?? '3000'

/** Known Next.js marketing / tenant apices (never the API host). */
const KNOWN_APP_APICES = ['zentroapp.app', 'zentroapp.uncodedsolutions.com'] as const

/** API hosts — must never be used as APP_HOST for login redirects. */
const KNOWN_API_APICES = [
  'zentroapp-backend.com',
  'zentroapp-api.uncodedsolutions.com',
] as const

function stripWww(hostname: string): string {
  return hostname.replace(/^www\./, '')
}

function isApiHost(hostname: string): boolean {
  const h = stripWww(hostname)
  return KNOWN_API_APICES.some((api) => h === api || h.endsWith(`.${api}`))
}

/**
 * Frontend apex for `{slug}.{host}/login`.
 * Prefer the page the user is on; ignore mis-set NEXT_PUBLIC_APP_HOST when it points at the API.
 */
export function getProdAppHost(): string {
  if (typeof window !== 'undefined') {
    const h = stripWww(window.location.hostname)
    for (const apex of KNOWN_APP_APICES) {
      if (h === apex || h.endsWith(`.${apex}`)) return apex
    }
  }

  const fromEnv = process.env.NEXT_PUBLIC_APP_HOST?.trim()
  if (fromEnv && !isApiHost(fromEnv)) {
    return stripWww(fromEnv)
  }

  return 'zentroapp.app'
}

export function getProdApiHost(): string {
  const fromEnv = process.env.NEXT_PUBLIC_API_HOST?.trim()
  if (fromEnv) return stripWww(fromEnv)
  return 'zentroapp-backend.com'
}

const ENV_APP_HOST = process.env.NEXT_PUBLIC_APP_HOST ?? 'zentroapp.app'

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

  const h = stripWww(hostname)
  const appHost =
    typeof window !== 'undefined' ? getProdAppHost() : stripWww(ENV_APP_HOST)
  if (h === appHost) return true
  return KNOWN_APP_APICES.some((apex) => h === apex)
}

export function isTenantSubdomain(hostname: string): boolean {
  if (!hostname || isMainAppHost(hostname)) return false
  const parts = hostname.split('.')
  if (parts.length >= 2 && parts[1] === 'localhost') {
    return parts[0] !== 'www' && parts[0] !== 'localhost'
  }

  const h = stripWww(hostname)
  for (const apex of KNOWN_APP_APICES) {
    if (h.endsWith(`.${apex}`) && h !== `www.${apex}`) return true
  }

  const appHost =
    typeof window !== 'undefined' ? getProdAppHost() : stripWww(ENV_APP_HOST)
  if (h.endsWith(`.${appHost}`) && h !== `www.${appHost}`) return true

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
  const appHost = isDev ? 'localhost' : getProdAppHost()
  const host = isDev ? `${normalized}.localhost` : `${normalized}.${appHost}`

  return `${protocol}//${host}${portSuffix}${path.startsWith('/') ? path : `/${path}`}`
}

export function buildMainAppUrl(path = '/'): string {
  const isDev = process.env.NODE_ENV === 'development'
  const port = isDev ? getFrontendPort() : ''
  const portSuffix = port ? `:${port}` : ''
  const host = isDev ? 'localhost' : getProdAppHost()
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
  return `https://${normalized}.${getProdApiHost()}/api`
}

export function buildTenantPreviewHost(slug: string): string {
  const normalized = slugifyCompanyInput(slug)
  if (!normalized) return 'your-company.localhost'

  const isDev = process.env.NODE_ENV === 'development'
  const port = isDev ? getFrontendPort() : ''
  const portSuffix = port ? `:${port}` : ''
  return isDev
    ? `${normalized}.localhost${portSuffix}`
    : `${normalized}.${getProdAppHost()}`
}
