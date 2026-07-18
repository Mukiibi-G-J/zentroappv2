'use client'

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import axios from 'axios'
import {
  ArrowLeft,
  ArrowRight,
  Building2,
  CheckCircle2,
  Eye,
  EyeOff,
  Loader2,
  Sparkles,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { PhoneNumberPicker } from '@/components/shared/PhoneNumberPicker'
import {
  clearPendingCompanyCreation,
  readPendingCompanyCreation,
  writePendingCompanyCreation,
} from '@/lib/companyCreationSession'
import { redirectToTenantLoginAfterSignup } from '@/lib/postSignupSession'
import { buildMainAppUrl, buildTenantAppUrl, buildTenantPreviewHost, isTenantSubdomain, slugifyCompanyInput } from '@/lib/tenantUrl'
import {
  createCompanyAccount,
  getTaskStatus,
  type CreateCompanyAccountPayload,
} from '@/services/company.service'
import { getOnboardingData, validateCompanyName } from '@/services/onboarding.service'

const ORG_SIZES = [
  { label: 'Solo', value: 'solo' },
  { label: '2 ~ 10 members', value: '2~10' },
  { label: '11 ~ 50 members', value: '11~50' },
  { label: '51 ~ 200 members', value: '51~200' },
  { label: '201 ~ 500 members', value: '201~500' },
] as const

const SIGNUP_TRIAL_ELIGIBLE_PLANS = new Set(['Starter', 'Business', 'Pro'])

type CompanyData = {
  organizationName: string
  organizationSize: string
  businessCategory: string
  businessObjective: string
}

type AccountForm = {
  companyEmail: string
  companyPhone: string
  companyAddress: string
  companyCountry: string
  fullName: string
  password: string
  confirmPassword: string
}

type CreationStatus = {
  state: string
  progress: number
  message: string
  status: string
  loginUrl?: string
}

const PROGRESS_STEPS: Array<{ progress: number; message: string; status: string; delay: number }> =
  [
    { progress: 10, message: 'Validating data…', status: 'validating', delay: 1000 },
    { progress: 20, message: 'Creating company…', status: 'creating_company', delay: 1500 },
    { progress: 40, message: 'Setting up domain…', status: 'setting_domain', delay: 1000 },
    { progress: 60, message: 'Creating admin user…', status: 'creating_user', delay: 2000 },
    { progress: 75, message: 'Importing initial data…', status: 'importing_data', delay: 2500 },
    { progress: 90, message: 'Setting up number series…', status: 'setting_up_series', delay: 2000 },
    { progress: 96, message: 'Finalizing setup…', status: 'finalizing', delay: 1500 },
  ]

function resolveSignupPlan(planFromQuery: string | null): string {
  const raw = planFromQuery?.trim() || ''
  if (!raw || !SIGNUP_TRIAL_ELIGIBLE_PLANS.has(raw)) return 'Free Trial'
  return raw
}

function resolveDefaultOnboardingIds(
  categories: { id: number; name: string }[],
  objectives: { id: number; description: string }[],
) {
  const category = categories.find((c) => /^others?$/i.test(c.name.trim())) ?? categories[0]
  const objective =
    objectives.find((o) => o.description === 'Start a New Business') ?? objectives[0]
  return {
    businessCategory: category ? String(category.id) : '',
    businessObjective: objective ? String(objective.id) : '',
  }
}

function validateAccountForm(values: AccountForm): string | null {
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(values.companyEmail.trim())) {
    return 'Enter a valid email address.'
  }
  if (!/^\+[1-9]\d{7,14}$/.test(values.companyPhone.trim())) {
    return 'Enter a valid international phone number starting with + (E.164).'
  }
  if (!values.companyAddress.trim()) return 'Address is required.'
  if (!/^[a-zA-Z0-9\s,.-]+$/.test(values.companyAddress.trim())) {
    return 'Address can only contain letters, numbers, spaces, commas, dots, and hyphens.'
  }
  if (!values.companyCountry.trim()) return 'Country is required.'
  if (values.fullName.trim().length < 3) return 'Full name must be at least 3 characters.'
  if (!/^[a-zA-Z\s]+$/.test(values.fullName.trim())) {
    return 'Full name can only contain letters and spaces.'
  }
  if (values.password.length < 8) return 'Password must be at least 8 characters.'
  if (!/[A-Z]/.test(values.password)) return 'Password must contain an uppercase letter.'
  if (!/[a-z]/.test(values.password)) return 'Password must contain a lowercase letter.'
  if (!/[0-9]/.test(values.password)) return 'Password must contain a number.'
  if (!/[!@#$%^&*(),.?":{}|<>]/.test(values.password)) {
    return 'Password must contain a special character.'
  }
  if (values.password !== values.confirmPassword) return 'Passwords do not match.'
  return null
}

function SignupWizardForm() {
  const searchParams = useSearchParams()
  const selectedPlanName = useMemo(
    () => resolveSignupPlan(searchParams.get('plan')),
    [searchParams],
  )

  const [step, setStep] = useState(0)
  const [companyData, setCompanyData] = useState<CompanyData>({
    organizationName: '',
    organizationSize: '',
    businessCategory: '',
    businessObjective: '',
  })
  const [onboardingReady, setOnboardingReady] = useState(false)
  const [onboardingError, setOnboardingError] = useState(false)

  const [orgNameInput, setOrgNameInput] = useState('')
  const [orgSize, setOrgSize] = useState('')
  const [nameCheck, setNameCheck] = useState<{
    isValid: boolean
    message: string
    tone: 'idle' | 'success' | 'error'
  }>({ isValid: false, message: '', tone: 'idle' })
  const [isCheckingName, setIsCheckingName] = useState(false)
  const nameCheckSeq = useRef(0)

  const [accountForm, setAccountForm] = useState<AccountForm>({
    companyEmail: '',
    companyPhone: '',
    companyAddress: '',
    companyCountry: 'UG',
    fullName: '',
    password: '',
    confirmPassword: '',
  })
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const [taskId, setTaskId] = useState<string | null>(null)
  const [creationStatus, setCreationStatus] = useState<CreationStatus | null>(null)
  const credentialsRef = useRef<{ email: string; password: string } | null>(null)

  const slug = useMemo(() => slugifyCompanyInput(companyData.organizationName), [companyData.organizationName])
  const liveSlug = useMemo(() => slugifyCompanyInput(orgNameInput), [orgNameInput])
  const previewHost = useMemo(
    () => buildTenantPreviewHost(liveSlug || slug || 'your-company'),
    [liveSlug, slug],
  )

  useEffect(() => {
    if (typeof window === 'undefined') return
    if (isTenantSubdomain(window.location.hostname)) {
      window.location.replace(buildMainAppUrl('/signup'))
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    const pending = readPendingCompanyCreation()
    if (pending?.taskId && pending.companyData) {
      setCompanyData((prev) => ({ ...prev, ...pending.companyData }))
      setStep(2)
      setTaskId(pending.taskId)
      credentialsRef.current = pending.credentials ?? null
      setCreationStatus({
        state: 'PROGRESS',
        progress: 10,
        message: 'Resuming company setup…',
        status: 'validating',
      })
      setOnboardingReady(true)
      return
    }

    void (async () => {
      try {
        const data = await getOnboardingData()
        const defaults = resolveDefaultOnboardingIds(
          data.business_categories,
          data.business_objectives,
        )
        if (!cancelled) {
          setCompanyData((prev) => ({ ...prev, ...defaults }))
          setOnboardingReady(true)
        }
      } catch {
        if (!cancelled) setOnboardingError(true)
      }
    })()

    return () => {
      cancelled = true
    }
  }, [])

  const runNameValidation = useCallback(async (value: string) => {
    const trimmed = value.trim()
    if (trimmed.length < 3) {
      setNameCheck({ isValid: false, message: '', tone: 'idle' })
      setIsCheckingName(false)
      return
    }

    const seq = ++nameCheckSeq.current
    setIsCheckingName(true)
    setNameCheck({ isValid: false, message: '', tone: 'idle' })

    try {
      const data = await validateCompanyName(trimmed)
      if (seq !== nameCheckSeq.current) return
      setNameCheck({
        isValid: data.isValid,
        message: data.message,
        tone: data.isValid ? 'success' : 'error',
      })
    } catch (err) {
      if (seq !== nameCheckSeq.current) return
      if (axios.isAxiosError(err) && err.response?.data && typeof err.response.data === 'object') {
        const body = err.response.data as { isValid?: boolean; message?: string; errors?: string[] }
        setNameCheck({
          isValid: body.isValid ?? false,
          message: body.message || 'Unable to validate company name',
          tone: 'error',
        })
        return
      }
      setNameCheck({
        isValid: false,
        message: 'Unable to validate company name. Check your connection.',
        tone: 'error',
      })
    } finally {
      if (seq === nameCheckSeq.current) setIsCheckingName(false)
    }
  }, [])

  useEffect(() => {
    if (step !== 1) return
    const timer = window.setTimeout(() => {
      void runNameValidation(orgNameInput)
    }, 450)
    return () => window.clearTimeout(timer)
  }, [orgNameInput, step, runNameValidation])

  useEffect(() => {
    if (!taskId) return

    let intervalId: ReturnType<typeof setInterval>
    let progressTimeoutId: ReturnType<typeof setTimeout> | null = null
    let isBackendCompleted = false
    let stepIndex = 0
    let sawWorkerPickup = false
    /** Latest progress reported by Celery (drives the UI once the worker starts). */
    let backendProgress = 0
    let lastProgressKey = ''
    let lastProgressChangeAt = Date.now()
    const pollStartedAt = Date.now()
    /** If Celery never leaves PENDING, stop faking progress and fail. */
    const PENDING_STUCK_MS = 90_000
    /** Same PROGRESS payload for this long → worker likely interrupted mid-clone. */
    const PROGRESS_STUCK_MS = 8 * 60_000

    const failCreation = (message: string) => {
      isBackendCompleted = true
      clearInterval(intervalId)
      if (progressTimeoutId) clearTimeout(progressTimeoutId)
      clearPendingCompanyCreation()
      setCreationStatus({
        state: 'FAILURE',
        progress: 0,
        message,
        status: 'failed',
      })
    }

    const pollStatus = async () => {
      try {
        const response = await getTaskStatus(taskId)

        if (
          response.status === 'unknown' ||
          response.status === 'abandoned' ||
          (response.state === 'FAILURE' && response.enqueued === false)
        ) {
          failCreation(
            response.message ||
              'Company creation was never started. Clear the session and try again, and confirm Celery + Redis are running.',
          )
          return
        }

        if (response.state !== 'PENDING') {
          sawWorkerPickup = true
        }

        if (response.state === 'PENDING' && Date.now() - pollStartedAt > PENDING_STUCK_MS) {
          failCreation(
            'Celery did not pick up the company-creation task. Start the worker (`celery -A core worker -l info`) and Redis, then try again.',
          )
          return
        }

        if (response.state === 'PROGRESS') {
          const progress =
            typeof response.progress === 'number' ? response.progress : backendProgress
          backendProgress = Math.max(backendProgress, progress)
          const progressKey = `${progress}|${response.message}|${response.status}`
          if (progressKey !== lastProgressKey) {
            lastProgressKey = progressKey
            lastProgressChangeAt = Date.now()
          } else if (Date.now() - lastProgressChangeAt > PROGRESS_STUCK_MS) {
            failCreation(
              response.message
                ? `${response.message} — this step stopped updating. Leave Celery running (do not Ctrl+C), clear the signup session, and try again.`
                : 'Company creation stuck with no progress. Leave Celery running, clear the signup session, and try again.',
            )
            return
          }
          setCreationStatus({
            state: 'PROGRESS',
            progress: backendProgress,
            message: response.message || 'Working…',
            status: response.status || 'progress',
          })
          return
        }

        if (['SUCCESS', 'FAILURE'].includes(response.state)) {
          isBackendCompleted = true
          clearInterval(intervalId)
          if (progressTimeoutId) clearTimeout(progressTimeoutId)

          if (response.state === 'SUCCESS') {
            clearPendingCompanyCreation()
            const email = credentialsRef.current?.email?.trim() || ''
            let loginUrl =
              response.login_url ||
              (typeof response.result?.login_url === 'string'
                ? response.result.login_url
                : '') ||
              ''

            if (loginUrl) {
              try {
                const u = new URL(loginUrl)
                if (email && !u.searchParams.get('email')) u.searchParams.set('email', email)
                u.searchParams.set('setup', '1')
                loginUrl = u.toString()
              } catch {
                // keep loginUrl as-is
              }
            } else {
              loginUrl = buildTenantAppUrl(
                companyData.organizationName,
                (() => {
                  const params = new URLSearchParams({ setup: '1' })
                  if (email) params.set('email', email)
                  return `/login?${params.toString()}`
                })(),
              )
            }

            setCreationStatus({
              state: 'SUCCESS',
              progress: 100,
              message: 'Company setup completed successfully!',
              status: 'completed',
              loginUrl: loginUrl || undefined,
            })

            if (loginUrl) {
              // Hard navigation — do not depend on tenant token/OTP (often blocked by CORS).
              window.location.replace(loginUrl)
            } else {
              try {
                redirectToTenantLoginAfterSignup(
                  companyData.organizationName,
                  email,
                )
              } catch {
                setFormError(
                  'Company is ready. Use the button below to open your workspace login.',
                )
              }
            }
          } else {
            clearPendingCompanyCreation()
            setCreationStatus({
              state: 'FAILURE',
              progress: 0,
              message: response.message || 'Company creation failed',
              status: 'failed',
            })
          }
        }
      } catch (err) {
        const msg = axios.isAxiosError(err)
          ? err.response?.data &&
            typeof err.response.data === 'object' &&
            'message' in err.response.data
            ? String((err.response.data as { message?: string }).message || '')
            : err.message
          : ''
        failCreation(
          msg ||
            'Could not reach the server for task status. Check that Django is running on :8002 and try again.',
        )
      }
    }

    const showNextStep = () => {
      if (isBackendCompleted) return
      // Prefer Celery progress once the worker has reported PROGRESS/STARTED.
      if (sawWorkerPickup && backendProgress > 0) {
        progressTimeoutId = setTimeout(showNextStep, 2000)
        return
      }
      // Do not animate past early steps until Celery has actually started the job.
      if (!sawWorkerPickup && stepIndex >= 2) {
        setCreationStatus((prev) =>
          prev
            ? {
                ...prev,
                progress: Math.min(Math.max(prev.progress, 10), 20),
                message: 'Waiting for Celery worker to start…',
                status: 'pending',
              }
            : prev,
        )
        progressTimeoutId = setTimeout(showNextStep, 2000)
        return
      }
      if (stepIndex >= PROGRESS_STEPS.length) {
        if (!isBackendCompleted) {
          setCreationStatus((prev) =>
            prev
              ? {
                  ...prev,
                  progress: Math.min(prev.progress, 20),
                  message: prev.message || 'Waiting for backend…',
                  status: 'waiting',
                }
              : prev,
          )
        }
        return
      }
      const current = PROGRESS_STEPS[stepIndex]
      // Cap optimistic animation below / at the next real backend milestone.
      const capped = Math.min(current.progress, Math.max(backendProgress, 20))
      setCreationStatus({
        state: 'PROGRESS',
        progress: capped,
        message: current.message,
        status: current.status,
      })
      stepIndex += 1
      progressTimeoutId = setTimeout(showNextStep, current.delay)
    }

    showNextStep()
    void pollStatus()
    intervalId = setInterval(pollStatus, 2000)

    return () => {
      clearInterval(intervalId)
      if (progressTimeoutId) clearTimeout(progressTimeoutId)
    }
  }, [taskId, companyData.organizationName])

  const handleOrgContinue = () => {
    if (!nameCheck.isValid || !orgSize) return
    setCompanyData((prev) => ({
      ...prev,
      organizationName: orgNameInput.trim(),
      organizationSize: orgSize,
    }))
    setStep(2)
  }

  const handleAccountSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setFormError(null)

    const validationError = validateAccountForm(accountForm)
    if (validationError) {
      setFormError(validationError)
      return
    }

    setIsSubmitting(true)
    try {
      const payload: CreateCompanyAccountPayload = {
        companyName: companyData.organizationName,
        companyEmail: accountForm.companyEmail.trim(),
        companyPhone: accountForm.companyPhone.trim(),
        companyAddress: accountForm.companyAddress.trim(),
        companyCountry: accountForm.companyCountry.trim(),
        fullName: accountForm.fullName.trim(),
        password: accountForm.password,
        organization_size: companyData.organizationSize,
        business_category: companyData.businessCategory,
        business_objective: companyData.businessObjective,
        subscription: {
          plan: selectedPlanName,
          price: 30000,
          yearlyPrice: 288000,
        },
      }

      const response = await createCompanyAccount(payload)
      if (!response.task_id) {
        setFormError('Failed to start company creation. Please try again.')
        return
      }

      credentialsRef.current = {
        email: accountForm.companyEmail.trim(),
        password: accountForm.password,
      }

      writePendingCompanyCreation({
        taskId: response.task_id,
        planName: selectedPlanName,
        companyData,
        credentials: credentialsRef.current,
        createdAt: Date.now(),
      })

      setTaskId(response.task_id)
      setCreationStatus({
        state: 'PROGRESS',
        progress: 10,
        message: 'Starting company setup…',
        status: 'validating',
      })
    } catch (err) {
      if (axios.isAxiosError(err)) {
        const data = err.response?.data as { message?: string; error_type?: string } | undefined
        if (err.response?.status === 503) {
          setFormError('Service is temporarily unavailable. Please try again in a few minutes.')
        } else {
          setFormError(data?.message || 'Failed to create company account. Please try again.')
        }
      } else {
        setFormError('Failed to create company account. Please try again.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  const shell = (content: React.ReactNode) => (
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
        <main className="flex flex-1 items-center justify-center py-10">{content}</main>
      </div>
    </div>
  )

  if (onboardingError) {
    return shell(
      <div className="max-w-md rounded-3xl border border-white/10 bg-white p-8 text-center text-mainTextColor">
        <p className="text-red-600">We couldn&apos;t load signup defaults. Please refresh and try again.</p>
        <button
          type="button"
          onClick={() => window.location.reload()}
          className="mt-4 text-s1 font-medium hover:text-s2"
        >
          Refresh
        </button>
      </div>,
    )
  }

  if (step === 0) {
    return shell(
      <div className="w-full max-w-lg text-center">
        <span className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-s2">
          <Sparkles className="h-3.5 w-3.5" />
          Get started
        </span>
        <h1 className="mt-6 text-3xl font-bold leading-tight sm:text-4xl">
          Welcome to Zentro
        </h1>
        <p className="mt-3 text-white/70">
          Set up your business workspace in a few minutes — inventory, sales, and reports included.
        </p>
        {selectedPlanName !== 'Free Trial' && (
          <p className="mt-2 text-sm text-s2">Selected plan: {selectedPlanName}</p>
        )}
        <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:justify-center">
          <button
            type="button"
            onClick={() => setStep(1)}
            disabled={!onboardingReady}
            className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-s1 px-8 text-sm font-semibold text-white hover:bg-s1/90 disabled:opacity-50"
          >
            {onboardingReady ? 'Get started' : 'Loading…'}
            <ArrowRight className="h-4 w-4" />
          </button>
          <Link
            href="/workspace"
            className="inline-flex h-11 items-center justify-center rounded-xl border border-white/20 px-8 text-sm font-semibold text-white/90 hover:bg-white/5"
          >
            Already have an account
          </Link>
        </div>
      </div>,
    )
  }

  if (step === 1) {
    return shell(
      <div className="w-full max-w-xl rounded-3xl border border-white/10 bg-white p-8 text-mainTextColor shadow-2xl">
        <button
          type="button"
          onClick={() => setStep(0)}
          className="mb-4 inline-flex items-center gap-1 text-sm text-bodyText hover:text-mainTextColor"
        >
          <ArrowLeft className="h-4 w-4" />
          Back
        </button>
        <h2 className="text-xl font-semibold">Tell us about your organization</h2>
        <p className="mt-1 text-sm text-bodyText">
          This name becomes your workspace URL — choose something your team will recognize.
        </p>

        <div className="mt-6 space-y-5">
          <div>
            <label htmlFor="orgName" className="mb-2 block text-sm font-medium">
              Company / organization name
            </label>
            <div className="relative">
              <Building2 className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-bodyText" />
              <input
                id="orgName"
                value={orgNameInput}
                onChange={(e) => setOrgNameInput(e.target.value)}
                placeholder="e.g. companyname"
                className="flex h-11 w-full rounded-xl border border-strokeColor bg-softBg pl-10 pr-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-s2"
              />
            </div>
            <div className="mt-3 rounded-xl border border-dashed border-strokeColor bg-softBg2/60 px-4 py-3">
              <p className="text-xs font-medium uppercase tracking-wide text-bodyText">Workspace URL</p>
              <p className="mt-1 font-mono text-sm text-s1">
                {liveSlug ? previewHost : 'your-company.localhost:3000'}
              </p>
            </div>
            {(isCheckingName || nameCheck.message) && (
              <div
                className={cn(
                  'mt-3 rounded-xl px-4 py-3 text-sm',
                  nameCheck.tone === 'success' && 'bg-emerald-50 text-emerald-800',
                  nameCheck.tone === 'error' && 'bg-red-50 text-red-700',
                  nameCheck.tone === 'idle' && isCheckingName && 'bg-softBg text-bodyText',
                )}
              >
                {isCheckingName && nameCheck.tone === 'idle'
                  ? 'Checking availability…'
                  : nameCheck.message}
              </div>
            )}
          </div>

          <div>
            <label htmlFor="orgSize" className="mb-2 block text-sm font-medium">
              Organization size
            </label>
            <select
              id="orgSize"
              value={orgSize}
              onChange={(e) => setOrgSize(e.target.value)}
              className="flex h-11 w-full rounded-xl border border-strokeColor bg-softBg px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-s2"
            >
              <option value="">Select size…</option>
              {ORG_SIZES.map((size) => (
                <option key={size.value} value={size.value}>
                  {size.label}
                </option>
              ))}
            </select>
          </div>

          <button
            type="button"
            disabled={!nameCheck.isValid || !orgSize || isCheckingName}
            onClick={handleOrgContinue}
            className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-s1 text-sm font-semibold text-white hover:bg-s1/90 disabled:opacity-50"
          >
            Continue
            <ArrowRight className="h-4 w-4" />
          </button>
        </div>
      </div>,
    )
  }

  return shell(
    <div className="w-full max-w-2xl rounded-3xl border border-white/10 bg-white p-8 text-mainTextColor shadow-2xl">
      {!taskId && (
        <button
          type="button"
          onClick={() => setStep(1)}
          className="mb-4 inline-flex items-center gap-1 text-sm text-bodyText hover:text-mainTextColor"
        >
          <ArrowLeft className="h-4 w-4" />
          Back
        </button>
      )}

      <h2 className="text-xl font-semibold">
        {taskId ? 'Setting up your workspace' : 'Create your account'}
      </h2>
      <p className="mt-1 text-sm text-bodyText">
        {taskId
          ? `Provisioning ${companyData.organizationName} — this usually takes a minute.`
          : 'Your admin login and business contact details.'}
      </p>

      {taskId ? (
        <div className="mt-8 space-y-6">
          <div className="h-2 overflow-hidden rounded-full bg-softBg">
            <div
              className="h-full rounded-full bg-s1 transition-all duration-500"
              style={{ width: `${creationStatus?.progress ?? 0}%` }}
            />
          </div>
          <div className="flex items-start gap-3 rounded-xl bg-softBg px-4 py-3">
            {creationStatus?.state === 'SUCCESS' ? (
              <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600" />
            ) : creationStatus?.state === 'FAILURE' ? (
              <span className="text-red-600">✕</span>
            ) : (
              <Loader2 className="mt-0.5 h-5 w-5 shrink-0 animate-spin text-s1" />
            )}
            <div>
              <p className="font-medium">{creationStatus?.message || 'Working…'}</p>
              {creationStatus?.progress != null && creationStatus.state !== 'FAILURE' && (
                <p className="text-sm text-bodyText">{creationStatus.progress}% complete</p>
              )}
            </div>
          </div>
          {creationStatus?.state === 'SUCCESS' && creationStatus.loginUrl && (
            <a
              href={creationStatus.loginUrl}
              className="inline-flex h-11 w-full items-center justify-center rounded-xl bg-s1 text-sm font-semibold text-white"
            >
              Continue to sign in
            </a>
          )}
          {creationStatus?.state === 'FAILURE' && (
            <button
              type="button"
              onClick={() => {
                clearPendingCompanyCreation()
                setTaskId(null)
                setCreationStatus(null)
              }}
              className="inline-flex h-11 w-full items-center justify-center rounded-xl bg-s1 text-sm font-semibold text-white"
            >
              Try again
            </button>
          )}
          {formError && <p className="text-sm text-amber-700">{formError}</p>}
        </div>
      ) : (
        <form onSubmit={handleAccountSubmit} className="mt-6 space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <label className="mb-2 block text-sm font-medium">Business name</label>
              <input
                value={companyData.organizationName}
                disabled
                className="flex h-11 w-full rounded-xl border border-strokeColor bg-softBg px-3 text-sm opacity-80"
              />
            </div>
            <div>
              <label htmlFor="companyEmail" className="mb-2 block text-sm font-medium">
                Email
              </label>
              <input
                id="companyEmail"
                type="email"
                value={accountForm.companyEmail}
                onChange={(e) => setAccountForm((p) => ({ ...p, companyEmail: e.target.value }))}
                placeholder="you@example.com"
                className="flex h-11 w-full rounded-xl border border-strokeColor bg-softBg px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-s2"
              />
            </div>
            <div>
              <label htmlFor="companyPhone" className="mb-2 block text-sm font-medium">
                Phone
              </label>
              <PhoneNumberPicker
                id="companyPhone"
                value={accountForm.companyPhone || undefined}
                defaultCountry="UG"
                placeholder="Phone number"
                onChange={(value) =>
                  setAccountForm((p) => ({ ...p, companyPhone: value ?? '' }))
                }
                onCountryChange={(country) => {
                  if (country) {
                    setAccountForm((p) => ({ ...p, companyCountry: country }))
                  }
                }}
              />
            </div>
            <div className="sm:col-span-2">
              <label htmlFor="companyAddress" className="mb-2 block text-sm font-medium">
                Address
              </label>
              <input
                id="companyAddress"
                value={accountForm.companyAddress}
                onChange={(e) => setAccountForm((p) => ({ ...p, companyAddress: e.target.value }))}
                placeholder="Street, building, or area"
                className="flex h-11 w-full rounded-xl border border-strokeColor bg-softBg px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-s2"
              />
            </div>
            <div className="hidden">
              <input
                id="companyCountry"
                value={accountForm.companyCountry}
                readOnly
                tabIndex={-1}
                aria-hidden
              />
            </div>
            <div className="sm:col-span-2">
              <label htmlFor="fullName" className="mb-2 block text-sm font-medium">
                Your full name
              </label>
              <input
                id="fullName"
                value={accountForm.fullName}
                onChange={(e) => setAccountForm((p) => ({ ...p, fullName: e.target.value }))}
                placeholder="Full name"
                className="flex h-11 w-full rounded-xl border border-strokeColor bg-softBg px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-s2"
              />
            </div>
            <div>
              <label htmlFor="password" className="mb-2 block text-sm font-medium">
                Password
              </label>
              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  value={accountForm.password}
                  onChange={(e) => setAccountForm((p) => ({ ...p, password: e.target.value }))}
                  className="flex h-11 w-full rounded-xl border border-strokeColor bg-softBg px-3 pr-10 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-s2"
                />
                <button
                  type="button"
                  tabIndex={-1}
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-bodyText"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>
            <div>
              <label htmlFor="confirmPassword" className="mb-2 block text-sm font-medium">
                Confirm password
              </label>
              <div className="relative">
                <input
                  id="confirmPassword"
                  type={showConfirmPassword ? 'text' : 'password'}
                  value={accountForm.confirmPassword}
                  onChange={(e) =>
                    setAccountForm((p) => ({ ...p, confirmPassword: e.target.value }))
                  }
                  className="flex h-11 w-full rounded-xl border border-strokeColor bg-softBg px-3 pr-10 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-s2"
                />
                <button
                  type="button"
                  tabIndex={-1}
                  onClick={() => setShowConfirmPassword((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-bodyText"
                >
                  {showConfirmPassword ? (
                    <EyeOff className="h-4 w-4" />
                  ) : (
                    <Eye className="h-4 w-4" />
                  )}
                </button>
              </div>
            </div>
          </div>

          {formError && (
            <div className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">{formError}</div>
          )}

          <button
            type="submit"
            disabled={isSubmitting}
            className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-s1 text-sm font-semibold text-white hover:bg-s1/90 disabled:opacity-50"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Creating account…
              </>
            ) : (
              <>
                Create workspace
                <ArrowRight className="h-4 w-4" />
              </>
            )}
          </button>
        </form>
      )}
    </div>,
  )
}

export function SignupWizardPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-[#060b1e] text-white/70">
          Loading…
        </div>
      }
    >
      <SignupWizardForm />
    </Suspense>
  )
}
