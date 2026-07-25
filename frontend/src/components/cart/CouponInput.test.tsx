import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { CouponInput } from './CouponInput'
import * as cartService from '@/services/cart'
import type { Cart } from '@/types/cart'

vi.mock('@/services/cart')

afterEach(() => {
  cleanup()
  vi.resetAllMocks()
})

function baseCart(overrides: Partial<Cart> = {}): Cart {
  return {
    public_id: 'cart-1',
    currency: 'INR',
    items: [],
    coupon_code: null,
    coupon_error: null,
    totals: { subtotal: '1000.00', discount_total: '0.00', tax_total: '0.00', estimated_total: '1000.00' },
    ...overrides,
  }
}

function renderWithClient(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>)
}

describe('CouponInput', () => {
  it('shows an input and Apply button when no coupon is applied', () => {
    renderWithClient(<CouponInput appliedCode={null} error={null} />)
    expect(screen.getByPlaceholderText('Coupon code')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Apply' })).toBeDisabled()
  })

  it('submits the entered code via the apply-coupon service call', async () => {
    vi.mocked(cartService.applyCoupon).mockResolvedValue(baseCart({ coupon_code: 'SAVE10' }))

    renderWithClient(<CouponInput appliedCode={null} error={null} />)
    const input = screen.getByPlaceholderText('Coupon code')
    await userEvent.type(input, 'save10')
    await userEvent.click(screen.getByRole('button', { name: 'Apply' }))

    await waitFor(() => expect(cartService.applyCoupon).toHaveBeenCalledWith('SAVE10'))
  })

  it('uppercases the code as the user types', async () => {
    renderWithClient(<CouponInput appliedCode={null} error={null} />)
    const input = screen.getByPlaceholderText('Coupon code') as HTMLInputElement
    await userEvent.type(input, 'lowercase')
    expect(input.value).toBe('LOWERCASE')
  })

  it('shows the applied code with a success indicator and a Remove control', () => {
    renderWithClient(<CouponInput appliedCode="WELCOME10" error={null} />)
    expect(screen.getByText('WELCOME10')).toBeInTheDocument()
    expect(screen.getByText('Applied')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Remove' })).toBeInTheDocument()
  })

  it('shows the error message instead of "Applied" when the applied coupon is now invalid', () => {
    renderWithClient(<CouponInput appliedCode="EXPIRED5" error="This coupon has expired." />)
    expect(screen.getByText('This coupon has expired.')).toBeInTheDocument()
    expect(screen.queryByText('Applied')).not.toBeInTheDocument()
  })

  it('calls remove-coupon when Remove is clicked', async () => {
    vi.mocked(cartService.removeCoupon).mockResolvedValue(baseCart())
    renderWithClient(<CouponInput appliedCode="WELCOME10" error={null} />)
    await userEvent.click(screen.getByRole('button', { name: 'Remove' }))
    await waitFor(() => expect(cartService.removeCoupon).toHaveBeenCalledOnce())
  })
})
