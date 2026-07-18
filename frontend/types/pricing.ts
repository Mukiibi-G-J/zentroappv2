export interface PlanComparisonRow {
  name: string
  starter?: boolean | string | null
  business?: boolean | string | null
  pro?: boolean | string | null
  [key: string]: boolean | string | null | undefined
}

export interface FeatureCategory {
  name: string
  rows: PlanComparisonRow[]
}

export interface PlanComparisonPlan {
  id: number
  name: string
  price: number
  annual_price: number
  trial_period: number
  tagline?: string
  best_for?: string
  users_included?: number
  branches?: string
  is_popular?: boolean
  monthly_price_display?: string
  annual_price_display?: string
}

export interface AddOn {
  id: number
  code: string
  name: string
  price: number
  description: string
  is_per_unit: boolean
  order: number
}

export const FEATURE_MATRIX: FeatureCategory[] = [
  {
    name: '',
    rows: [
      {
        name: 'Best for',
        starter: 'Small retailers & shops',
        business: 'Growing wholesalers & chains',
        pro: 'Multi-branch & EFRIS compliance',
      },
      { name: 'Free Trial', starter: '14 Days', business: '14 Days', pro: '14 Days' },
      {
        name: 'Monthly Price',
        starter: 'UGX 50,000',
        business: 'UGX 100,000',
        pro: 'UGX 150,000',
      },
    ],
  },
  {
    name: 'Core Operations',
    rows: [
      { name: 'Active Users', starter: '4', business: '8', pro: '15' },
      { name: 'Branches', starter: '1', business: 'Up to 3', pro: 'Unlimited' },
      { name: 'Sales & POS', starter: true, business: true, pro: true },
      { name: 'Inventory Management', starter: true, business: true, pro: true },
      { name: 'Purchases & Suppliers', starter: true, business: true, pro: true },
      { name: 'Customer Management', starter: true, business: true, pro: true },
      { name: 'Expense Tracking', starter: true, business: true, pro: true },
      { name: 'User Roles & Permissions', starter: true, business: true, pro: true },
    ],
  },
  {
    name: 'Reports & Analytics',
    rows: [
      { name: 'Daily Profit Report', starter: true, business: true, pro: true },
      { name: 'Expense Breakdown Report', starter: true, business: true, pro: true },
      { name: 'Weekly & Monthly Summaries', starter: true, business: true, pro: true },
      { name: 'Product Profitability Report', starter: true, business: true, pro: true },
      { name: 'Inventory Expiry Report', starter: true, business: true, pro: true },
    ],
  },
  {
    name: 'Financial Statements',
    rows: [
      { name: 'Chart of Accounts', starter: true, business: true, pro: true },
      { name: 'Profit & Loss Statement', starter: true, business: true, pro: true },
      { name: 'Balance Sheet', starter: true, business: true, pro: true },
    ],
  },
  {
    name: 'Money Management',
    rows: [
      { name: 'Payments & Settlements', starter: true, business: true, pro: true },
      { name: 'Prepayments & Deposits', starter: true, business: true, pro: true },
      { name: 'Bank Account Management', starter: true, business: true, pro: true },
    ],
  },
  {
    name: 'Advanced Inventory',
    rows: [
      {
        name: 'Item Tracking (Lot / Serial / Expiry)',
        starter: null,
        business: 'Included · Up to 3 branches',
        pro: 'Included · Unlimited branches',
      },
      { name: 'Stock Taking & Physical Inventory', starter: null, business: true, pro: true },
    ],
  },
  {
    name: 'Advanced Operations',
    rows: [
      {
        name: 'Manufacturing & Production (BOM, Orders)',
        starter: null,
        business: true,
        pro: true,
      },
      { name: 'Loan Management', starter: null, business: true, pro: true },
      { name: 'Resources (People, Equipment)', starter: null, business: true, pro: true },
    ],
  },
  {
    name: 'Compliance',
    rows: [
      {
        name: 'EFRIS Integration (URA)',
        starter: 'Add-on (80K/mo)',
        business: 'Add-on (80K/mo)',
        pro: true,
      },
    ],
  },
  {
    name: '',
    rows: [
      {
        name: 'Add-ons Available',
        starter: 'Restaurant, Extra Users',
        business: 'Restaurant, Extra Users',
        pro: 'Restaurant, Extra Users',
      },
    ],
  },
]
