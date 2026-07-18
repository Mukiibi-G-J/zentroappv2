import type { Metadata } from 'next'
import { LandingPage } from '@/components/landing/LandingPage'
import { HOME_FAQ, OG_IMAGE, SEO_PAGES, SITE_URL } from '@/config/seo.config'

const homeSeo = SEO_PAGES.home

export const metadata: Metadata = {
  title: homeSeo.title,
  description: homeSeo.description,
  keywords: homeSeo.keywords,
  openGraph: {
    title: homeSeo.title,
    description: homeSeo.description,
    url: SITE_URL,
    siteName: 'ZentroApp',
    images: [{ url: OG_IMAGE, width: 1200, height: 630, alt: 'ZentroApp POS' }],
    locale: 'en_UG',
    type: 'website',
  },
  twitter: {
    card: 'summary_large_image',
    title: homeSeo.title,
    description: homeSeo.description,
    images: [OG_IMAGE],
  },
  alternates: { canonical: SITE_URL },
}

function faqJsonLd() {
  return {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: HOME_FAQ.map((item) => ({
      '@type': 'Question',
      name: item.question,
      acceptedAnswer: { '@type': 'Answer', text: item.answer },
    })),
  }
}

export default function Home() {
  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(faqJsonLd()) }}
      />
      <LandingPage />
    </>
  )
}
