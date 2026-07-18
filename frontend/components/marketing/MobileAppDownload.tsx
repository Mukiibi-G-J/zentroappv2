import { FaAndroid, FaApple, FaDownload } from 'react-icons/fa'
import { ANDROID_APK_DOWNLOAD_URL } from '@/constants/mobileApp'

type Variant = 'nav' | 'navDark' | 'featured' | 'footer' | 'menu'

interface MobileAppDownloadProps {
  variant?: Variant
  className?: string
  onNavigate?: () => void
}

function IosComingSoon({ variant }: { variant: Variant }) {
  if (variant === 'nav' || variant === 'navDark') {
    const isDark = variant === 'navDark'
    return (
      <span
        className={`inline-flex items-center gap-1.5 text-sm font-medium px-3 py-2 rounded-lg cursor-not-allowed ${
          isDark
            ? 'text-white/50 border border-white/15'
            : 'text-gray-400 border border-gray-200 bg-gray-50'
        }`}
        title="iOS app coming soon"
      >
        <FaApple className="text-xs" />
        iOS soon
      </span>
    )
  }

  if (variant === 'menu') {
    return (
      <span className="flex items-center gap-2 px-3 py-2.5 rounded-lg font-medium text-gray-400 bg-gray-50 border border-gray-100 cursor-not-allowed">
        <FaApple className="text-sm" />
        iOS — Coming soon
      </span>
    )
  }

  if (variant === 'footer') {
    return (
      <span className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-gray-800/60 text-gray-500 text-xs font-medium border border-gray-700 cursor-not-allowed">
        <FaApple className="text-xs" />
        iOS — Coming soon
      </span>
    )
  }

  return (
    <span className="inline-flex items-center justify-center gap-2 px-6 py-3.5 rounded-xl border border-dashed border-gray-300 text-gray-400 font-medium cursor-not-allowed">
      <FaApple className="text-sm" />
      iOS — Coming soon
    </span>
  )
}

function AndroidDownload({
  variant,
  onNavigate,
}: {
  variant: Variant
  onNavigate?: () => void
}) {
  const handleClick = () => onNavigate?.()

  if (variant === 'nav' || variant === 'navDark') {
    const isDark = variant === 'navDark'
    return (
      <a
        href={ANDROID_APK_DOWNLOAD_URL}
        onClick={handleClick}
        className={`inline-flex items-center gap-1.5 text-sm font-medium px-3 py-2 rounded-lg transition-colors cursor-pointer ${
          isDark
            ? 'text-white/90 hover:text-white hover:bg-white/10 bg-white/5 border border-white/20'
            : 'text-green-700 hover:text-green-800 hover:bg-green-50 bg-green-50/80 border border-green-200'
        }`}
      >
        <FaDownload className="text-xs" />
        Android
      </a>
    )
  }

  if (variant === 'menu') {
    return (
      <a
        href={ANDROID_APK_DOWNLOAD_URL}
        onClick={handleClick}
        className="flex items-center gap-2 px-3 py-2.5 bg-green-50 text-green-700 rounded-lg font-medium hover:bg-green-100 transition-colors border border-green-100"
      >
        <FaDownload className="text-sm" />
        Download Android App
      </a>
    )
  }

  if (variant === 'footer') {
    return (
      <a
        href={ANDROID_APK_DOWNLOAD_URL}
        className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-gray-800 text-gray-300 text-xs font-medium hover:bg-gray-700 hover:text-white transition-colors cursor-pointer"
      >
        <FaAndroid className="text-xs" />
        Android — Download
      </a>
    )
  }

  return (
    <a
      href={ANDROID_APK_DOWNLOAD_URL}
      className="inline-flex items-center justify-center gap-2 px-6 py-3.5 rounded-xl bg-gray-900 text-white font-semibold hover:bg-gray-800 transition-colors cursor-pointer"
    >
      <FaDownload className="text-sm" />
      Download Android APK
    </a>
  )
}

export function MobileAppDownload({
  variant = 'featured',
  className = '',
  onNavigate,
}: MobileAppDownloadProps) {
  const layout =
    variant === 'menu'
      ? 'flex flex-col gap-2'
      : variant === 'featured'
        ? 'flex flex-col sm:flex-row gap-3 sm:gap-4'
        : 'inline-flex flex-wrap items-center gap-2'

  return (
    <div className={`${layout} ${className}`.trim()}>
      <AndroidDownload variant={variant} onNavigate={onNavigate} />
      <IosComingSoon variant={variant} />
    </div>
  )
}
