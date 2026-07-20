'use client'

import { formatDecimalDisplay } from '@/lib/formatNumber'
import type { POSProduct } from '@/types/pos'

interface POSProductGridProps {
  products: POSProduct[]
  favorites?: POSProduct[]
  loading?: boolean
  onSelect: (product: POSProduct) => void
  onLoadMore?: () => void
  hasMore?: boolean
  compact?: boolean
}

export function POSProductGrid({
  products,
  favorites = [],
  loading,
  onSelect,
  onLoadMore,
  hasMore,
  compact,
}: POSProductGridProps) {
  const showFavorites = favorites.length > 0

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-hidden">
      {showFavorites && (
        <section>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-bodyText">
            Favorites
          </h3>
          <div className={`grid gap-2 ${compact ? 'grid-cols-2' : 'grid-cols-3 sm:grid-cols-4 lg:grid-cols-5'}`}>
            {favorites.map((p) => (
              <ProductTile key={p.SystemId} product={p} onSelect={onSelect} compact={compact} />
            ))}
          </div>
        </section>
      )}

      <section className="flex min-h-0 flex-1 flex-col">
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-bodyText">
          Products
        </h3>
        {loading && !products.length ? (
          <div className="grid flex-1 place-content-center text-sm text-bodyText">Loading items…</div>
        ) : (
          <div className="min-h-0 flex-1 overflow-y-auto">
            <div className={`grid gap-2 pb-4 ${compact ? 'grid-cols-2' : 'grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5'}`}>
              {products.map((p) => (
                <ProductTile key={p.SystemId} product={p} onSelect={onSelect} compact={compact} />
              ))}
            </div>
            {hasMore && (
              <div className="flex justify-center pb-4">
                <button
                  type="button"
                  onClick={onLoadMore}
                  className="rounded-lg border border-strokeColor bg-white px-4 py-2 text-sm font-medium text-mainTextColor hover:bg-softBg"
                >
                  Load more
                </button>
              </div>
            )}
          </div>
        )}
      </section>
    </div>
  )
}

function ProductTile({
  product,
  onSelect,
  compact,
}: {
  product: POSProduct
  onSelect: (p: POSProduct) => void
  compact?: boolean
}) {
  const isInventory = product.type === 'Inventory' || product.type == null
  const qty = product.inventory
  const outOfStock = isInventory && qty != null && qty <= 0

  return (
    <button
      type="button"
      disabled={outOfStock}
      onClick={() => onSelect(product)}
      className={`flex flex-col rounded-xl border border-strokeColor bg-white text-left shadow-sm transition hover:border-primary/40 hover:shadow-md disabled:cursor-not-allowed disabled:opacity-50 ${
        compact ? 'p-3 min-h-[88px]' : 'p-4 min-h-[100px]'
      }`}
    >
      <span className="line-clamp-2 text-sm font-medium text-mainTextColor">{product.item_name}</span>
      <span className="mt-1 text-xs text-bodyText">{product.no}</span>
      <div className="mt-auto flex items-end justify-between gap-2 pt-2">
        <span className="text-sm font-semibold text-primary">
          {formatDecimalDisplay(product.unit_price)}
        </span>
        {isInventory && qty != null ? (
          <span
            className={`shrink-0 text-xs font-medium ${
              outOfStock ? 'text-red-600' : qty <= 5 ? 'text-amber-600' : 'text-bodyText'
            }`}
          >
            {outOfStock ? 'Out of stock' : `Qty ${formatDecimalDisplay(qty)}`}
          </span>
        ) : null}
      </div>
    </button>
  )
}
