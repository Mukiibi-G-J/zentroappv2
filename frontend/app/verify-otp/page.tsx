import type { Metadata } from 'next'
import { VerifyOtpPage } from '@/components/auth/VerifyOtpPage'

export const metadata: Metadata = {
  title: 'Verify account | ZentroApp',
  description: 'Verify your Zentro account with the code we sent you.',
}

export default function VerifyOtpRoute() {
  return <VerifyOtpPage />
}
