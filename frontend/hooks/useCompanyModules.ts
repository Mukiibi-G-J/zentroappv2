'use client'

import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  getCompanyModules,
  toggleCompanyModule,
  type CompanyModulesResponse,
} from '@/services/company.service'

export const COMPANY_MODULES_QUERY_KEY = ['company-modules'] as const

export function useCompanyModules() {
  return useQuery({
    queryKey: COMPANY_MODULES_QUERY_KEY,
    queryFn: getCompanyModules,
    staleTime: 5 * 60 * 1000,
  })
}

export async function toggleModuleAndRefresh(
  queryClient: ReturnType<typeof useQueryClient>,
  moduleId: string,
  action: 'enable' | 'disable',
) {
  const result = await toggleCompanyModule(moduleId, action)
  queryClient.setQueryData<CompanyModulesResponse>(COMPANY_MODULES_QUERY_KEY, (prev) =>
    prev
      ? {
          ...prev,
          enabled_modules: result.enabled_modules,
          module_overrides: result.module_overrides,
          modules: prev.modules.map((mod) => ({
            ...mod,
            enabled: result.enabled_modules.includes(mod.identifier),
            from_override: result.module_overrides.includes(mod.identifier),
          })),
        }
      : prev,
  )
  await queryClient.invalidateQueries({ queryKey: COMPANY_MODULES_QUERY_KEY })
  return result
}
