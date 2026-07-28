import { NavLink, Navigate, Outlet } from 'react-router'
import { useCurrentUser } from '@/hooks/useAuth'
import { cn } from '@/lib/cn'

const NAV_ITEMS = [
  { label: 'Dashboard', to: '/admin' },
  { label: 'Products', to: '/admin/products' },
  { label: 'Orders', to: '/admin/orders' },
  { label: 'Users', to: '/admin/users' },
  { label: 'Coupons', to: '/admin/coupons' },
  { label: 'Reviews', to: '/admin/reviews' },
  { label: 'CMS Pages', to: '/admin/cms/pages' },
  { label: 'Banners', to: '/admin/cms/banners' },
  { label: 'Support', to: '/admin/support' },
]

export function AdminLayout() {
  const { data: user, isPending } = useCurrentUser()

  if (isPending) {
    return <div className="container-page py-24 text-center text-sm text-text-tertiary">Loading…</div>
  }

  if (!user) {
    return <Navigate to="/auth/login?next=%2Fadmin" replace />
  }

  const isStaff = user.roles.some((r) => r !== 'customer')
  if (!isStaff) {
    return <Navigate to="/" replace />
  }

  return (
    <div className="flex min-h-dvh bg-bg text-text">
      <aside className="hidden w-56 shrink-0 border-r border-border p-5 md:block">
        <p className="text-sm font-semibold tracking-tight">BLACKCART Admin</p>
        <nav aria-label="Admin" className="mt-6 flex flex-col gap-1">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/admin'}
              className={({ isActive }) =>
                cn(
                  'rounded-(--radius-md) px-3 py-2.5 text-sm text-text-secondary hover:bg-surface-raised hover:text-text',
                  isActive && 'bg-surface-raised font-medium text-text',
                )
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="mt-8 border-t border-border pt-4 text-xs text-text-tertiary">
          Signed in as {user.first_name} · {user.roles.join(', ')}
        </div>
      </aside>
      <main className="min-w-0 flex-1 p-6 md:p-8">
        <Outlet />
      </main>
    </div>
  )
}
