'use client'

import { Suspense } from 'react'
import CompanyModulesPanel from '@/components/company/CompanyModulesPanel'
import { Loader2 } from 'lucide-react'

function SettingsFallback() {
  return (
    <div className="flex flex-1 min-h-0 items-center justify-center">
      <Loader2 className="h-8 w-8 animate-spin text-p1" />
    </div>
  )
}

export default function CompanySettingsPage() {
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <Suspense fallback={<SettingsFallback />}>
        <CompanyModulesPanel />
      </Suspense>
    </div>
  )
}
