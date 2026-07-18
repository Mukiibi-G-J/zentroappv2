'use client'

import { useRef } from 'react'
import {
  motion,
  useInView,
  useReducedMotion,
  useScroll,
  useTransform,
} from 'framer-motion'

const DASHBOARD_SCREENSHOT = '/screenshots/dashboard.png'
const FALLBACK_IMAGE =
  'https://images.unsplash.com/photo-1551288049-bebda4e38f71?auto=format&fit=crop&w=1400&q=80'

function BrowserMockup({ src, alt }: { src: string; alt: string }) {
  const ref = useRef<HTMLDivElement>(null)
  const reduced = useReducedMotion()
  const inView = useInView(ref, { once: true, margin: '-80px' })
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ['start end', 'end start'],
  })
  const y = useTransform(scrollYProgress, [0, 1], reduced ? [0, 0] : [48, -24])
  const scale = useTransform(
    scrollYProgress,
    [0, 0.5, 1],
    reduced ? [1, 1, 1] : [0.96, 1, 0.98],
  )

  return (
    <motion.div
      ref={ref}
      style={{ y, scale }}
      initial={reduced ? false : { opacity: 0, y: 40 }}
      animate={inView ? { opacity: 1, y: 0 } : undefined}
      transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
      className="relative mx-auto max-w-5xl"
    >
      <div
        aria-hidden
        className="pointer-events-none absolute -inset-x-8 -bottom-8 h-32 bg-gradient-to-t from-blue-600/20 to-transparent blur-3xl"
      />

      <div className="relative overflow-hidden rounded-2xl border border-gray-200/80 bg-white shadow-[0_24px_80px_-12px_rgba(15,23,42,0.18)]">
        <div className="flex items-center gap-3 border-b border-gray-100 bg-gray-50/90 px-4 py-3">
          <div className="flex gap-1.5" aria-hidden>
            <span className="h-2.5 w-2.5 rounded-full bg-[#FF5F57]" />
            <span className="h-2.5 w-2.5 rounded-full bg-[#FEBC2E]" />
            <span className="h-2.5 w-2.5 rounded-full bg-[#28C840]" />
          </div>
          <div className="mx-auto flex h-7 w-full max-w-md items-center justify-center rounded-md border border-gray-200 bg-white px-3 text-xs text-gray-400">
            app.zentroapp.app/dashboard
          </div>
        </div>

        <img
          src={src}
          alt={alt}
          width={1400}
          height={720}
          loading="lazy"
          className="block w-full object-cover object-left-top"
          draggable={false}
          onError={(e) => {
            e.currentTarget.src = FALLBACK_IMAGE
          }}
        />
      </div>
    </motion.div>
  )
}

export function ProductScrollShowcase() {
  const headerRef = useRef<HTMLDivElement>(null)
  const inView = useInView(headerRef, { once: true, margin: '-60px' })
  const reduced = useReducedMotion()

  return (
    <section className="relative overflow-hidden bg-white pb-24 pt-20 lg:pb-32 lg:pt-28">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-40 bg-gradient-to-b from-[#0B1120] to-white"
      />

      <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <motion.div
          ref={headerRef}
          initial={reduced ? false : { opacity: 0, y: 24 }}
          animate={inView ? { opacity: 1, y: 0 } : undefined}
          transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1] }}
          className="mx-auto mb-14 max-w-2xl text-center lg:mb-16"
        >
          <span className="mb-4 inline-block rounded-full bg-blue-600/10 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-blue-700">
            Analytics &amp; reporting
          </span>
          <h2 className="mb-4 text-4xl font-extrabold tracking-tight text-gray-900 sm:text-5xl">
            One dashboard for your entire operation
          </h2>
          <p className="text-lg leading-relaxed text-gray-600">
            Monitor sales, stock, and branch performance in real time, without
            switching tools or waiting on end-of-day reports.
          </p>
        </motion.div>

        <BrowserMockup
          src={DASHBOARD_SCREENSHOT}
          alt="ZentroApp dashboard showing sales, inventory, and branch analytics"
        />
      </div>
    </section>
  )
}
