import type { Metadata } from 'next'
import { ResetPasswordPage } from '@/components/auth/ResetPasswordPage'

export const metadata: Metadata = {
  title: 'Reset Password — ZentroApp',
  description: 'Set a new password for your ZentroApp account.',
}

export default function ResetPasswordRoute() {
  return <ResetPasswordPage />
}
