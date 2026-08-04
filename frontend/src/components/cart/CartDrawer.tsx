import { useEffect, useRef } from 'react'
import { Link } from 'react-router'
import { useCartDrawerStore } from '@/store/cartDrawerStore'
import { useCart, useRemoveCartItem, useUpdateCartItem } from '@/hooks/useCart'
import { CartLine } from './CartLine'
import { Button } from '@/components/ui/Button'
import { cn } from '@/lib/cn'
import { formatMoney } from '@/lib/money'

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

export function CartDrawer() {
  const { isOpen, close } = useCartDrawerStore()
  const cart = useCart()
  const updateMutation = useUpdateCartItem()
  const removeMutation = useRemoveCartItem()
  const dialogRef = useRef<HTMLDivElement>(null)
  const closeButtonRef = useRef<HTMLButtonElement>(null)
  const previouslyFocused = useRef<HTMLElement | null>(null)

  // Real focus management, not just aria-modal (which tells assistive tech this is a dialog but
  // doesn't itself move focus or stop Tab from reaching the page behind it): capture whatever had
  // focus before opening (usually the header's cart button) so it can be restored on close, move
  // focus into the dialog on open, and trap Tab/Shift+Tab within it while it's open.
  useEffect(() => {
    if (!isOpen) return
    previouslyFocused.current = document.activeElement as HTMLElement | null
    closeButtonRef.current?.focus()

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        close()
        return
      }
      if (e.key !== 'Tab' || !dialogRef.current) return
      const focusable = Array.from(dialogRef.current.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR))
      if (focusable.length === 0) return
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault()
        last.focus()
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault()
        first.focus()
      }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      previouslyFocused.current?.focus()
    }
  }, [isOpen, close])

  const items = cart.data?.items ?? []

  return (
    <div className={cn('fixed inset-0 z-50', !isOpen && 'pointer-events-none')} aria-hidden={!isOpen}>
      <div
        onClick={close}
        className={cn(
          'absolute inset-0 bg-(--overlay) transition-opacity duration-250 ease-(--ease-standard)',
          isOpen ? 'opacity-100' : 'opacity-0',
        )}
      />
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label="Shopping cart"
        className={cn(
          'absolute right-0 top-0 flex h-full w-full max-w-md flex-col border-l border-border bg-bg',
          'transition-transform duration-250 ease-(--ease-standard)',
          isOpen ? 'translate-x-0' : 'translate-x-full',
        )}
      >
        <div className="flex h-16 shrink-0 items-center justify-between border-b border-border px-5">
          <h2 className="text-sm font-medium text-text">Cart{items.length > 0 ? ` (${items.length})` : ''}</h2>
          <button
            ref={closeButtonRef}
            type="button"
            onClick={close}
            aria-label="Close cart"
            className="flex h-10 w-10 items-center justify-center rounded-(--radius-md) text-text-secondary hover:bg-surface-raised hover:text-text"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden="true">
              <path d="M6 6l12 12M18 6L6 18" />
            </svg>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-5">
          {items.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center gap-2 text-center">
              <p className="text-sm text-text-secondary">Your cart is empty</p>
              <Button variant="secondary" size="sm" onClick={close}>
                Continue shopping
              </Button>
            </div>
          ) : (
            <ul className="divide-y divide-border">
              {items.map((item) => (
                <CartLine
                  key={item.id}
                  item={item}
                  currency={cart.data!.currency}
                  updating={updateMutation.isPending || removeMutation.isPending}
                  onUpdateQuantity={(quantity) => updateMutation.mutate({ itemId: item.id, quantity })}
                  onRemove={() => removeMutation.mutate(item.id)}
                />
              ))}
            </ul>
          )}
        </div>

        {items.length > 0 && cart.data ? (
          <div className="shrink-0 border-t border-border p-5">
            <div className="flex justify-between text-sm">
              <span className="text-text-secondary">Estimated total</span>
              <span className="text-price text-text">{formatMoney(cart.data.totals.estimated_total, cart.data.currency)}</span>
            </div>
            <div className="mt-4 flex flex-col gap-2">
              <Link
                to="/checkout"
                onClick={close}
                className="flex h-11 items-center justify-center rounded-(--radius-md) bg-accent text-sm font-medium text-accent-fg transition-opacity duration-150 hover:opacity-90"
              >
                Checkout
              </Link>
              <Link
                to="/cart"
                onClick={close}
                className="flex h-11 items-center justify-center rounded-(--radius-md) border border-border-strong text-sm text-text hover:bg-surface-raised"
              >
                View cart
              </Link>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  )
}
