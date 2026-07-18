import type { Metadata } from 'next'
import { SignupWizardPage } from '@/components/auth/SignupWizardPage'

export const metadata: Metadata = {
  title: 'Sign up | ZentroApp',
  description: 'Create your Zentro workspace and start your free trial.',
}

export default function SignupPage() {
  return <SignupWizardPage />
}
