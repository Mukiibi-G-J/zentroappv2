import api from '@/lib/api'
import type { UserSetup } from '@/types/userSetup'

export async function fetchMyUserSetup(): Promise<UserSetup> {
  const res = await api.get<UserSetup>('/api/user-setup/my-setup/')
  return res.data
}
