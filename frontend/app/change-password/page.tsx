import type { Metadata } from 'next'
import { ChangePasswordPage } from '@/components/auth/ChangePasswordPage'

export const metadata: Metadata = {
  title: 'Change password | ZentroApp',
  description: 'Set a new password to continue using ZentroApp.',
}

export default function ChangePasswordRoute() {
  return <ChangePasswordPage />
}
