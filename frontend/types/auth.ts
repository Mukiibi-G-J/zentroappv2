export type OtpChannel = 'email' | 'sms' | 'both'

export type BranchScope = 'single' | 'all'

export interface BranchSummary {
  id: number
  code: string
  description: string
}

export interface AuthSessionBranchConfig {
  assignedBranch: BranchSummary | null
  enableMultipleBranches: boolean
  canSwitchBranch: boolean
}

export interface AuthSessionUser {
  id: number
  email: string
  fullName: string
  username: string
  role: string
  avatarUrl?: string | null
}

export interface AuthSessionProfile {
  code: string
  description: string
}

export interface AuthSessionCompany {
  name: string
  displayName: string
  logoUrl: string | null
  email: string
  phone: string
}

export interface AuthNavItem {
  name: string
  caption: string
  imageUrl: string
  targetPageName: string
  ribbonTab?: string
  /** When true, only show in the Zentro Desktop client — hide in web sidebar. */
  desktopOnly?: boolean
}

export interface AuthSession {
  user: AuthSessionUser
  profile: AuthSessionProfile | null
  company: AuthSessionCompany | null
  roleCentrePageId: number | null
  navItems: AuthNavItem[]
  branch?: AuthSessionBranchConfig
  /** From General Ledger Setup local currency (LCY). */
  localCurrencyCode?: string
  enabledModules?: string[]
  planName?: string | null
  planBranches?: string | null
  impersonation?: AuthImpersonation
}

export interface AuthImpersonation {
  active: boolean
  target: {
    id: number
    fullName: string
    username: string
    email: string
  }
  impersonator: {
    id: number
    username: string
  }
}
