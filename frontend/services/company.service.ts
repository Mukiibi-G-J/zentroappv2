import api from '@/lib/api'
import publicApi from '@/lib/publicApi'
import type { BranchSummary } from '@/types/auth'

export interface CompanyExistsResponse {
  is_existing: boolean
  message: string
  status: 'success' | 'error'
}

/** Public schema check — always hits the main API, not a tenant host. */
export async function checkCompanyExists(companyName: string): Promise<CompanyExistsResponse> {
  const { data } = await publicApi.post<CompanyExistsResponse>(
    '/api/company/check-company-exists/',
    { company_name: companyName.trim() },
  )
  return data
}

interface CompanyBranchRow {
  id: string | number
  code: string
  name?: string
}

function normalizeBranchRow(row: CompanyBranchRow): BranchSummary | null {
  const id = Number(row.id)
  const code = String(row.code ?? '').trim()
  if (!Number.isFinite(id) || !code) return null
  const description = String(row.name ?? row.code ?? '').trim() || code
  return { id, code, description }
}

/** Fallback when sales setup returns no branch_values. */
export async function fetchCompanyBranches(): Promise<BranchSummary[]> {
  const res = await api.get<CompanyBranchRow[]>('/api/company/branches/')
  const rows = Array.isArray(res.data) ? res.data : []
  return rows
    .map(normalizeBranchRow)
    .filter((b): b is BranchSummary => b !== null)
}

export interface CreateCompanyAccountPayload {
  companyName: string
  companyEmail: string
  companyPhone: string
  companyAddress: string
  companyCountry: string
  fullName: string
  password: string
  organization_size: string
  business_category: string
  business_objective: string
  companyCity?: string
  subscription: {
    plan: string
    price: number
    yearlyPrice: number
  }
}

export interface CreateCompanyAccountResponse {
  message: string
  task_id: string
  company_name: string
}

export interface TaskStatusResponse {
  state: string
  progress: number
  message: string
  status: string
  result?: {
    login_url?: string
    company_name?: string
    used_template_baseline?: boolean
    [key: string]: unknown
  }
  login_url?: string
  enqueued?: boolean
}

export async function createCompanyAccount(
  payload: CreateCompanyAccountPayload,
): Promise<CreateCompanyAccountResponse> {
  const { data } = await publicApi.post<CreateCompanyAccountResponse>(
    '/api/company/create-company-account/',
    payload,
  )
  return data
}

export async function getTaskStatus(taskId: string): Promise<TaskStatusResponse> {
  const { data } = await publicApi.get<TaskStatusResponse>(
    `/api/company/task-status/${taskId}/`,
  )
  return data
}

export async function uploadCompanyLogo(file: File): Promise<string | null> {
  const form = new FormData()
  form.append('logo', file)
  const res = await api.post<{ logo?: string; logoUrl?: string }>(
    '/api/company/upload-logo/',
    form,
    { headers: { 'Content-Type': 'multipart/form-data' } },
  )
  return res.data.logoUrl ?? res.data.logo ?? null
}

export interface CompanyModule {
  identifier: string
  display_name: string
  description: string
  icon: string
  category: string
  enabled: boolean
  from_plan: boolean
  from_override: boolean
}

export interface CompanyModulesResponse {
  modules: CompanyModule[]
  enabled_modules: string[]
  module_overrides: string[]
  plan_name: string | null
  plan_modules: string[]
  plan_branches?: string | null
  is_trial: boolean
  allow_manual_module_toggle: boolean
}

export interface ToggleModuleResponse {
  success: boolean
  enabled_modules: string[]
  module_overrides: string[]
  setup_ran?: boolean
}

export interface CurrencyOption {
  code: string
  name: string
  minor_units: number
}

export interface CompanyOverviewSettings {
  localCurrencyCode?: string
}

export interface CompanyOverviewResponse {
  company: {
    name: string
    displayName?: string
  }
  settings?: CompanyOverviewSettings
}

export async function getCompanyModules(): Promise<CompanyModulesResponse> {
  const { data } = await api.get<CompanyModulesResponse>('/api/company/modules/')
  return data
}

export async function toggleCompanyModule(
  moduleId: string,
  action: 'enable' | 'disable',
): Promise<ToggleModuleResponse> {
  const { data } = await api.post<ToggleModuleResponse>('/api/company/modules/toggle/', {
    module: moduleId,
    action,
  })
  return data
}

export async function getCompanyOverview(): Promise<CompanyOverviewResponse> {
  const { data } = await api.get<CompanyOverviewResponse>('/api/company/overview/')
  return data
}

export async function updateCompanyLocalCurrency(
  localCurrencyCode: string,
): Promise<{ settings?: CompanyOverviewSettings }> {
  const { data } = await api.put<{ settings?: CompanyOverviewSettings }>(
    '/api/company/update-info/',
    { localCurrencyCode },
  )
  return data
}

export async function listCurrencies(): Promise<CurrencyOption[]> {
  const { data } = await api.get<{ results: CurrencyOption[] }>('/api/financials/currencies/')
  return data.results ?? []
}
