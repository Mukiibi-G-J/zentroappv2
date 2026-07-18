import type { AddOn } from '@/types/pricing'

interface AddOnsSectionProps {
  addOns?: AddOn[]
}

const DEFAULT_ADDONS: AddOn[] = [
  {
    id: 1,
    code: 'restaurant',
    name: 'Restaurant Module',
    price: 25000,
    description: 'Perfect for food & beverage businesses',
    is_per_unit: false,
    order: 1,
  },
  {
    id: 2,
    code: 'efris',
    name: 'EFRIS Integration',
    price: 80000,
    description: 'Seamless compliance with Uganda Revenue Authority',
    is_per_unit: false,
    order: 2,
  },
  {
    id: 3,
    code: 'extra_users',
    name: 'Extra Active Users',
    price: 10000,
    description: 'Per additional user (one-time), for any plan',
    is_per_unit: true,
    order: 3,
  },
]

export function AddOnsSection({ addOns = DEFAULT_ADDONS }: AddOnsSectionProps) {
  const displayAddOns = addOns.length > 0 ? addOns : DEFAULT_ADDONS

  return (
    <div
      className="mt-12 p-6 rounded-xl border"
      style={{ backgroundColor: '#F8FAFC', borderColor: '#E2E8F0' }}
    >
      <h3 className="text-lg font-semibold mb-4" style={{ color: '#0F172A' }}>
        Add-ons
      </h3>
      <ul className="space-y-3">
        {displayAddOns.map((addon) => (
          <li
            key={addon.id}
            className="flex items-start justify-between gap-4"
            style={{ color: '#475569' }}
          >
            <div>
              <span className="font-medium" style={{ color: '#0F172A' }}>
                {addon.name}:
              </span>{' '}
              <span style={{ color: '#64748B' }}>{addon.description}</span>
            </div>
            <span className="font-semibold whitespace-nowrap" style={{ color: '#0F172A' }}>
              {addon.is_per_unit
                ? `+ UGX ${addon.price.toLocaleString()} per user (one-time)`
                : `UGX ${addon.price.toLocaleString()}`}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
