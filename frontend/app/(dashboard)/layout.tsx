import { QueryProvider } from '@/context/QueryProvider'
import { SessionProvider } from '@/context/SessionContext'
import { BranchProvider } from '@/context/BranchContext'
import { DashboardLayout } from '@/components/layout/DashboardLayout'

export default function DashboardRootLayout({ children }: { children: React.ReactNode }) {
  return (
    <QueryProvider>
      <SessionProvider>
        <BranchProvider>
          <DashboardLayout>{children}</DashboardLayout>
        </BranchProvider>
      </SessionProvider>
    </QueryProvider>
  )
}
