'use client'

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import { ArrowLeft, ArrowRight, Building2, CheckCircle2, Globe2, Sparkles } from 'lucide-react'
import { cn } from '@/lib/utils'
import { checkCompanyExists } from '@/services/company.service'
import {
  buildTenantAppUrl,
  buildTenantPreviewHost,
  isTenantSubdomain,
  slugifyCompanyInput,
} from '@/lib/tenantUrl'

const CHECK_DEBOUNCE_MS = 450

type CheckState = {
  isValid: boolean
  message: string
  tone: 'idle' | 'success' | 'error'
}

function WorkspaceGatewayForm() {
  const searchParams = useSearchParams()
  const [companyInput, setCompanyInput] = useState('')
  const [checkState, setCheckState] = useState<CheckState>({
    isValid: false,
    message: '',
    tone: 'idle',
  })
  const [isChecking, setIsChecking] = useState(false)
  const latestInputRef = useRef('')
  const checkSeqRef = useRef(0)
  const prefillDoneRef = useRef(false)

  useEffect(() => {
    if (typeof window === 'undefined') return
    if (isTenantSubdomain(window.location.hostname)) {
      window.location.replace('/login')
    }
  }, [])

  const slug = useMemo(() => slugifyCompanyInput(companyInput), [companyInput])
  const previewHost = useMemo(() => buildTenantPreviewHost(slug || 'your-company'), [slug])

  const runCheck = useCallback(async (value: string) => {
    const trimmed = value.trim()
    const lookupName = slugifyCompanyInput(trimmed) || trimmed
    if (lookupName.length < 2) {
      setCheckState({ isValid: false, message: '', tone: 'idle' })
      setIsChecking(false)
      return
    }

    const seq = ++checkSeqRef.current
    setIsChecking(true)
    setCheckState({ isValid: false, message: '', tone: 'idle' })

    try {
      const data = await checkCompanyExists(lookupName)
      if (seq !== checkSeqRef.current || trimmed !== latestInputRef.current.trim()) return

      setCheckState({
        isValid: data.is_existing,
        message: data.message,
        tone: data.is_existing ? 'success' : 'error',
      })
    } catch {
      if (seq !== checkSeqRef.current) return
      setCheckState({
        isValid: false,
        message: 'Could not verify that workspace. Check your connection and try again.',
        tone: 'error',
      })
    } finally {
      if (seq === checkSeqRef.current) setIsChecking(false)
    }
  }, [])

  useEffect(() => {
    if (prefillDoneRef.current) return
    const fromQuery = searchParams.get('company')?.trim()
    if (!fromQuery || fromQuery.length < 2) return
    prefillDoneRef.current = true
    latestInputRef.current = fromQuery
    setCompanyInput(fromQuery)
    void runCheck(fromQuery)
  }, [searchParams, runCheck])

  useEffect(() => {
    latestInputRef.current = companyInput
    if (companyInput.trim().length < 2) {
      setCheckState({ isValid: false, message: '', tone: 'idle' })
      setIsChecking(false)
      return
    }

    const timer = window.setTimeout(() => {
      void runCheck(companyInput)
    }, CHECK_DEBOUNCE_MS)

    return () => window.clearTimeout(timer)
  }, [companyInput, runCheck])

  const handleContinue = () => {
    if (!checkState.isValid || !slug) return
    const target = buildTenantAppUrl(slug, '/login')
    if (target) window.location.href = target
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    handleContinue()
  }

  return (
    <div className="min-h-screen bg-[#060b1e] text-white overflow-hidden">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top_left,rgba(0,81,81,0.35),transparent_55%),radial-gradient(ellipse_at_bottom_right,rgba(255,191,63,0.12),transparent_50%)]"
      />

      <div className="relative mx-auto flex min-h-screen max-w-6xl flex-col px-4 py-8 sm:px-6 lg:px-8">
        <header className="flex items-center justify-between">
          <Link
            href="/"
            className="inline-flex items-center gap-2 text-sm text-white/70 transition hover:text-white"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to home
          </Link>
          <img src="/img/logo/logo-white.png" alt="ZentroApp" className="h-8 w-auto" />
        </header>

        <main className="flex flex-1 items-center justify-center py-10">
          <div className="grid w-full max-w-5xl gap-10 lg:grid-cols-[1.05fr_0.95fr] lg:items-center">
            <div className="space-y-6">
              <span className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-s2">
                <Sparkles className="h-3.5 w-3.5" />
                Workspace access
              </span>
              <h1 className="text-4xl font-bold leading-tight tracking-tight sm:text-5xl">
                Find your
                <span className="block text-s2">Zentro workspace</span>
              </h1>
              <p className="max-w-md text-base leading-relaxed text-white/70">
                Every business runs on its own secure space. Enter the company name your team
                registered with — we&apos;ll route you to the right sign-in page.
              </p>

              <div className="rounded-2xl border border-white/10 bg-white/5 p-5 backdrop-blur-sm">
                <div className="flex items-start gap-3">
                  <Globe2 className="mt-0.5 h-5 w-5 shrink-0 text-s2" />
                  <div>
                    <p className="text-sm font-medium text-white">How it works</p>
                    <p className="mt-1 text-sm text-white/60">
                      Type <strong className="text-white/90">companyname</strong> and we open{' '}
                      <code className="rounded bg-black/30 px-1.5 py-0.5 text-xs text-s2">
                        companyname.localhost:3000
                      </code>{' '}
                      with your ERP login.
                    </p>
                  </div>
                </div>
              </div>
            </div>

            <div className="rounded-3xl border border-white/10 bg-white p-8 text-mainTextColor shadow-2xl shadow-black/20">
              <div className="mb-6">
                <h2 className="text-xl font-semibold text-mainTextColor">Company workspace</h2>
                <p className="mt-1 text-sm text-bodyText">
                  Use the same name you chose when your account was created.
                </p>
              </div>

              <form onSubmit={handleSubmit} className="space-y-5">
                <div>
                  <label htmlFor="company" className="mb-2 block text-sm font-medium text-mainTextColor">
                    Business name
                  </label>
                  <div className="relative">
                    <Building2 className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-bodyText" />
                    <input
                      id="company"
                      name="company"
                      type="text"
                      value={companyInput}
                      onChange={(e) => setCompanyInput(e.target.value)}
                      placeholder="e.g. companyname"
                      autoComplete="organization"
                      autoFocus
                      className={cn(
                        'flex h-11 w-full rounded-xl border border-strokeColor bg-softBg pl-10 pr-3 text-sm text-mainTextColor',
                        'placeholder:text-bodyText/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-s2 focus-visible:ring-offset-2',
                      )}
                    />
                  </div>
                </div>

                <div className="rounded-xl border border-dashed border-strokeColor bg-softBg2/60 px-4 py-3">
                  <p className="text-xs font-medium uppercase tracking-wide text-bodyText">
                    Your workspace URL
                  </p>
                  <p className="mt-1 break-all font-mono text-sm text-s1">
                    {slug ? previewHost : 'your-company.localhost:3000'}
                  </p>
                </div>

                {(isChecking || checkState.message) && (
                  <div
                    className={cn(
                      'rounded-xl px-4 py-3 text-sm',
                      checkState.tone === 'success' && 'bg-emerald-50 text-emerald-800',
                      checkState.tone === 'error' && 'bg-red-50 text-red-700',
                      checkState.tone === 'idle' && isChecking && 'bg-softBg text-bodyText',
                    )}
                  >
                    {isChecking && checkState.tone === 'idle' ? (
                      'Looking up your workspace…'
                    ) : (
                      <span className="inline-flex items-start gap-2">
                        {checkState.tone === 'success' && (
                          <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
                        )}
                        {checkState.message}
                      </span>
                    )}
                  </div>
                )}

                <button
                  type="submit"
                  disabled={!checkState.isValid || isChecking || !slug}
                  className={cn(
                    'inline-flex h-11 w-full items-center justify-center gap-2 rounded-xl text-sm font-semibold text-white transition',
                    'bg-s1 hover:bg-s1/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-s2 focus-visible:ring-offset-2',
                    'disabled:cursor-not-allowed disabled:opacity-50',
                  )}
                >
                  Continue to sign in
                  <ArrowRight className="h-4 w-4" />
                </button>
              </form>

              <p className="mt-6 text-center text-sm text-bodyText">
                New to Zentro?{' '}
                <Link href="/signup" className="font-medium text-s1 hover:text-s2">
                  Create a free account
                </Link>
              </p>
            </div>
          </div>
        </main>
      </div>
    </div>
  )
}

export function WorkspaceGatewayPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-[#060b1e] text-white/70">
          Loading…
        </div>
      }
    >
      <WorkspaceGatewayForm />
    </Suspense>
  )
}
