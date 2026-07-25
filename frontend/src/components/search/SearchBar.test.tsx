import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router'
import { SearchBar } from './SearchBar'
import * as searchService from '@/services/search'

const navigateMock = vi.fn()
vi.mock('react-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router')>()
  return { ...actual, useNavigate: () => navigateMock }
})
vi.mock('@/services/search')

afterEach(() => {
  cleanup()
  vi.resetAllMocks()
})

function renderSearchBar() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <SearchBar />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

const emptySuggestions = { products: [], brands: [], categories: [], popular_queries: [] }

describe('SearchBar', () => {
  it('is collapsed to an icon button by default', () => {
    renderSearchBar()
    expect(screen.getByLabelText('Search')).toBeInTheDocument()
    expect(screen.queryByLabelText('Search products')).not.toBeInTheDocument()
  })

  it('expands into a search field when the icon is clicked', async () => {
    renderSearchBar()
    await userEvent.click(screen.getByLabelText('Search'))
    expect(screen.getByLabelText('Search products')).toBeInTheDocument()
  })

  it('debounces the suggest call — does not fire on every keystroke', async () => {
    vi.mocked(searchService.suggestSearch).mockResolvedValue(emptySuggestions)
    renderSearchBar()
    await userEvent.click(screen.getByLabelText('Search'))
    await userEvent.type(screen.getByLabelText('Search products'), 'shirt')

    // Immediately after typing, the debounce window (200ms) shouldn't have elapsed yet.
    expect(searchService.suggestSearch).not.toHaveBeenCalled()

    await waitFor(() => expect(searchService.suggestSearch).toHaveBeenCalledWith('shirt'), { timeout: 1000 })
    expect(searchService.suggestSearch).toHaveBeenCalledTimes(1)
  })

  it('does not query for a single character (below the 2-char minimum)', async () => {
    vi.mocked(searchService.suggestSearch).mockResolvedValue(emptySuggestions)
    renderSearchBar()
    await userEvent.click(screen.getByLabelText('Search'))
    await userEvent.type(screen.getByLabelText('Search products'), 'a')

    await new Promise((r) => setTimeout(r, 400))
    expect(searchService.suggestSearch).not.toHaveBeenCalled()
  })

  it('navigates to the product on Enter when a suggestion is keyboard-highlighted', async () => {
    vi.mocked(searchService.suggestSearch).mockResolvedValue({
      products: [
        { slug: 'blue-tee', title: 'Blue Tee', thumbnail_url: null, price: '499.00', currency: 'INR' },
        { slug: 'red-tee', title: 'Red Tee', thumbnail_url: null, price: '599.00', currency: 'INR' },
      ],
      brands: [],
      categories: [],
      popular_queries: [],
    })
    renderSearchBar()
    await userEvent.click(screen.getByLabelText('Search'))
    const input = screen.getByLabelText('Search products')
    await userEvent.type(input, 'tee')

    await waitFor(() => expect(screen.getByText('Blue Tee')).toBeInTheDocument())

    await userEvent.keyboard('{ArrowDown}{ArrowDown}{Enter}')
    expect(navigateMock).toHaveBeenCalledWith('/p/red-tee')
  })

  it('submits the raw query to the search page on Enter with nothing highlighted', async () => {
    vi.mocked(searchService.suggestSearch).mockResolvedValue(emptySuggestions)
    renderSearchBar()
    await userEvent.click(screen.getByLabelText('Search'))
    const input = screen.getByLabelText('Search products')
    await userEvent.type(input, 'oversized hoodie{Enter}')

    expect(navigateMock).toHaveBeenCalledWith('/search?q=oversized%20hoodie')
  })

  it('closes the panel on Escape', async () => {
    renderSearchBar()
    await userEvent.click(screen.getByLabelText('Search'))
    expect(screen.getByLabelText('Search products')).toBeInTheDocument()
    await userEvent.keyboard('{Escape}')
    expect(screen.queryByLabelText('Search products')).not.toBeInTheDocument()
  })
})
