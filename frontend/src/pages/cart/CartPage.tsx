import { Link } from 'react-router'
import { useCart, useRemoveCartItem, useUpdateCartItem } from '@/hooks/useCart'
import { CartLine } from '@/components/cart/CartLine'
import { CouponInput } from '@/components/cart/CouponInput'
import { OrderSummary } from '@/components/cart/OrderSummary'
import { EmptyState, ErrorState } from '@/components/feedback/EmptyState'
import { Skeleton } from '@/components/feedback/Skeleton'
import { getApiErrorMessage } from '@/services/apiClient'

export function CartPage() {
  const cart = useCart()
  const updateMutation = useUpdateCartItem()
  const removeMutation = useRemoveCartItem()

  if (cart.isError) {
    return (
      <div className="container-page py-16">
        <ErrorState message={getApiErrorMessage(cart.error)} onRetry={() => cart.refetch()} />
      </div>
    )
  }

  if (cart.isLoading || !cart.data) {
    return (
      <div className="container-page py-10">
        <Skeleton className="h-8 w-40" />
        <div className="mt-8 grid gap-10 md:grid-cols-[1fr_320px]">
          <div className="space-y-4">
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-24 w-full" />
          </div>
          <Skeleton className="h-64 w-full" />
        </div>
      </div>
    )
  }

  const { items, totals, currency, coupon_code, coupon_error } = cart.data

  if (items.length === 0) {
    return (
      <div className="container-page py-16">
        <EmptyState
          title="Your cart is empty"
          description="Browse the catalogue and add something you like."
          action={
            <Link
              to="/"
              className="mt-2 inline-flex h-11 items-center justify-center rounded-(--radius-md) bg-accent px-5 text-sm font-medium text-accent-fg hover:opacity-90"
            >
              Continue shopping
            </Link>
          }
        />
      </div>
    )
  }

  return (
    <div className="container-page py-10">
      <h1 className="text-3xl font-semibold tracking-tight">Your cart</h1>

      <div className="mt-8 grid gap-10 md:grid-cols-[1fr_320px]">
        <ul className="divide-y divide-border">
          {items.map((item) => (
            <CartLine
              key={item.id}
              item={item}
              currency={currency}
              updating={updateMutation.isPending || removeMutation.isPending}
              onUpdateQuantity={(quantity) => updateMutation.mutate({ itemId: item.id, quantity })}
              onRemove={() => removeMutation.mutate(item.id)}
            />
          ))}
        </ul>

        <div className="flex flex-col gap-4">
          <CouponInput appliedCode={coupon_code} error={coupon_error} />
          <OrderSummary
            currency={currency}
            subtotal={totals.subtotal}
            discountTotal={totals.discount_total}
            taxTotal={totals.tax_total}
            total={totals.estimated_total}
            totalLabel="Estimated total"
          >
            <Link
              to="/checkout"
              className="flex h-11 w-full items-center justify-center rounded-(--radius-md) bg-accent text-sm font-medium text-accent-fg transition-opacity duration-150 hover:opacity-90"
            >
              Proceed to checkout
            </Link>
          </OrderSummary>
        </div>
      </div>
    </div>
  )
}
