export const SITE_URL = 'https://zentroapp.uncodedsolutions.com'
export const SITE_NAME = 'ZentroApp'
export const OG_IMAGE = `${SITE_URL}/og-image.png`

export const SEO_PAGES = {
  home: {
    path: '/',
    title: 'Point of Sale Systems Uganda & Africa | EFRIS Compliant POS | ZentroApp',
    description:
      'Best point of sale software in Uganda and across Africa. EFRIS-compliant POS with inventory management, sales tracking, multi-branch control, and offline Android app. Free trial for Kampala and nationwide businesses.',
    keywords:
      'point of sale systems Uganda, POS systems Uganda, EFRIS compliant POS, retail POS Uganda, restaurant POS Uganda, inventory management Uganda, Kampala POS, POS systems Africa',
  },
} as const

export const HOME_FAQ = [
  {
    question: 'Is ZentroApp EFRIS compliant in Uganda?',
    answer:
      'Yes. ZentroApp supports Uganda Revenue Authority Electronic Fiscal Receipting and Invoicing Solution (EFRIS) so you can issue compliant fiscal receipts from your POS.',
  },
  {
    question: 'Does ZentroApp work offline?',
    answer:
      'Yes. The ZentroApp Android POS works offline and syncs sales and inventory when your connection returns, which is ideal for unreliable internet.',
  },
  {
    question: 'Can I manage multiple branches in Uganda?',
    answer:
      'Yes. Manage stock, staff, and reports per branch from one account with centralized oversight.',
  },
  {
    question: 'How much does POS software cost in Uganda?',
    answer:
      'Plans start with a 14-day free trial. Visit our pricing section on the homepage or contact sales for multi-branch quotes in UGX.',
  },
  {
    question: 'Who is ZentroApp built for?',
    answer:
      'Retail shops, restaurants, pharmacies, and growing businesses in Uganda and across Africa that need POS, inventory, and EFRIS in one system.',
  },
] as const
