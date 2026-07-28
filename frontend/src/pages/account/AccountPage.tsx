import { Link, useNavigate } from 'react-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { cn } from '@/lib/cn'
import { Button } from '@/components/ui/Button'
import { useCurrentUser } from '@/hooks/useAuth'
import { listSessions, logout, logoutAll, revokeSession } from '@/services/auth'

const NAV_ITEMS = [
  { label: 'Profile', href: null },
  { label: 'Orders', href: '/account/orders' },
  { label: 'Addresses', href: null },
  { label: 'Wishlist', href: '/account/wishlist' },
  { label: 'Settings', href: null },
  { label: 'Support', href: '/account/support' },
]

export function AccountPage() {
  const { data: user } = useCurrentUser()
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  const sessionsQuery = useQuery({
    queryKey: ['auth', 'sessions'],
    queryFn: listSessions,
    retry: false,
  })

  const logoutMutation = useMutation({
    mutationFn: logout,
    onSuccess: () => {
      queryClient.setQueryData(['auth', 'me'], null)
      navigate('/', { replace: true })
    },
  })

  const logoutAllMutation = useMutation({
    mutationFn: logoutAll,
    onSuccess: () => {
      queryClient.setQueryData(['auth', 'me'], null)
      navigate('/auth/login', { replace: true })
    },
  })

  const revokeMutation = useMutation({
    mutationFn: revokeSession,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['auth', 'sessions'] }),
  })

  if (!user) return null

  return (
    <div className="container-page py-10">
      <h1 className="text-3xl font-semibold tracking-tight">Account</h1>

      <div className="mt-8 grid gap-8 md:grid-cols-[240px_1fr]">
        <nav aria-label="Account" className="flex flex-row gap-1 overflow-x-auto md:flex-col md:overflow-visible">
          {NAV_ITEMS.map((item, i) =>
            item.href ? (
              <Link
                key={item.label}
                to={item.href}
                className="shrink-0 rounded-(--radius-md) px-4 py-3 text-sm text-text-secondary hover:bg-surface-raised hover:text-text"
              >
                {item.label}
              </Link>
            ) : (
              <span
                key={item.label}
                className={cn(
                  'shrink-0 rounded-(--radius-md) px-4 py-3 text-sm',
                  i === 0 ? 'bg-surface-raised text-text' : 'text-text-tertiary',
                )}
              >
                {item.label}
                {i > 0 ? ' (soon)' : ''}
              </span>
            ),
          )}
        </nav>

        <div className="flex flex-col gap-8">
          <section className="rounded-(--radius-lg) border border-border p-6">
            <h2 className="text-xs font-medium uppercase tracking-wide text-text-tertiary">Profile</h2>
            <div className="mt-4 flex flex-col gap-1">
              <p className="text-base font-medium">
                {user.first_name} {user.last_name ?? ''}
              </p>
              <p className="text-sm text-text-secondary">{user.email}</p>
              <p className="text-sm text-text-tertiary">
                {user.email_verified_at ? 'Email verified' : 'Email not verified'}
              </p>
            </div>
          </section>

          <section className="rounded-(--radius-lg) border border-border p-6">
            <div className="flex items-center justify-between gap-4">
              <h2 className="text-xs font-medium uppercase tracking-wide text-text-tertiary">Active sessions</h2>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => logoutAllMutation.mutate()}
                loading={logoutAllMutation.isPending}
              >
                Sign out everywhere
              </Button>
            </div>

            <div className="mt-4">
              {sessionsQuery.isLoading ? (
                <p className="text-sm text-text-tertiary">Loading sessions…</p>
              ) : sessionsQuery.isError ? (
                <p className="text-sm text-text-tertiary">Session history isn&apos;t available yet.</p>
              ) : sessionsQuery.data && sessionsQuery.data.length > 0 ? (
                <ul className="flex flex-col divide-y divide-border">
                  {sessionsQuery.data.map((session) => (
                    <li key={session.id} className="flex items-center justify-between gap-4 py-3">
                      <div>
                        <p className="text-sm text-text">
                          {session.device_label ?? 'Unknown device'}
                          {session.is_current ? (
                            <span className="ml-2 rounded-full bg-surface-raised px-2 py-0.5 text-xs text-text-tertiary">
                              This device
                            </span>
                          ) : null}
                        </p>
                        <p className="text-xs text-text-tertiary">
                          {session.ip ?? 'Unknown IP'} · last active{' '}
                          {new Date(session.last_used_at ?? session.created_at).toLocaleString()}
                        </p>
                      </div>
                      {!session.is_current ? (
                        <Button
                          variant="destructive"
                          size="sm"
                          onClick={() => revokeMutation.mutate(session.id)}
                          loading={revokeMutation.isPending}
                        >
                          Revoke
                        </Button>
                      ) : null}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-text-tertiary">No other active sessions.</p>
              )}
            </div>
          </section>

          <div>
            <Button variant="secondary" onClick={() => logoutMutation.mutate()} loading={logoutMutation.isPending}>
              Sign out
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
