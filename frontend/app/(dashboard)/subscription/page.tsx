'use client'

import { Suspense } from 'react'
import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import { ArrowLeft } from 'lucide-react'

function SubscriptionContent() {
  const searchParams = useSearchParams()
  const intent = searchParams.get('intent')
  const isPlanChange = intent === 'plan-change'

  return (
    <div className="mx-auto max-w-3xl space-y-6 p-6">
      <Link
        href="/dashboard"
        className="inline-flex items-center gap-2 text-sm font-medium text-p1 hover:underline"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to dashboard
      </Link>

      <div className="rounded-xl border border-strokeColor bg-white p-6 shadow-sm">
        <h1 className="text-2xl font-bold text-mainTextColor">
          {isPlanChange ? 'Change plan' : 'Pay upfront months'}
        </h1>
        <p className="mt-2 text-sm text-bodyText">
          {isPlanChange
            ? 'Select a new plan and pay via mobile money. We verify your payment before your subscription tier updates.'
            : 'Extend your current plan without switching tier. Pay via mobile money; we verify your payment before your period is extended.'}
        </p>
        <p className="mt-4 rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-950">
          The full subscription checkout is being wired into this app. For now, contact support or
          use the legacy subscription page if you need to complete payment immediately.
        </p>
      </div>
    </div>
  )
}

export default function SubscriptionPage() {
  return (
    <Suspense fallback={<div className="h-32 animate-pulse rounded-xl bg-gray-100 m-6" />}>
      <SubscriptionContent />
    </Suspense>
  )
}
