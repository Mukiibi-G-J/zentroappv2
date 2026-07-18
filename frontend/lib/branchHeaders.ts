import axios, { type InternalAxiosRequestConfig } from 'axios'
import {
  getBranchScopeForApi,
  getEffectiveBranchIdForApi,
  type BranchScope,
} from '@/lib/branchSession'

const BRANCH_ID_HEADER = 'X-Branch-Id'
const BRANCH_SCOPE_HEADER = 'X-Branch-Scope'
const ALL_BRANCH_SCOPE = 'all'

/** Routes that must not send tenant branch headers (login, token refresh). */
const BRANCH_HEADER_SKIP_PATHS = [
  '/api/auth/token/',
  '/api/auth/token/refresh/',
  '/api/auth/register/',
  '/api/auth/password-reset/',
  '/api/auth/forgot-password/',
  '/api/auth/reset-password/',
]

function shouldSkipBranchHeaders(url: string | undefined): boolean {
  if (!url) return false
  return BRANCH_HEADER_SKIP_PATHS.some((path) => url.includes(path))
}

function ensureAxiosHeaders(config: InternalAxiosRequestConfig) {
  if (!config.headers || typeof config.headers.set !== 'function') {
    config.headers = axios.AxiosHeaders.from(config.headers ?? {})
  }
  return config.headers
}

function getHeader(config: InternalAxiosRequestConfig, name: string): string | undefined {
  const headers = config.headers
  if (!headers) return undefined
  if (typeof headers.get === 'function') {
    const value = headers.get(name)
    return value != null ? String(value) : undefined
  }
  const value = headers[name] ?? headers[name.toLowerCase()]
  return value != null ? String(value) : undefined
}

function setHeader(config: InternalAxiosRequestConfig, name: string, value: string): void {
  ensureAxiosHeaders(config).set(name, value)
}

function deleteHeader(config: InternalAxiosRequestConfig, name: string): void {
  const headers = ensureAxiosHeaders(config)
  headers.delete(name)
  headers.delete(name.toLowerCase())
}

/**
 * Attach dimension branch headers to outgoing API requests.
 * Mirrors zentro-frontend BaseService: active branch with assigned fallback;
 * never overwrites explicit per-request overrides.
 */
export function applyBranchHeadersToRequest(config: InternalAxiosRequestConfig): void {
  if (typeof window === 'undefined') return
  if (shouldSkipBranchHeaders(config.url)) {
    deleteHeader(config, BRANCH_ID_HEADER)
    deleteHeader(config, BRANCH_SCOPE_HEADER)
    return
  }

  const hasScopeOverride = getHeader(config, BRANCH_SCOPE_HEADER) != null
  const hasBranchOverride = getHeader(config, BRANCH_ID_HEADER) != null
  if (hasScopeOverride || hasBranchOverride) return

  const scope = getBranchScopeForApi()
  if (scope === ALL_BRANCH_SCOPE) {
    setHeader(config, BRANCH_SCOPE_HEADER, ALL_BRANCH_SCOPE)
    deleteHeader(config, BRANCH_ID_HEADER)
    return
  }

  const effectiveBranchId = getEffectiveBranchIdForApi()
  if (effectiveBranchId != null) {
    setHeader(config, BRANCH_ID_HEADER, String(effectiveBranchId))
  }
}

/** Per-request override for reports/dashboards (legacy ReportService pattern). */
export function branchHeadersForFilter(
  branchId: number | null | undefined,
  scope?: BranchScope,
): Record<string, string> | undefined {
  if (scope === 'all' || branchId === null) {
    return { [BRANCH_SCOPE_HEADER]: ALL_BRANCH_SCOPE }
  }
  if (typeof branchId === 'number') {
    return { [BRANCH_ID_HEADER]: String(branchId) }
  }
  return undefined
}

export function branchCacheKeySegment(): string {
  const scope = getBranchScopeForApi()
  if (scope === 'all') return 'all'
  const id = getEffectiveBranchIdForApi()
  return id != null ? String(id) : 'none'
}
