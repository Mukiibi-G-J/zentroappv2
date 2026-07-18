import publicApi from '@/lib/publicApi'

export interface CompanyValidationResponse {
  isValid: boolean
  message: string
  errors?: string[]
}

export interface BusinessObjective {
  id: number
  description: string
}

export interface BusinessCategory {
  id: number
  name: string
}

export interface OnboardingData {
  business_objectives: BusinessObjective[]
  business_categories: BusinessCategory[]
}

export async function validateCompanyName(companyName: string): Promise<CompanyValidationResponse> {
  const { data } = await publicApi.post<CompanyValidationResponse>(
    '/api/company/validate-company-name/',
    { company_name: companyName.trim() },
  )
  return data
}

export async function getOnboardingData(): Promise<OnboardingData> {
  const { data } = await publicApi.get<OnboardingData>('/api/home/on-boarding/')
  return data
}
