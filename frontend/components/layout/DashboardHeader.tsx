'use client'

import { useState, useRef, useEffect, useMemo } from 'react'
import { useRouter } from 'next/navigation'
import { Menu, Bell, User, LogOut, Building2, MapPin } from 'lucide-react'
import { clearAccessTokenCookie } from '@/lib/api'
import { clearStoredSession } from '@/lib/session'
import { clearBranchSession } from '@/lib/branchSession'
import { useSession } from '@/context/SessionContext'
import { useBranch } from '@/context/BranchContext'
import { usePageNavigation } from '@/hooks/usePageNavigation'
import { resolveProfileAvatarSrc } from '@/lib/profileAvatar'
import { cn } from '@/lib/utils'
import { GlobalSearch } from './GlobalSearch'

interface DashboardHeaderProps {
  title?: string
  onMenuToggle?: () => void
  className?: string
}

const PROFILE_PAGE = 'UserSettingsCard'
const COMPANY_PAGE = 'CompanyCard'

function UserAvatar({
  src,
  alt,
  size = 32,
  className,
}: {
  src: string
  alt: string
  size?: number
  className?: string
}) {
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={src}
      alt={alt}
      width={size}
      height={size}
      className={cn('rounded-full object-cover bg-softBg shrink-0', className)}
      style={{ width: size, height: size }}
    />
  )
}

export function DashboardHeader({ title, onMenuToggle, className }: DashboardHeaderProps) {
  const router = useRouter()
  const { session, isReady, clearSession } = useSession()
  const { activeBranch, canSwitchBranch, enableMultipleBranches, openBranchPicker } =
    useBranch()
  const { navigateToPageName } = usePageNavigation()
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setUserMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  const handleLogout = () => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    clearAccessTokenCookie()
    clearBranchSession()
    clearSession()
    clearStoredSession()
    router.push('/login')
  }

  // Session comes from localStorage after mount — keep SSR/hydrate placeholders
  // identical so we don't flash mismatched text (e.g. "User" vs real name).
  const showSession = isReady
  const showBranchLabel =
    showSession && enableMultipleBranches && (activeBranch?.code || canSwitchBranch)
  const showSwitchBranch =
    showSession && enableMultipleBranches && canSwitchBranch

  const displayName =
    showSession && session?.user.fullName ? session.user.fullName : 'User'
  const displayEmail = showSession ? session?.user.email || '' : ''
  const displayRole = showSession
    ? session?.profile?.description || session?.user.role || 'User'
    : 'User'

  const avatarSrc = useMemo(
    () =>
      resolveProfileAvatarSrc(
        showSession ? session?.user.avatarUrl : null,
        displayEmail || displayName,
        64,
      ),
    [showSession, session?.user.avatarUrl, displayEmail, displayName],
  )

  const openPage = async (pageName: string) => {
    setUserMenuOpen(false)
    await navigateToPageName(pageName)
  }

  return (
    <header
      className={cn(
        'flex h-16 items-center justify-between bg-white border-b border-strokeColor px-6',
        className,
      )}
      role="banner"
    >
      <div className="flex items-center gap-4">
        <button
          onClick={onMenuToggle}
          className="p-2 rounded-lg hover:bg-softBg transition-colors lg:hidden"
          aria-label="Toggle menu"
        >
          <Menu className="w-5 h-5 text-bodyText" />
        </button>
        {title && (
          <h1 className="text-xl font-semibold text-mainTextColor">{title}</h1>
        )}
      </div>

      <div className="mx-6 flex-1 max-w-md">
        <GlobalSearch />
      </div>

      <div className="flex items-center gap-3">
        <button
          className="relative p-2 rounded-lg hover:bg-softBg transition-colors"
          aria-label="Notifications"
        >
          <Bell className="w-5 h-5 text-bodyText" />
          <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full" />
        </button>

        <div className="relative" ref={menuRef}>
          <button
            className="flex items-center gap-3 p-2 rounded-lg hover:bg-softBg transition-colors"
            onClick={() => setUserMenuOpen(!userMenuOpen)}
            aria-label="User menu"
            aria-expanded={userMenuOpen}
          >
            <div className="text-right hidden sm:block min-w-0">
              <p
                className="text-sm font-semibold text-mainTextColor truncate"
                suppressHydrationWarning
              >
                {displayName}
              </p>
              <p
                className="text-xs text-bodyText capitalize truncate"
                suppressHydrationWarning
              >
                {displayRole}
              </p>
              {showBranchLabel && activeBranch?.code && (
                <p className="text-xs text-p1 truncate max-w-[160px] flex items-center justify-end gap-1">
                  <MapPin className="w-3 h-3 shrink-0" aria-hidden />
                  {activeBranch.code}
                </p>
              )}
            </div>
            <UserAvatar src={avatarSrc} alt={displayName} size={32} />
          </button>

          {userMenuOpen && (
            <div className="absolute right-0 mt-2 w-64 bg-white border border-strokeColor rounded-lg shadow-lg z-50 overflow-hidden">
              <div className="px-4 py-3 border-b border-strokeColor">
                <div className="flex items-start gap-3">
                  <UserAvatar src={avatarSrc} alt={displayName} size={40} />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-bold text-mainTextColor truncate">{displayName}</p>
                    <p className="text-xs text-bodyText truncate">{displayEmail}</p>
                    {showBranchLabel && activeBranch?.code && (
                      <p className="text-xs text-p1 truncate mt-1 flex items-center gap-1">
                        <MapPin className="w-3.5 h-3.5 shrink-0" aria-hidden />
                        Branch: {activeBranch.code}
                      </p>
                    )}
                  </div>
                </div>
              </div>

              <div className="py-1">
                {showSwitchBranch && (
                  <button
                    onClick={() => {
                      setUserMenuOpen(false)
                      openBranchPicker()
                    }}
                    className="flex items-center gap-3 w-full px-4 py-2 text-sm text-mainTextColor hover:bg-softBg transition-colors"
                  >
                    <MapPin className="w-4 h-4 opacity-60" />
                    Switch branch
                  </button>
                )}
                <button
                  onClick={() => openPage(PROFILE_PAGE)}
                  className="flex items-center gap-3 w-full px-4 py-2 text-sm text-mainTextColor hover:bg-softBg transition-colors"
                >
                  <User className="w-4 h-4 opacity-60" />
                  Profile
                </button>
                <button
                  onClick={() => openPage(COMPANY_PAGE)}
                  className="flex items-center gap-3 w-full px-4 py-2 text-sm text-mainTextColor hover:bg-softBg transition-colors"
                >
                  <Building2 className="w-4 h-4 opacity-60" />
                  Company
                </button>
                <div className="border-t border-strokeColor my-1" />
                <button
                  onClick={handleLogout}
                  className="flex items-center gap-3 w-full px-4 py-2 text-sm text-red-600 hover:bg-red-50 transition-colors"
                >
                  <LogOut className="w-4 h-4 opacity-60" />
                  Sign Out
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
