import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useCart } from '@/hooks/useCart'
import { createAddress, listAddresses } from '@/services/addresses'
import { previewCheckout, createOrder } from '@/services/orders'
import { getApiErrorMessage } from '@/services/apiClient'
import { AddressList } from '@/components/checkout/AddressList'
import { AddressForm } from '@/components/checkout/AddressForm'
import { PaymentMethodSelector, type PaymentMethod } from '@/components/checkout/PaymentMethodSelector'
import { OrderSummary } from '@/components/cart/OrderSummary'
import { Button } from '@/components/ui/Button'
import { Checkbox } from '@/components/ui/Checkbox'
import { FormAlert } from '@/components/ui/FormAlert'
import { Skeleton } from '@/components/feedback/Skeleton'
import { SeoHead } from '@/components/seo/SeoHead'
import type { AddressInput } from '@/types/address'

export function CheckoutPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const cart = useCart()
  const addresses = useQuery({ queryKey: ['addresses'], queryFn: listAddresses })

  const [selectedAddressId, setSelectedAddressId] = useState<number | null>(null)
  const [showAddForm, setShowAddForm] = useState(false)
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>('card')
  const [cardNumber, setCardNumber] = useState('')
  const [customerNote, setCustomerNote] = useState('')
  const [acceptTerms, setAcceptTerms] = useState(false)

  useEffect(() => {
    if (!cart.isLoading && cart.data && cart.data.items.length === 0) {
      navigate('/cart', { replace: true })
    }
  }, [cart.isLoading, cart.data, navigate])

  useEffect(() => {
    if (selectedAddressId === null && addresses.data && addresses.data.length > 0) {
      const preferred = addresses.data.find((a) => a.is_default_shipping) ?? addresses.data[0]
      setSelectedAddressId(preferred.id)
    }
  }, [addresses.data, selectedAddressId])

  useEffect(() => {
    if (addresses.data && addresses.data.length === 0) setShowAddForm(true)
  }, [addresses.data])

  const createAddressMutation = useMutation({
    mutationFn: createAddress,
    onSuccess: (address) => {
      queryClient.setQueryData(['addresses'], [...(addresses.data ?? []), address])
      setSelectedAddressId(address.id)
      setShowAddForm(false)
    },
  })

  const preview = useQuery({
    queryKey: ['checkout-preview', selectedAddressId, paymentMethod],
    queryFn: () =>
      previewCheckout({ shipping_address_id: selectedAddressId!, shipping_method: 'standard', payment_method: paymentMethod }),
    enabled: selectedAddressId !== null && Boolean(cart.data?.items.length),
  })

  const placeOrder = useMutation({
    mutationFn: createOrder,
    onSuccess: (order) => {
      queryClient.invalidateQueries({ queryKey: ['cart'] })
      queryClient.invalidateQueries({ queryKey: ['orders'] })
      navigate(`/order/confirmation/${order.order_number}`, { replace: true })
    },
  })

  const handlePlaceOrder = () => {
    if (selectedAddressId === null) return
    placeOrder.mutate({
      shipping_address_id: selectedAddressId,
      shipping_method: 'standard',
      payment_method: paymentMethod,
      card_number: paymentMethod === 'card' ? cardNumber : undefined,
      customer_note: customerNote || undefined,
      accept_terms: acceptTerms,
    })
  }

  if (cart.isLoading || addresses.isLoading) {
    return (
      <div className="container-page py-10">
        <Skeleton className="h-8 w-48" />
        <div className="mt-8 grid gap-10 md:grid-cols-[1fr_360px]">
          <Skeleton className="h-96 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      </div>
    )
  }

  const totals = preview.data?.totals
  const canPlaceOrder =
    selectedAddressId !== null &&
    acceptTerms &&
    (paymentMethod !== 'card' || cardNumber.trim().length >= 12) &&
    !placeOrder.isPending

  return (
    <div className="container-page py-10">
      <SeoHead
        title="Checkout"
        description="Complete your BlackCart purchase by confirming shipping and payment details."
        path="/checkout"
        noindex
      />
      <h1 className="text-3xl font-semibold tracking-tight">Checkout</h1>

      <div className="mt-8 grid gap-10 md:grid-cols-[1fr_360px]">
        <div className="flex flex-col gap-8">
          <section>
            <h2 className="text-xs font-medium uppercase tracking-wide text-text-tertiary">Shipping address</h2>
            <div className="mt-4">
              {addresses.data && addresses.data.length > 0 ? (
                <AddressList
                  addresses={addresses.data}
                  selectedId={selectedAddressId}
                  onSelect={setSelectedAddressId}
                />
              ) : null}

              {showAddForm ? (
                <div className="mt-4">
                  <AddressForm
                    isSubmitting={createAddressMutation.isPending}
                    onCancel={addresses.data && addresses.data.length > 0 ? () => setShowAddForm(false) : undefined}
                    onSubmit={(payload: AddressInput) => createAddressMutation.mutate(payload)}
                  />
                </div>
              ) : (
                <button
                  type="button"
                  onClick={() => setShowAddForm(true)}
                  className="mt-3 text-sm font-medium text-text hover:underline"
                >
                  + Add a new address
                </button>
              )}
            </div>
          </section>

          <section>
            <h2 className="text-xs font-medium uppercase tracking-wide text-text-tertiary">Payment method</h2>
            <div className="mt-4">
              <PaymentMethodSelector
                method={paymentMethod}
                onMethodChange={setPaymentMethod}
                cardNumber={cardNumber}
                onCardNumberChange={setCardNumber}
              />
            </div>
          </section>

          <section>
            <h2 className="text-xs font-medium uppercase tracking-wide text-text-tertiary">Order note (optional)</h2>
            <textarea
              value={customerNote}
              onChange={(e) => setCustomerNote(e.target.value)}
              maxLength={500}
              rows={3}
              placeholder="Delivery instructions, gift note, etc."
              className="mt-3 w-full rounded-(--radius-md) border border-border bg-surface-sunken p-3 text-sm text-text placeholder:text-text-tertiary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring"
            />
          </section>
        </div>

        <div className="flex flex-col gap-4">
          {placeOrder.isError ? <FormAlert>{getApiErrorMessage(placeOrder.error)}</FormAlert> : null}

          <OrderSummary
            currency="INR"
            subtotal={totals?.subtotal ?? cart.data?.totals.subtotal ?? '0'}
            discountTotal={totals?.discount_total ?? cart.data?.totals.discount_total}
            shippingFee={totals?.shipping_fee}
            taxTotal={totals?.tax_total ?? cart.data?.totals.tax_total ?? '0'}
            total={totals?.grand_total ?? cart.data?.totals.estimated_total ?? '0'}
          >
            <div className="flex flex-col gap-4">
              <Checkbox
                label="I agree to the Terms of Service and Privacy Policy"
                checked={acceptTerms}
                onChange={(e) => setAcceptTerms(e.target.checked)}
              />
              <Button className="w-full" loading={placeOrder.isPending} disabled={!canPlaceOrder} onClick={handlePlaceOrder}>
                Place order
              </Button>
            </div>
          </OrderSummary>
        </div>
      </div>
    </div>
  )
}
