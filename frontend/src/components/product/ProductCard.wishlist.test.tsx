import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router'
import { ProductCard } from './ProductCard'
import * as discoveryService from '@/services/discovery'
import * as authHooks from '@/hooks/useAuth'
import type { ProductCard as ProductCardType } from '@/types/catalog'

const navigateMock = vi.fn()
vi.mock('react-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router')>()
  return { ...actual, useNavigate: () => navigateMock }
})
vi.mock('@/services/discovery')
vi.mock('@/hooks/useAuth')

afterEach(() => {
  cleanup()
  vi.resetAllMocks()
})

const product: ProductCardType = {
  slug: 'test-product',
  title: 'Test Product',
  brand: 'TestBrand',
  thumbnail_url: null,
  price: '999.00',
  mrp: '1999.00',
  discount_percent: '50.00',
  rating_avg: '4.5',
  rating_count: 10,
  currency: 'INR',
  in_stock: true,
}

function renderCard() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <ProductCard product={product} />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('ProductCard wishlist toggle', () => {
  it('redirects a guest to login instead of calling the wishlist API', async () => {
    vi.mocked(authHooks.useCurrentUser).mockReturnValue({ data: null } as ReturnType<typeof authHooks.useCurrentUser>)

    renderCard()
    await userEvent.click(screen.getByLabelText('Add to wishlist'))

    expect(discoveryService.addWishlistItem).not.toHaveBeenCalled()
    expect(navigateMock).toHaveBeenCalledWith(expect.stringContaining('/auth/login?next='))
  })

  it('adds to the wishlist and flips the button to "pressed" for a logged-in user', async () => {
    vi.mocked(authHooks.useCurrentUser).mockReturnValue({
      data: { public_id: 'u1' },
    } as ReturnType<typeof authHooks.useCurrentUser>)
    vi.mocked(discoveryService.getWishlistSlugs).mockResolvedValue([])
    vi.mocked(discoveryService.addWishlistItem).mockResolvedValue({
      items: [{ item_id: 1, product }],
    })

    renderCard()
    const button = await screen.findByLabelText('Add to wishlist')
    await userEvent.click(button)

    await waitFor(() => expect(discoveryService.addWishlistItem).toHaveBeenCalledWith('test-product'))
    await waitFor(() => expect(screen.getByLabelText('Remove from wishlist')).toHaveAttribute('aria-pressed', 'true'))
  })

  it('removes from the wishlist when already wishlisted', async () => {
    vi.mocked(authHooks.useCurrentUser).mockReturnValue({
      data: { public_id: 'u1' },
    } as ReturnType<typeof authHooks.useCurrentUser>)
    vi.mocked(discoveryService.getWishlistSlugs).mockResolvedValue(['test-product'])
    vi.mocked(discoveryService.removeWishlistItem).mockResolvedValue({ items: [] })

    renderCard()
    const button = await screen.findByLabelText('Remove from wishlist')
    await userEvent.click(button)

    await waitFor(() => expect(discoveryService.removeWishlistItem).toHaveBeenCalledWith('test-product'))
  })
})
