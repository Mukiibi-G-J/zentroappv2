import publicApi from '@/lib/publicApi'
import type { AddOn, PlanComparisonPlan } from '@/types/pricing'

export async function getPricingPlansLanding(): Promise<PlanComparisonPlan[]> {
  const { data } = await publicApi.get<PlanComparisonPlan[]>('/api/company/pricing-plans-v2/')
  return data
}

export async function getAddOns(): Promise<AddOn[]> {
  try {
    const { data } = await publicApi.get<AddOn[]>('/api/company/add-ons/')
    return data
  } catch {
    return []
  }
}

export async function sendContactEmail(payload: {
  name: string
  email: string
  phone?: string
  message: string
}): Promise<void> {
  await publicApi.post('/api/auth/send-contact-email/', payload)
}
