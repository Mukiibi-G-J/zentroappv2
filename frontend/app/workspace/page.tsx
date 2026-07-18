import type { Metadata } from 'next'
import { WorkspaceGatewayPage } from '@/components/auth/WorkspaceGatewayPage'

export const metadata: Metadata = {
  title: 'Find your workspace | ZentroApp',
  description: 'Enter your company name to open your ZentroApp workspace and sign in.',
  robots: { index: false, follow: false },
}

export default function WorkspacePage() {
  return <WorkspaceGatewayPage />
}
