import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { CartLine } from './CartLine'
import type { CartItem } from '@/types/cart'

function makeItem(overrides: Partial<CartItem> = {}): CartItem {
  return {
    id: 1,
    variant_id: 10,
    variant: { sku: 'SKU-1', size: 'M', color: 'Black', color_hex: '#000000' },
    product: { slug: 'test-product', title: 'Test Product', brand: 'TestBrand', thumbnail_url: null },
    quantity: 2,
    unit_price: '500.00',
    unit_price_snapshot: '500.00',
    price_changed: false,
    available: 5,
    is_active: true,
    line_total: '1000.00',
    ...overrides,
  }
}

function renderLine(props: Partial<React.ComponentProps<typeof CartLine>> = {}) {
  const onUpdateQuantity = vi.fn()
  const onRemove = vi.fn()
  render(
    <MemoryRouter>
      <ul>
        <CartLine
          item={makeItem()}
          currency="INR"
          onUpdateQuantity={onUpdateQuantity}
          onRemove={onRemove}
          {...props}
        />
      </ul>
    </MemoryRouter>,
  )
  return { onUpdateQuantity, onRemove }
}

describe('CartLine', () => {
  it('renders the product title, quantity, and formatted line total', () => {
    renderLine()
    expect(screen.getByText('Test Product')).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument()
    expect(screen.getByText('₹1,000')).toBeInTheDocument()
  })

  it('calls onUpdateQuantity with quantity+1 when the increase button is clicked', async () => {
    const { onUpdateQuantity } = renderLine()
    await userEvent.click(screen.getByLabelText('Increase quantity'))
    expect(onUpdateQuantity).toHaveBeenCalledWith(3)
  })

  it('calls onUpdateQuantity with quantity-1 when the decrease button is clicked', async () => {
    const { onUpdateQuantity } = renderLine()
    await userEvent.click(screen.getByLabelText('Decrease quantity'))
    expect(onUpdateQuantity).toHaveBeenCalledWith(1)
  })

  it('disables the decrease button at quantity 1', () => {
    renderLine({ item: makeItem({ quantity: 1 }) })
    expect(screen.getByLabelText('Decrease quantity')).toBeDisabled()
  })

  it('disables the increase button once available stock is reached', () => {
    renderLine({ item: makeItem({ quantity: 3, available: 3 }) })
    expect(screen.getByLabelText('Increase quantity')).toBeDisabled()
  })

  it('disables the increase button at the 10-unit cap even with more stock available', () => {
    renderLine({ item: makeItem({ quantity: 10, available: 50 }) })
    expect(screen.getByLabelText('Increase quantity')).toBeDisabled()
  })

  it('calls onRemove when the remove button is clicked', async () => {
    const { onRemove } = renderLine()
    await userEvent.click(screen.getByLabelText('Remove item'))
    expect(onRemove).toHaveBeenCalledOnce()
  })

  it('shows an unavailable notice when the item is no longer active', () => {
    renderLine({ item: makeItem({ is_active: false }) })
    expect(screen.getByText('No longer available')).toBeInTheDocument()
  })

  it('shows a price-changed notice when the price has moved since it was added', () => {
    renderLine({ item: makeItem({ price_changed: true }) })
    expect(screen.getByText('Price updated since you added this')).toBeInTheDocument()
  })
})
