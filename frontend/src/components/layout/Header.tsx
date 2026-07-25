import { Link, NavLink } from 'react-router'
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { cn } from '@/lib/cn'
import { listCategories } from '@/services/catalog'
import { useCurrentUser } from '@/hooks/useAuth'
import { useCart } from '@/hooks/useCart'
import { useCartDrawerStore } from '@/store/cartDrawerStore'
import { SearchBar } from '@/components/search/SearchBar'

export function Header() {
  const [mobileOpen, setMobileOpen] = useState(false)

  const categories = useQuery({
    queryKey: ['categories'],
    queryFn: listCategories,
    staleTime: 60 * 60 * 1000,
  })
  const { data: currentUser } = useCurrentUser()
  const accountHref = currentUser ? '/account' : '/auth/login?next=%2Faccount'
  const isStaff = currentUser?.roles.some((r) => r !== 'customer') ?? false
  const cart = useCart()
  const openCartDrawer = useCartDrawerStore((s) => s.open)
  const itemCount = cart.data?.items.length ?? 0
  const navLinks = (categories.data ?? [])
    .filter((c) => c.depth === 0)
    .map((c) => ({ label: c.name, to: `/c/${c.slug}` }))

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-bg/95 backdrop-blur-sm">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-(--radius-sm) focus:bg-accent focus:px-4 focus:py-2 focus:text-accent-fg"
      >
        Skip to main content
      </a>

      <div className="container-page flex h-16 items-center justify-between gap-4">
        <button
          type="button"
          className="flex h-11 w-11 items-center justify-center md:hidden"
          aria-label="Open menu"
          aria-expanded={mobileOpen}
          onClick={() => setMobileOpen((v) => !v)}
        >
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden="true">
            <path d="M4 7h16M4 12h16M4 17h16" />
          </svg>
        </button>

        <Link to="/" className="text-lg font-semibold tracking-tight">
          BLACKCART
        </Link>

        <nav className="hidden items-center gap-8 md:flex" aria-label="Primary">
          {navLinks.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              className={({ isActive }) =>
                cn(
                  'text-sm text-text-secondary hover:text-text transition-colors duration-150',
                  isActive && 'text-text font-medium',
                )
              }
            >
              {link.label}
            </NavLink>
          ))}
        </nav>

        <div className="flex items-center gap-1">
          {isStaff ? (
            <Link
              to="/admin"
              className="hidden h-9 items-center rounded-(--radius-md) border border-border-strong px-3 text-sm text-text-secondary hover:text-text md:flex"
            >
              Admin
            </Link>
          ) : null}
          <SearchBar />
          <Link
            to={accountHref}
            aria-label={currentUser ? 'Account' : 'Sign in'}
            className="flex h-11 w-11 items-center justify-center rounded-(--radius-md) hover:bg-surface-raised"
          >
            <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden="true">
              <circle cx="12" cy="8" r="4" />
              <path d="M4 20c1.6-3.6 5-5.5 8-5.5s6.4 1.9 8 5.5" />
            </svg>
          </Link>
          <button
            type="button"
            onClick={openCartDrawer}
            aria-label={`Cart${itemCount > 0 ? `, ${itemCount} item${itemCount === 1 ? '' : 's'}` : ''}`}
            className="relative flex h-11 w-11 items-center justify-center rounded-(--radius-md) hover:bg-surface-raised"
          >
            <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden="true">
              <path d="M6 6h15l-1.5 9h-12z" />
              <path d="M6 6L5 3H2" />
              <circle cx="9.5" cy="20" r="1.25" fill="currentColor" stroke="none" />
              <circle cx="17.5" cy="20" r="1.25" fill="currentColor" stroke="none" />
            </svg>
            {itemCount > 0 ? (
              <span
                aria-hidden="true"
                className="absolute right-1 top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-accent px-1 text-[10px] font-medium text-accent-fg"
              >
                {itemCount}
              </span>
            ) : null}
          </button>
        </div>
      </div>

      {mobileOpen ? (
        <nav className="border-t border-border px-4 py-3 md:hidden" aria-label="Primary mobile">
          <ul className="flex flex-col gap-1">
            {navLinks.map((link) => (
              <li key={link.to}>
                <NavLink
                  to={link.to}
                  onClick={() => setMobileOpen(false)}
                  className="block rounded-(--radius-sm) px-3 py-3 text-sm text-text-secondary hover:bg-surface-raised hover:text-text"
                >
                  {link.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
      ) : null}
    </header>
  )
}
