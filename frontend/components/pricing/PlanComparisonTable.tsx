import React from 'react'
import Link from 'next/link'
import { FaCheck } from 'react-icons/fa'
import type { PlanComparisonPlan } from '@/types/pricing'
import { FEATURE_MATRIX } from '@/types/pricing'

interface PlanComparisonTableProps {
  plans: PlanComparisonPlan[]
  isYearly: boolean
  onSelectPlan?: (plan: PlanComparisonPlan) => void
  showActions?: boolean
  actionHref?: string
  actionButtonLabel?: string
  currentComparisonPlan?: 'Starter' | 'Business' | 'Pro' | null
}

const COLORS = {
  primary: '#2563EB',
  neutralBg: '#F8FAFC',
  neutralBorder: '#E2E8F0',
  text: '#0F172A',
  textSecondary: '#475569',
  textMuted: '#94A3B8',
  success: '#16A34A',
} as const

const DEFAULT_TAGLINES: Record<string, string> = {
  Starter: 'Ideal for: Small Retailers & Shops',
  Business: 'Ideal for: Growing Wholesalers & Chains',
  Pro: 'Ideal for: Multi-Branch & EFRIS Compliance',
}

const PLAN_DOT_COLORS: Record<string, string> = {
  Starter: '#16A34A',
  Business: '#2563EB',
  Pro: '#7C3AED',
}

function CellValue({ value }: { value: boolean | string | null }) {
  if (value === null) {
    return <span style={{ color: COLORS.textMuted }}>—</span>
  }
  if (value === true) {
    return <FaCheck className="text-lg" style={{ color: COLORS.success }} />
  }
  return <span style={{ color: COLORS.textSecondary }}>{value}</span>
}

export function PlanComparisonTable({
  plans,
  isYearly,
  onSelectPlan,
  showActions = true,
  actionHref = '/signup',
  actionButtonLabel = 'Start Free Trial',
  currentComparisonPlan = null,
}: PlanComparisonTableProps) {
  const planOrder = ['Starter', 'Business', 'Pro']
  const sortedPlans = [...plans]
    .filter((p) => planOrder.includes(p.name))
    .sort((a, b) => planOrder.indexOf(a.name) - planOrder.indexOf(b.name))

  if (sortedPlans.length === 0) return null

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[700px] border-collapse">
        <thead>
          <tr>
            <th
              className="text-left p-4 border-b w-48"
              style={{ borderColor: COLORS.neutralBorder }}
            />
            {sortedPlans.map((plan) => (
              <th
                key={plan.id}
                className="p-4 border-b border-l min-w-[180px]"
                style={{ backgroundColor: COLORS.neutralBg, borderColor: COLORS.neutralBorder }}
              >
                <div className="flex flex-wrap items-center gap-2 mb-1">
                  <span
                    className="w-3 h-3 rounded-full"
                    style={{ backgroundColor: PLAN_DOT_COLORS[plan.name] || COLORS.primary }}
                    aria-hidden
                  />
                  <span className="font-bold" style={{ color: COLORS.text }}>
                    {plan.name}
                  </span>
                  {currentComparisonPlan === plan.name && (
                    <span
                      className="text-xs font-semibold px-2 py-0.5 rounded-full"
                      style={{ backgroundColor: '#E0E7FF', color: '#3730A3' }}
                    >
                      Current
                    </span>
                  )}
                </div>
                <div className="text-lg font-semibold" style={{ color: COLORS.text }}>
                  UGX{(isYearly ? plan.annual_price : plan.price).toLocaleString()}/
                  {isYearly ? 'yr' : 'mo'}
                </div>
                {(plan.tagline || DEFAULT_TAGLINES[plan.name]) && (
                  <div className="text-sm mt-1" style={{ color: COLORS.textSecondary }}>
                    ({plan.tagline || DEFAULT_TAGLINES[plan.name]})
                  </div>
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {FEATURE_MATRIX.map((category, catIdx) => (
            <React.Fragment key={catIdx}>
              {category.name && (
                <tr>
                  <td
                    className="p-2 font-semibold border-b border-l"
                    style={{
                      backgroundColor: COLORS.neutralBg,
                      color: COLORS.textSecondary,
                      borderColor: COLORS.neutralBorder,
                    }}
                  >
                    {category.name}
                  </td>
                  {sortedPlans.map((plan) => (
                    <td
                      key={plan.id}
                      className="p-2 border-b border-l"
                      style={{ backgroundColor: COLORS.neutralBg, borderColor: COLORS.neutralBorder }}
                    />
                  ))}
                </tr>
              )}
              {category.rows.map((row, rowIdx) => {
                const getVal = (planName: string) =>
                  (row as Record<string, boolean | string | null>)[planName.toLowerCase()]
                return (
                  <tr
                    key={`${category.name}-${rowIdx}`}
                    className="border-b"
                    style={{ borderColor: COLORS.neutralBorder }}
                  >
                    <td className="p-4 font-medium" style={{ color: COLORS.textSecondary }}>
                      {row.name}
                    </td>
                    {sortedPlans.map((plan) => (
                      <td
                        key={plan.id}
                        className="p-4 border-l text-center"
                        style={{ borderColor: COLORS.neutralBorder }}
                      >
                        <CellValue value={getVal(plan.name) ?? null} />
                      </td>
                    ))}
                  </tr>
                )
              })}
            </React.Fragment>
          ))}
          {showActions && (
            <tr>
              <td className="p-4 font-medium" style={{ color: COLORS.textSecondary }}>
                Action
              </td>
              {sortedPlans.map((plan) => (
                <td
                  key={plan.id}
                  className="p-4 border-l text-center"
                  style={{ borderColor: COLORS.neutralBorder }}
                >
                  {onSelectPlan ? (
                    <button
                      type="button"
                      onClick={() => onSelectPlan(plan)}
                      className="px-4 py-2 rounded-lg font-semibold text-white hover:opacity-90 transition"
                      style={{ backgroundColor: COLORS.primary }}
                    >
                      {actionButtonLabel}
                    </button>
                  ) : (
                    <Link
                      href={
                        actionHref.startsWith('/signup')
                          ? `/signup?plan=${encodeURIComponent(plan.name)}`
                          : actionHref
                      }
                      className="inline-block px-4 py-2 rounded-lg font-semibold text-white hover:opacity-90 transition"
                      style={{ backgroundColor: COLORS.primary }}
                    >
                      {actionButtonLabel}
                    </Link>
                  )}
                </td>
              ))}
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
