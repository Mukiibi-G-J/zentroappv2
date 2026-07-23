'use client'

import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  ArrowLeft,
  ArrowRight,
  Building2,
  Home,
  LayoutDashboard,
  LogIn,
  Search,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import {
  buildMainAppUrl,
  buildTenantAppUrl,
  isTenantSubdomain,
  slugifyCompanyInput,
  tenantSlugFromHostname,
} from '@/lib/tenantUrl'

/** App routes that are never a company workspace slug. */
const RESERVED_SEGMENTS = new Set([
  'api',
  'change-password',
  'company',
  'dashboard',
  'document',
  'favicon',
  'forgot-password',
  'landing',
  'login',
  'menu',
  'on-boarding',
  'record',
  'reset-password',
  'signup',
  'subscription',
  'verify-otp',
  'workspace',
  '_next',
])

type Action = {
  href: string
  label: string
  description: string
  icon: typeof Home
  primary?: boolean
  external?: boolean
}

function looksLikeTenantSlug(segment: string): boolean {
  const slug = slugifyCompanyInput(segment)
  if (!slug || slug !== segment.toLowerCase()) return false
  if (RESERVED_SEGMENTS.has(slug)) return false
  if (slug.length < 2) return false
  return /^[a-z][a-z0-9_]*$/.test(slug)
}

function parseMistakenTenantPath(pathname: string): {
  slug: string
  restPath: string
} | null {
  const parts = pathname.split('/').filter(Boolean)
  if (parts.length < 1) return null
  const [maybeSlug, ...rest] = parts
  if (!looksLikeTenantSlug(maybeSlug)) return null
  const restPath = rest.length ? `/${rest.join('/')}` : '/login'
  return { slug: maybeSlug.toLowerCase(), restPath }
}

export function NotFoundPage() {
  const pathname = usePathname() || '/'
  const mistaken = useMemo(() => parseMistakenTenantPath(pathname), [pathname])

  const [hostContext, setHostContext] = useState<{
    onTenant: boolean
    workspaceSlug: string | null
    homeUrl: string
    tenantUrl: string
  }>({
    onTenant: false,
    workspaceSlug: null,
    homeUrl: '/',
    tenantUrl: '',
  })

  useEffect(() => {
    const hostname = window.location.hostname
    const onTenant = isTenantSubdomain(hostname)
    const pathHint = onTenant ? null : parseMistakenTenantPath(pathname)
    setHostContext({
      onTenant,
      workspaceSlug: tenantSlugFromHostname(hostname),
      homeUrl: buildMainAppUrl('/'),
      tenantUrl: pathHint
        ? buildTenantAppUrl(pathHint.slug, pathHint.restPath)
        : '',
    })
  }, [pathname])

  const showMistakenHint = Boolean(mistaken) && !hostContext.onTenant
  const mistakenTenantUrl = hostContext.tenantUrl

  const actions = useMemo((): Action[] => {
    const list: Action[] = []

    if (showMistakenHint && mistaken && mistakenTenantUrl) {
      list.push({
        href: mistakenTenantUrl,
        label: `Open ${mistaken.slug} workspace`,
        description: `Company workspaces use a subdomain, not a path. Continue to ${mistaken.slug}.localhost…`,
        icon: LogIn,
        primary: true,
        external: true,
      })
    }

    if (hostContext.onTenant) {
      list.push({
        href: '/dashboard',
        label: 'Go to dashboard',
        description: hostContext.workspaceSlug
          ? `Continue in ${hostContext.workspaceSlug}`
          : 'Open your ERP home',
        icon: LayoutDashboard,
        primary: true,
      })
      list.push({
        href: '/login',
        label: 'Sign in',
        description: 'Sign in to this workspace',
        icon: LogIn,
      })
    } else if (!showMistakenHint) {
      list.push({
        href: '/workspace',
        label: 'Find your workspace',
        description: 'Enter your company name to open the right login',
        icon: Search,
        primary: true,
      })
      list.push({
        href: '/login',
        label: 'Sign in',
        description: 'Sign in if you already know your workspace URL',
        icon: LogIn,
      })
    } else {
      list.push({
        href: '/workspace',
        label: 'Find another workspace',
        description: 'Look up a different company workspace',
        icon: Search,
      })
    }

    list.push({
      href: hostContext.homeUrl || '/',
      label: 'Zentro home',
      description: 'Back to the main ZentroApp site',
      icon: Home,
      external: true,
    })

    return list
  }, [showMistakenHint, mistaken, mistakenTenantUrl, hostContext])

  return (
    <div className="min-h-screen bg-gradient-to-br from-s1/5 via-white to-s2/5 flex items-center justify-center p-4">
      <div className="w-full max-w-lg rounded-2xl border border-strokeColor bg-white p-8 shadow-sm text-mainTextColor">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-s1">
            <Building2 className="h-8 w-8 text-white" />
          </div>
          <p className="mb-2 text-sm font-semibold uppercase tracking-wide text-s1">404</p>
          <h1 className="mb-2 text-2xl font-bold">Page not found</h1>
          <p className="text-sm text-bodyText">
            {showMistakenHint && mistaken ? (
              <>
                <code className="rounded bg-softBg px-1.5 py-0.5 font-mono text-xs text-s1">
                  /{mistaken.slug}/…
                </code>{' '}
                is not a valid app route. Company workspaces live on a subdomain.
              </>
            ) : (
              <>
                We couldn&apos;t find{' '}
                <code className="rounded bg-softBg px-1.5 py-0.5 font-mono text-xs text-s1">
                  {pathname}
                </code>
                .
              </>
            )}
          </p>
        </div>

        <div className="space-y-3">
          {actions.map((action) => {
            const Icon = action.icon
            const className = cn(
              'group flex w-full items-start gap-3 rounded-xl border px-4 py-3 text-left transition',
              action.primary
                ? 'border-s1 bg-s1 text-white hover:bg-s1/90'
                : 'border-strokeColor bg-white hover:border-s1/40 hover:bg-softBg2',
            )
            const body = (
              <>
                <span
                  className={cn(
                    'mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg',
                    action.primary ? 'bg-white/15' : 'bg-softBg2 text-s1',
                  )}
                >
                  <Icon className="h-4 w-4" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-2 text-sm font-semibold">
                    {action.label}
                    <ArrowRight
                      className={cn(
                        'h-3.5 w-3.5 opacity-0 transition group-hover:translate-x-0.5 group-hover:opacity-100',
                        action.primary ? 'text-white' : 'text-s1',
                      )}
                    />
                  </span>
                  <span
                    className={cn(
                      'mt-0.5 block text-xs',
                      action.primary ? 'text-white/80' : 'text-bodyText',
                    )}
                  >
                    {action.description}
                  </span>
                </span>
              </>
            )

            if (action.external) {
              return (
                <a key={action.label} href={action.href} className={className}>
                  {body}
                </a>
              )
            }
            return (
              <Link key={action.label} href={action.href} className={className}>
                {body}
              </Link>
            )
          })}
        </div>

        <button
          type="button"
          onClick={() => {
            if (window.history.length > 1) {
              window.history.back()
            } else {
              window.location.href = hostContext.homeUrl || '/'
            }
          }}
          className="mt-6 inline-flex w-full items-center justify-center gap-2 text-sm text-bodyText hover:text-s1"
        >
          <ArrowLeft className="h-4 w-4" />
          Go back
        </button>
      </div>
    </div>
  )
}
