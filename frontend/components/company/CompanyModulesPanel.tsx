'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import axios from 'axios'
import Link from 'next/link'
import { useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { useSession } from '@/context/SessionContext'
import { usePageNavigation } from '@/hooks/usePageNavigation'
import {
  toggleModuleAndRefresh,
  useCompanyModules,
} from '@/hooks/useCompanyModules'
import {
  getCompanyOverview,
  listCurrencies,
  updateCompanyLocalCurrency,
  type CompanyModule,
  type CurrencyOption,
} from '@/services/company.service'
import { cn } from '@/lib/utils'

const DEFAULT_LOCAL_CURRENCY = 'UGX'

function isCompanyAdmin(role: string | undefined): boolean {
  const normalized = (role || '').toLowerCase()
  return normalized.includes('admin')
}

function ModuleStatusCell({
  mod,
  isTrial,
  allowManualModuleToggle,
  toggling,
  onToggle,
}: {
  mod: CompanyModule
  isTrial: boolean
  allowManualModuleToggle: boolean
  toggling: boolean
  onToggle: (moduleId: string, action: 'enable' | 'disable') => void
}) {
  const canDisable = allowManualModuleToggle && mod.from_override && !mod.from_plan
  const canEnable = allowManualModuleToggle && !mod.enabled

  if (mod.enabled && mod.from_plan) {
    return (
      <span className="inline-flex items-center rounded-md border border-strokeColor bg-softBg px-2.5 py-0.5 text-xs font-medium text-bodyText">
        Included in Plan
      </span>
    )
  }

  if (mod.enabled && canDisable) {
    return (
      <button
        type="button"
        onClick={() => onToggle(mod.identifier, 'disable')}
        disabled={toggling}
        className="inline-flex items-center gap-1.5 rounded-md border border-strokeColor bg-white px-3 py-1 text-xs font-medium text-bodyText transition-colors hover:bg-softBg disabled:opacity-50"
      >
        {toggling ? (
          <Loader2 className="h-3 w-3 animate-spin" />
        ) : (
          <span className="h-1.5 w-1.5 rounded-full bg-bodyText/40" />
        )}
        {isTrial ? 'Trial — Disable' : 'Remove override'}
      </button>
    )
  }

  if (mod.enabled) {
    return (
      <span className="inline-flex items-center rounded-md border border-strokeColor bg-softBg px-2.5 py-0.5 text-xs font-medium text-bodyText">
        Enabled
      </span>
    )
  }

  if (canEnable) {
    return (
      <button
        type="button"
        onClick={() => onToggle(mod.identifier, 'enable')}
        disabled={toggling}
        className="inline-flex items-center gap-1.5 rounded-md border border-strokeColor bg-white px-3 py-1 text-xs font-medium text-p1 transition-colors hover:bg-softBg disabled:opacity-50"
      >
        {toggling ? <Loader2 className="h-3 w-3 animate-spin" /> : null}
        {isTrial ? 'Try it' : 'Include module'}
      </button>
    )
  }

  return (
    <span className="inline-flex items-center rounded-md border border-strokeColor bg-softBg px-2.5 py-0.5 text-xs font-medium text-bodyText/70">
      Not Included
    </span>
  )
}

export default function CompanyModulesPanel() {
  const queryClient = useQueryClient()
  const { session, refreshSession } = useSession()
  const { navigateToPageName } = usePageNavigation()
  const { data, isLoading, isError, error } = useCompanyModules()

  const [togglingModule, setTogglingModule] = useState<string | null>(null)
  const [localCurrencyCode, setLocalCurrencyCode] = useState(DEFAULT_LOCAL_CURRENCY)
  const [currencyOptions, setCurrencyOptions] = useState<CurrencyOption[]>([])
  const [loadingCurrencies, setLoadingCurrencies] = useState(true)
  const [savingCurrency, setSavingCurrency] = useState(false)

  const isAdmin = isCompanyAdmin(session?.user.role)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        setLoadingCurrencies(true)
        const [overview, currencies] = await Promise.all([
          getCompanyOverview(),
          listCurrencies(),
        ])
        if (cancelled) return
        setLocalCurrencyCode(
          overview.settings?.localCurrencyCode?.trim() || DEFAULT_LOCAL_CURRENCY,
        )
        setCurrencyOptions(currencies)
      } catch {
        if (!cancelled) toast.error('Could not load regional settings')
      } finally {
        if (!cancelled) setLoadingCurrencies(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const modules = data?.modules ?? []
  const enabledModules = useMemo(() => {
    const raw = data?.enabled_modules ?? []
    if (raw.includes('sales') && raw.includes('pos')) {
      return raw.filter((mod) => mod !== 'pos')
    }
    return raw
  }, [data?.enabled_modules])
  const moduleOverrides = useMemo(() => {
    const raw = data?.module_overrides ?? []
    const enabled = data?.enabled_modules ?? []
    if (enabled.includes('sales')) {
      return raw.filter((mod) => mod !== 'pos')
    }
    return raw
  }, [data?.enabled_modules, data?.module_overrides])
  const planName = data?.plan_name
  const planBranches = data?.plan_branches
  const isTrial = data?.is_trial ?? false
  const allowManualModuleToggle = data?.allow_manual_module_toggle ?? false

  const moduleLabelById = useMemo(() => {
    const map = new Map<string, string>()
    for (const mod of modules) map.set(mod.identifier, mod.display_name)
    return map
  }, [modules])

  const handleToggleModule = useCallback(
    async (moduleId: string, action: 'enable' | 'disable') => {
      try {
        setTogglingModule(moduleId)
        const result = await toggleModuleAndRefresh(queryClient, moduleId, action)
        await refreshSession()
        const label = moduleLabelById.get(moduleId) ?? moduleId
        if (action === 'enable') {
          toast.success(
            result.setup_ran
              ? `${label} is ready — permissions and setup were configured. Refresh or sign in again to update navigation.`
              : `${label} enabled. Refresh or sign in again to update navigation.`,
          )
        } else {
          toast.success(`${label} disabled. Refresh or sign in again to update navigation.`)
        }
      } catch (err) {
        let message = `Failed to ${action} module`
        if (axios.isAxiosError(err)) {
          message = err.response?.data?.error ?? message
        } else if (err instanceof Error) {
          message = err.message
        }
        toast.error(message)
      } finally {
        setTogglingModule(null)
      }
    },
    [moduleLabelById, queryClient, refreshSession],
  )

  const handleSaveCurrency = async () => {
    try {
      setSavingCurrency(true)
      const response = await updateCompanyLocalCurrency(localCurrencyCode)
      const saved = response.settings?.localCurrencyCode ?? localCurrencyCode
      setLocalCurrencyCode(saved)
      await refreshSession()
      toast.success('Local currency saved')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to save currency')
    } finally {
      setSavingCurrency(false)
    }
  }

  const openBranchManagement = async () => {
    await navigateToPageName('GeneralLedgerSetupCard')
  }

  if (isLoading) {
    return (
      <div className="flex flex-1 min-h-0 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-p1" />
      </div>
    )
  }

  if (isError) {
    return (
      <div className="flex-1 min-h-0 overflow-y-auto">
        <div className="mx-auto max-w-6xl rounded-xl border border-red-200 bg-red-50 p-6 text-sm text-red-800">
          {error instanceof Error ? error.message : 'Failed to load company settings'}
        </div>
      </div>
    )
  }

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-1 min-h-0 flex-col gap-8 overflow-y-auto">
      <div>
        <Link
          href="/dashboard"
          className="mb-4 inline-flex items-center gap-2 text-sm font-medium text-p1 hover:underline"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to dashboard
        </Link>
        <h1 className="text-2xl font-bold text-mainTextColor">Company Settings</h1>
        <p className="mt-1 text-sm text-bodyText">
          Regional settings and module access for your company.
        </p>
      </div>

      <section className="rounded-xl border border-strokeColor bg-white p-5 shadow-sm">
        <h2 className="text-lg font-semibold text-mainTextColor">Regional Settings</h2>
        <p className="mt-1 text-sm text-bodyText">
          Local currency used across sales, purchases, financials, and reports.
        </p>
        <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-end">
          <label className="flex min-w-0 flex-1 flex-col gap-1.5 text-sm">
            <span className="font-medium text-mainTextColor">Local Currency Code</span>
            <select
              value={localCurrencyCode}
              onChange={(e) => setLocalCurrencyCode(e.target.value)}
              disabled={!isAdmin || loadingCurrencies}
              className="h-10 w-full rounded-lg border border-strokeColor bg-white px-3 text-sm disabled:opacity-60"
            >
              {currencyOptions.map((opt) => (
                <option key={opt.code} value={opt.code}>
                  {opt.code}: {opt.name}
                </option>
              ))}
            </select>
          </label>
          {isAdmin && (
            <button
              type="button"
              onClick={handleSaveCurrency}
              disabled={savingCurrency || loadingCurrencies}
              className="inline-flex h-10 items-center justify-center rounded-lg bg-p1 px-4 text-sm font-medium text-white hover:bg-p1/90 disabled:opacity-60"
            >
              {savingCurrency ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Save currency'}
            </button>
          )}
        </div>
        {!isAdmin && (
          <p className="mt-2 text-sm text-bodyText">
            Only company administrators can change the local currency.
          </p>
        )}
      </section>

      {isTrial && (
        <div className="rounded-xl border border-strokeColor bg-softBg p-4">
          <p className="font-semibold text-mainTextColor">You&apos;re on a free trial</p>
          <p className="mt-1 text-sm text-bodyText">
            Try any module for free during your trial. When the trial ends, only modules included in
            your paid plan will remain active.
          </p>
        </div>
      )}

      {allowManualModuleToggle && !isTrial && (
        <div className="rounded-xl border border-strokeColor bg-softBg p-4">
          <p className="font-semibold text-mainTextColor">Manual module access (support)</p>
          <p className="mt-1 text-sm text-bodyText">
            You can include modules that are not part of this company&apos;s subscription.
            Overrides are stored on the tenant until removed.
          </p>
        </div>
      )}

      <section className="rounded-xl border border-strokeColor bg-white p-5 shadow-sm">
        <h2 className="text-lg font-semibold text-mainTextColor">Enabled Modules</h2>
        <p className="mt-1 text-sm text-bodyText">
          Computed from your subscription plan plus any manual overrides.
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          {enabledModules.length > 0 ? (
            enabledModules.map((mod) => (
              <span
                key={mod}
                className="inline-flex items-center gap-1.5 rounded-lg border border-strokeColor bg-white px-3 py-1.5 text-sm font-medium text-mainTextColor"
              >
                <span className="h-1.5 w-1.5 rounded-full bg-p1/60" />
                {moduleLabelById.get(mod) ?? mod}
              </span>
            ))
          ) : (
            <p className="text-sm italic text-bodyText">No modules enabled</p>
          )}
        </div>
      </section>

      <section className="rounded-xl border border-strokeColor bg-white p-5 shadow-sm">
        <h2 className="text-lg font-semibold text-mainTextColor">
          Module Overrides (Waivers / Deals)
        </h2>
        <p className="mt-1 text-sm text-bodyText">
          Manually enabled modules beyond the subscription plan.
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          {moduleOverrides.length > 0 ? (
            moduleOverrides.map((mod) => (
              <span
                key={mod}
                className="inline-flex items-center gap-1.5 rounded-lg border border-strokeColor bg-white px-3 py-1.5 text-sm font-medium text-mainTextColor"
              >
                <span className="h-1.5 w-1.5 rounded-full bg-bodyText/35" />
                {moduleLabelById.get(mod) ?? mod}
              </span>
            ))
          ) : (
            <p className="text-sm italic text-bodyText">
              No manual overrides — all modules come from the subscription plan
            </p>
          )}
        </div>
      </section>

      {enabledModules.includes('multi_branch') && (
        <div className="rounded-xl border border-strokeColor bg-softBg p-4">
          <p className="text-sm font-semibold text-mainTextColor">Multi-Branch is enabled</p>
          <p className="mt-1 text-sm text-bodyText">
            <button
              type="button"
              onClick={openBranchManagement}
              className="font-medium text-p1 hover:underline"
            >
              Open G/L Setup
            </button>{' '}
            to configure multiple branches and branch switching.
          </p>
        </div>
      )}

      <section className="min-w-0">
        <h2 className="text-lg font-semibold text-mainTextColor">All Available Modules</h2>
        <p className="mt-1 text-sm text-bodyText">
          Full list of modules and their status for your company
          {planName ? (
            <>
              {' '}
              on the <span className="font-semibold text-mainTextColor">{planName}</span> plan
              {planBranches ? (
                <>
                  {' '}
                  <span>
                    (branches:{' '}
                    <span className="font-medium text-mainTextColor">{planBranches}</span>)
                  </span>
                </>
              ) : null}
            </>
          ) : null}
          .
        </p>

        <div className="mt-4 overflow-x-auto overscroll-x-contain rounded-xl border border-strokeColor bg-white">
          <table className="w-full min-w-[36rem] text-sm">
            <thead>
              <tr className="border-b border-strokeColor bg-softBg">
                <th className="min-w-[10rem] px-3 py-2.5 text-left font-semibold text-mainTextColor sm:px-5 sm:py-3">
                  Module
                </th>
                <th className="whitespace-nowrap px-3 py-2.5 text-left font-semibold text-mainTextColor sm:px-5 sm:py-3">
                  Category
                </th>
                <th className="min-w-[7.5rem] px-3 py-2.5 text-left font-semibold text-mainTextColor sm:px-5 sm:py-3">
                  Source
                </th>
                <th className="min-w-[8.5rem] px-3 py-2.5 text-center font-semibold text-mainTextColor sm:px-5 sm:py-3">
                  Status
                </th>
              </tr>
            </thead>
            <tbody>
              {modules.map((mod, idx) => {
                const isToggling = togglingModule === mod.identifier
                return (
                  <tr
                    key={mod.identifier}
                    className={cn(idx % 2 === 0 ? 'bg-white' : 'bg-softBg/50')}
                  >
                    <td className="px-3 py-2.5 align-top sm:px-5 sm:py-3">
                      <div className="min-w-0">
                        <span className="font-medium text-mainTextColor">{mod.display_name}</span>
                        <p className="mt-0.5 text-xs text-bodyText">{mod.description}</p>
                        {mod.identifier === 'item_tracking' && planBranches && (
                          <p className="mt-1 text-xs text-bodyText">
                            Same branch allowance as your package:{' '}
                            <span className="font-medium text-mainTextColor">{planBranches}</span>.
                            Tracking is maintained per branch.
                          </p>
                        )}
                        {mod.identifier === 'multi_branch' && (
                          <p className="mt-1 text-xs text-bodyText">
                            When included, your company can have up to{' '}
                            <span className="font-medium text-mainTextColor">3 branch locations</span>{' '}
                            (if your plan allows fewer, this raises the cap to 3). Configure branches
                            under G/L Setup, then use branch switching per location.
                          </p>
                        )}
                        {mod.identifier === 'stock_taking' &&
                          enabledModules.includes('multi_branch') && (
                            <p className="mt-1 text-xs text-bodyText">
                              With <span className="font-medium text-mainTextColor">Multi-Branch</span>{' '}
                              enabled, create physical inventory journals for each branch you have
                              access to.
                            </p>
                          )}
                      </div>
                    </td>
                    <td className="whitespace-nowrap px-3 py-2.5 align-top text-bodyText sm:px-5 sm:py-3">
                      {mod.category}
                    </td>
                    <td className="px-3 py-2.5 align-top sm:px-5 sm:py-3">
                      {mod.from_plan && mod.from_override ? (
                        <span className="whitespace-nowrap text-xs text-bodyText">Plan + Trial</span>
                      ) : mod.from_plan ? (
                        <span className="whitespace-nowrap text-xs text-bodyText">
                          Subscription Plan
                        </span>
                      ) : mod.from_override ? (
                        <span className="text-xs text-bodyText">
                          {isTrial ? 'Trial (enabled by you)' : 'Manual Override'}
                        </span>
                      ) : (
                        <span className="text-xs text-gray-400">—</span>
                      )}
                    </td>
                    <td className="px-3 py-2.5 text-center align-top sm:px-5 sm:py-3">
                      <ModuleStatusCell
                        mod={mod}
                        isTrial={isTrial}
                        allowManualModuleToggle={allowManualModuleToggle}
                        toggling={isToggling}
                        onToggle={handleToggleModule}
                      />
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
