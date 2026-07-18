import { FaApple, FaDesktop, FaDownload, FaWindows } from 'react-icons/fa'
import { DESKTOP_WINDOWS_DOWNLOAD_URL } from '@/constants/desktopApp'

type Variant = 'nav' | 'navDark' | 'featured' | 'footer' | 'menu'

interface DesktopAppDownloadProps {
  variant?: Variant
  className?: string
  onNavigate?: () => void
}

function MacComingSoon({ variant }: { variant: Variant }) {
  if (variant === 'nav' || variant === 'navDark') {
    const isDark = variant === 'navDark'
    return (
      <span
        className={`inline-flex items-center gap-1.5 text-sm font-medium px-3 py-2 rounded-lg cursor-not-allowed ${
          isDark
            ? 'text-white/50 border border-white/15'
            : 'text-gray-400 border border-gray-200 bg-gray-50'
        }`}
        title="macOS app coming soon"
      >
        <FaApple className="text-xs" />
        Mac soon
      </span>
    )
  }

  if (variant === 'menu') {
    return (
      <span className="flex items-center gap-2 px-3 py-2.5 rounded-lg font-medium text-gray-400 bg-gray-50 border border-gray-100 cursor-not-allowed">
        <FaApple className="text-sm" />
        macOS — Coming soon
      </span>
    )
  }

  if (variant === 'footer') {
    return (
      <span className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-gray-800/60 text-gray-500 text-xs font-medium border border-gray-700 cursor-not-allowed">
        <FaApple className="text-xs" />
        macOS — Coming soon
      </span>
    )
  }

  return (
    <span className="inline-flex items-center justify-center gap-2 px-6 py-3.5 rounded-xl border border-dashed border-gray-300 text-gray-400 font-medium cursor-not-allowed">
      <FaApple className="text-sm" />
      macOS — Coming soon
    </span>
  )
}

function WindowsDownload({
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
        href={DESKTOP_WINDOWS_DOWNLOAD_URL}
        onClick={handleClick}
        className={`inline-flex items-center gap-1.5 text-sm font-medium px-3 py-2 rounded-lg transition-colors cursor-pointer ${
          isDark
            ? 'text-white/90 hover:text-white hover:bg-white/10 bg-white/5 border border-white/20'
            : 'text-slate-700 hover:text-slate-900 hover:bg-slate-50 bg-slate-50/80 border border-slate-200'
        }`}
      >
        <FaWindows className="text-xs" />
        Windows
      </a>
    )
  }

  if (variant === 'menu') {
    return (
      <a
        href={DESKTOP_WINDOWS_DOWNLOAD_URL}
        onClick={handleClick}
        className="flex items-center gap-2 px-3 py-2.5 bg-slate-50 text-slate-800 rounded-lg font-medium hover:bg-slate-100 transition-colors border border-slate-200"
      >
        <FaDesktop className="text-sm" />
        Download Windows App
      </a>
    )
  }

  if (variant === 'footer') {
    return (
      <a
        href={DESKTOP_WINDOWS_DOWNLOAD_URL}
        className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-gray-800 text-gray-300 text-xs font-medium hover:bg-gray-700 hover:text-white transition-colors cursor-pointer"
      >
        <FaWindows className="text-xs" />
        Windows — Download
      </a>
    )
  }

  return (
    <a
      href={DESKTOP_WINDOWS_DOWNLOAD_URL}
      className="inline-flex items-center justify-center gap-2 px-6 py-3.5 rounded-xl bg-slate-900 text-white font-semibold hover:bg-slate-800 transition-colors cursor-pointer"
    >
      <FaDownload className="text-sm" />
      Download for Windows
    </a>
  )
}

export function DesktopAppDownload({
  variant = 'featured',
  className = '',
  onNavigate,
}: DesktopAppDownloadProps) {
  const layout =
    variant === 'menu'
      ? 'flex flex-col gap-2'
      : variant === 'featured'
        ? 'flex flex-col sm:flex-row gap-3 sm:gap-4'
        : 'inline-flex flex-wrap items-center gap-2'

  return (
    <div className={`${layout} ${className}`.trim()}>
      <WindowsDownload variant={variant} onNavigate={onNavigate} />
      {variant !== 'nav' && variant !== 'navDark' ? (
        <MacComingSoon variant={variant} />
      ) : null}
    </div>
  )
}
