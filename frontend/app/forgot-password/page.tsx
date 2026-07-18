import type { Metadata } from 'next'
import { ForgotPasswordPage } from '@/components/auth/ForgotPasswordPage'

export const metadata: Metadata = {
  title: 'Forgot Password — ZentroApp',
  description: 'Reset your ZentroApp account password.',
}

export default function ForgotPasswordRoute() {
  return <ForgotPasswordPage />
}
