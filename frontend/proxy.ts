import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

const PUBLIC_PATHS = new Set([
  '/',
  '/login',
  '/landing',
  '/workspace',
  '/signup',
  '/verify-otp',
  '/on-boarding',
  '/forgot-password',
  '/reset-password',
  '/change-password',
])

function isPublicAsset(pathname: string): boolean {
  return (
    pathname.startsWith('/_next') ||
    pathname === '/favicon.ico' ||
    pathname === '/robots.txt' ||
    pathname.startsWith('/assets') ||
    /\.(ico|png|jpg|jpeg|svg|gif|webp|woff|woff2|ttf|eot)$/i.test(pathname)
  )
}

const KNOWN_APP_APICES = ['zentroapp.app', 'zentroapp.uncodedsolutions.com'] as const

function stripWww(hostname: string): string {
  return hostname.replace(/^www\./, '')
}

function resolveAppHost(hostname: string): string {
  const h = stripWww(hostname)
  for (const apex of KNOWN_APP_APICES) {
    if (h === apex || h.endsWith(`.${apex}`)) return apex
  }
  const fromEnv = process.env.NEXT_PUBLIC_APP_HOST?.trim()
  if (
    fromEnv &&
    fromEnv !== 'zentroapp-backend.com' &&
    !fromEnv.includes('zentroapp-api') &&
    !fromEnv.includes('backend.com')
  ) {
    return stripWww(fromEnv)
  }
  return 'zentroapp.app'
}

function isTenantSubdomain(hostname: string): boolean {
  const parts = hostname.split('.')
  if (parts.length >= 2 && parts[1] === 'localhost') {
    return parts[0] !== 'localhost' && parts[0] !== 'www'
  }
  const h = stripWww(hostname)
  for (const apex of KNOWN_APP_APICES) {
    if (h.endsWith(`.${apex}`) && h !== `www.${apex}`) return true
  }
  const appHost = resolveAppHost(hostname)
  if (h.endsWith(`.${appHost}`) && h !== `www.${appHost}`) return true
  return (
    parts.length > 2 &&
    parts[0] !== 'www' &&
    parts[1] === 'zentroapp' &&
    parts[2] === 'app'
  )
}

function isMainAppHost(hostname: string): boolean {
  return !isTenantSubdomain(hostname)
}

function buildMainDomainUrl(request: NextRequest, path: string): string {
  const isDev = process.env.NODE_ENV === 'development'
  const hostname = request.headers.get('host')?.split(':')[0] ?? ''
  const domain = isDev ? 'localhost' : resolveAppHost(hostname)
  const port = isDev ? ':3000' : ''
  const { protocol } = request.nextUrl
  return `${protocol}//${domain}${port}${path}`
}

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl
  const hostname = request.headers.get('host')?.split(':')[0] ?? ''

  if (isTenantSubdomain(hostname) && (pathname === '/' || pathname === '/landing')) {
    return NextResponse.redirect(buildMainDomainUrl(request, '/'))
  }

  if (isTenantSubdomain(hostname) && (pathname === '/signup' || pathname === '/on-boarding')) {
    return NextResponse.redirect(buildMainDomainUrl(request, '/signup'))
  }

  if (isMainAppHost(hostname) && pathname === '/verify-otp') {
    return NextResponse.redirect(buildMainDomainUrl(request, '/workspace'))
  }

  if (
    isMainAppHost(hostname) &&
    (pathname === '/login' ||
      pathname === '/forgot-password' ||
      pathname === '/reset-password')
  ) {
    const workspaceUrl = request.nextUrl.clone()
    workspaceUrl.pathname = '/workspace'
    return NextResponse.redirect(workspaceUrl)
  }

  if (isPublicAsset(pathname) || PUBLIC_PATHS.has(pathname)) {
    return NextResponse.next()
  }

  const isProtected =
    pathname === '/dashboard' ||
    pathname.startsWith('/dashboard/') ||
    pathname.startsWith('/record/') ||
    pathname.startsWith('/document/')

  if (!isProtected) {
    return NextResponse.next()
  }

  const hasSession =
    request.cookies.get('auth_session')?.value === '1' ||
    !!request.cookies.get('access_token')?.value
  if (hasSession) {
    return NextResponse.next()
  }

  const loginUrl = request.nextUrl.clone()
  loginUrl.pathname = '/login'
  loginUrl.search = ''
  loginUrl.searchParams.set('redirect', request.nextUrl.pathname + request.nextUrl.search)
  return NextResponse.redirect(loginUrl)
}

export const config = {
  matcher: [
    '/',
    '/landing',
    '/login',
    '/forgot-password',
    '/reset-password',
    '/workspace',
    '/signup',
    '/on-boarding',
    '/verify-otp',
    '/dashboard',
    '/dashboard/:path*',
    '/record/:path*',
    '/document/:path*',
  ],
}
