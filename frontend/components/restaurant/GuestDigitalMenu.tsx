'use client'

import { useEffect, useMemo, useState } from 'react'
import {
  fetchPublicDigitalMenu,
  formatGuestMenuPrice,
  resolveGuestMenuImageUrl,
  type PublicDigitalMenu,
} from '@/services/guestMenu'
import { HiOutlinePhone, HiOutlineSparkles } from 'react-icons/hi'
import { FaFacebookF, FaInstagram, FaTiktok } from 'react-icons/fa'
import { FaXTwitter } from 'react-icons/fa6'

function SocialIcon({ network }: { network: string }) {
  const n = network.toLowerCase()
  if (n === 'facebook') return <FaFacebookF className="w-4 h-4" />
  if (n === 'instagram') return <FaInstagram className="w-4 h-4" />
  if (n === 'tiktok') return <FaTiktok className="w-4 h-4" />
  if (n === 'x' || n === 'twitter') return <FaXTwitter className="w-4 h-4" />
  return null
}

export default function GuestDigitalMenu({ slug = 'main' }: { slug?: string }) {
  const [menu, setMenu] = useState<PublicDigitalMenu | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [activeSection, setActiveSection] = useState(0)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      setLoading(true)
      setError(null)
      try {
        const data = await fetchPublicDigitalMenu(slug)
        if (!cancelled) {
          setMenu(data)
          setActiveSection(0)
        }
      } catch (e: unknown) {
        if (!cancelled) {
          const msg =
            e instanceof Error
              ? e.message
              : 'Could not load menu. Check your link or try again later.'
          setError(msg)
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [slug])

  const primaryPhone = menu?.phones?.[0]
  const brandPrimary = menu?.brand_primary || '#3B1614'
  const brandAccent = menu?.brand_accent || '#E86E25'
  const logoUrl = menu ? resolveGuestMenuImageUrl(menu.logo_url) : ''
  const coverUrl = menu ? resolveGuestMenuImageUrl(menu.cover_image_url) : ''

  const sectionTabs = useMemo(
    () => menu?.sections?.map((s) => s.name) ?? [],
    [menu],
  )

  if (loading) {
    return (
      <div
        className="min-h-screen flex items-center justify-center"
        style={{ backgroundColor: brandPrimary }}
      >
        <div className="text-white/90 text-sm animate-pulse">Loading menu…</div>
      </div>
    )
  }

  if (error || !menu) {
    return (
      <div
        className="min-h-screen flex flex-col items-center justify-center px-6 text-center"
        style={{ backgroundColor: '#3B1614' }}
      >
        <p className="text-white text-lg font-semibold mb-2">Menu unavailable</p>
        <p className="text-white/80 text-sm max-w-md">{error || 'Not found'}</p>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-[#faf8f6] text-[#1a1a1a]">
      <header
        className="relative overflow-hidden px-4 pt-8 pb-10 sm:px-6"
        style={{
          background: `linear-gradient(160deg, ${brandPrimary} 0%, ${brandPrimary}dd 45%, ${brandAccent}22 100%)`,
        }}
      >
        <div className="max-w-lg mx-auto text-center text-white">
          {logoUrl ? (
            <img
              src={logoUrl}
              alt={menu.title}
              className="mx-auto mb-4 h-24 w-auto max-w-[220px] object-contain drop-shadow-lg"
            />
          ) : (
            <div
              className="inline-flex items-center justify-center w-16 h-16 rounded-2xl mb-4 shadow-lg"
              style={{ backgroundColor: brandAccent }}
              aria-hidden
            >
              <span className="text-2xl font-black tracking-tight">SC</span>
            </div>
          )}
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight leading-tight">
            {menu.title}
          </h1>
          {menu.tagline ? (
            <p className="mt-2 text-sm sm:text-base text-white/85 font-medium">
              {menu.tagline}
            </p>
          ) : null}
          {primaryPhone ? (
            <a
              href={`tel:${primaryPhone.replace(/\s/g, '')}`}
              className="mt-4 inline-flex items-center gap-2 rounded-full bg-white/15 backdrop-blur px-4 py-2 text-sm font-semibold hover:bg-white/25 transition-colors"
            >
              <HiOutlinePhone className="w-4 h-4" />
              {primaryPhone}
            </a>
          ) : null}
        </div>
      </header>

      {coverUrl ? (
        <div className="max-w-lg mx-auto px-4 -mt-4 relative z-10">
          <img
            src={coverUrl}
            alt={`${menu.title} menu`}
            className="w-full rounded-2xl shadow-lg border border-white/80 object-cover"
          />
        </div>
      ) : null}

      {sectionTabs.length > 1 ? (
        <div className="sticky top-0 z-20 bg-white/95 backdrop-blur border-b border-stone-200 shadow-sm">
          <div className="max-w-lg mx-auto flex gap-1 overflow-x-auto px-2 py-2 [scrollbar-width:none]">
            {menu.sections.map((section, idx) => (
              <button
                key={section.name}
                type="button"
                onClick={() => setActiveSection(idx)}
                className={`shrink-0 px-3 py-1.5 rounded-full text-xs font-bold uppercase tracking-wide transition-colors ${
                  activeSection === idx
                    ? 'text-stone-900 shadow-sm'
                    : 'text-stone-500 hover:text-stone-800'
                }`}
                style={
                  activeSection === idx
                    ? { backgroundColor: section.accent_color || '#FACC15' }
                    : undefined
                }
              >
                {section.name}
              </button>
            ))}
          </div>
        </div>
      ) : null}

      <main
        className={`max-w-lg mx-auto px-4 py-6 pb-28 space-y-8 ${coverUrl ? 'pt-6' : ''}`}
      >
        {menu.sections.length === 0 ? (
          <p className="text-center text-stone-500 text-sm">No items published yet.</p>
        ) : (
          menu.sections.map((section, idx) => {
            if (sectionTabs.length > 1 && idx !== activeSection) return null
            const sectionImage = resolveGuestMenuImageUrl(section.image_url)
            return (
              <section key={section.name}>
                {sectionImage ? (
                  <div className="mb-4 overflow-hidden rounded-2xl shadow-md border border-stone-100">
                    <img
                      src={sectionImage}
                      alt={section.name}
                      className="w-full h-auto object-cover"
                    />
                  </div>
                ) : null}
                <div
                  className="inline-block px-4 py-1.5 rounded-sm font-black text-sm uppercase tracking-wider text-stone-900 mb-4 shadow-sm"
                  style={{ backgroundColor: section.accent_color || '#FACC15' }}
                >
                  {section.name}
                </div>
                {section.subtitle ? (
                  <p className="text-xs text-stone-500 mb-3 -mt-2">{section.subtitle}</p>
                ) : null}
                <ul className="space-y-3">
                  {section.lines.map((line) => (
                    <li
                      key={line.name}
                      className="flex items-start justify-between gap-3 border-b border-stone-100 pb-3"
                    >
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-1.5">
                          <span className="font-bold text-sm text-stone-900 leading-snug">
                            {line.name}
                          </span>
                          {line.is_featured ? (
                            <HiOutlineSparkles
                              className="w-3.5 h-3.5 shrink-0"
                              style={{ color: brandAccent }}
                              aria-label="Featured"
                            />
                          ) : null}
                        </div>
                        {line.description ? (
                          <p className="text-[11px] text-stone-500 mt-0.5 leading-relaxed">
                            {line.description}
                          </p>
                        ) : null}
                      </div>
                      <span
                        className="shrink-0 text-sm font-extrabold tabular-nums whitespace-nowrap"
                        style={{ color: brandPrimary }}
                      >
                        {formatGuestMenuPrice(
                          line.price,
                          menu.currency_code,
                          line.price_note,
                        )}
                      </span>
                    </li>
                  ))}
                </ul>
              </section>
            )
          })
        )}

        {menu.gallery_images?.length ? (
          <section className="space-y-3 pt-2">
            <h2 className="text-xs font-bold uppercase tracking-widest text-stone-500 text-center">
              From our kitchen
            </h2>
            <div className="grid grid-cols-1 gap-3">
              {menu.gallery_images.map((src) => {
                const url = resolveGuestMenuImageUrl(src)
                if (!url) return null
                return (
                  <img
                    key={src}
                    src={url}
                    alt=""
                    className="w-full rounded-2xl shadow-md object-cover"
                  />
                )
              })}
            </div>
          </section>
        ) : null}
      </main>

      <footer
        className="fixed bottom-0 inset-x-0 border-t border-stone-200 bg-white/95 backdrop-blur px-4 py-3"
        style={{ borderTopColor: `${brandAccent}44` }}
      >
        <div className="max-w-lg mx-auto flex flex-col items-center gap-2">
          {Object.entries(menu.social_links || {}).some(([, v]) => v) ? (
            <div className="flex items-center gap-3">
              {Object.entries(menu.social_links).map(([network, url]) =>
                url ? (
                  <a
                    key={network}
                    href={url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="w-9 h-9 rounded-full flex items-center justify-center text-white"
                    style={{ backgroundColor: brandPrimary }}
                    aria-label={network}
                  >
                    <SocialIcon network={network} />
                  </a>
                ) : null,
              )}
            </div>
          ) : null}
          {primaryPhone ? (
            <a
              href={`tel:${primaryPhone.replace(/\s/g, '')}`}
              className="w-full max-w-sm text-center rounded-xl py-3 text-sm font-bold text-white shadow-md active:scale-[0.99] transition-transform"
              style={{ backgroundColor: brandAccent }}
            >
              Call to order · {primaryPhone}
            </a>
          ) : (
            <p className="text-xs font-bold uppercase tracking-widest text-stone-500">
              Order at the counter
            </p>
          )}
        </div>
      </footer>
    </div>
  )
}
