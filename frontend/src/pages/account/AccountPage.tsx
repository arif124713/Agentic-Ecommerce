import { useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { cn } from '@/lib/cn'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { FormAlert } from '@/components/ui/FormAlert'
import { useCurrentUser } from '@/hooks/useAuth'
import { SeoHead } from '@/components/seo/SeoHead'
import {
  listSessions,
  logout,
  logoutAll,
  mfaDisable,
  mfaEnable,
  mfaSetup,
  revokeSession,
} from '@/services/auth'
import { getApiErrorMessage } from '@/services/apiClient'
import type { MfaSetup } from '@/types/auth'

function MfaSection({ mfaEnabled }: { mfaEnabled: boolean }) {
  const queryClient = useQueryClient()
  const [setup, setSetup] = useState<MfaSetup | null>(null)
  const [code, setCode] = useState('')
  const [recoveryCodes, setRecoveryCodes] = useState<string[] | null>(null)
  const [showDisable, setShowDisable] = useState(false)
  const [disablePassword, setDisablePassword] = useState('')
  const [disableCode, setDisableCode] = useState('')

  const setupMutation = useMutation({
    mutationFn: mfaSetup,
    onSuccess: (data) => setSetup(data),
    onError: (error) => toast.error(getApiErrorMessage(error)),
  })

  const enableMutation = useMutation({
    mutationFn: () => mfaEnable(code.trim()),
    onSuccess: (result) => {
      setRecoveryCodes(result.recovery_codes)
      setSetup(null)
      setCode('')
      queryClient.invalidateQueries({ queryKey: ['auth', 'me'] })
    },
  })

  const disableMutation = useMutation({
    mutationFn: () => mfaDisable(disablePassword, disableCode),
    onSuccess: () => {
      toast.success('Two-factor authentication disabled.')
      setShowDisable(false)
      setDisablePassword('')
      setDisableCode('')
      queryClient.invalidateQueries({ queryKey: ['auth', 'me'] })
    },
  })

  if (recoveryCodes) {
    return (
      <section className="rounded-(--radius-lg) border border-border p-6">
        <h2 className="text-xs font-medium uppercase tracking-wide text-text-tertiary">Two-factor authentication</h2>
        <div className="mt-4">
          <FormAlert tone="success">
            Two-factor authentication is now enabled. Save these recovery codes somewhere safe — each one can be
            used once if you lose access to your authenticator app, and they won&apos;t be shown again.
          </FormAlert>
        </div>
        <ul className="mt-4 grid grid-cols-2 gap-2 font-mono text-sm">
          {recoveryCodes.map((rc) => (
            <li key={rc} className="rounded-(--radius-md) bg-surface-raised px-3 py-2">
              {rc}
            </li>
          ))}
        </ul>
        <Button className="mt-4" size="sm" onClick={() => setRecoveryCodes(null)}>
          Done
        </Button>
      </section>
    )
  }

  return (
    <section className="rounded-(--radius-lg) border border-border p-6">
      <h2 className="text-xs font-medium uppercase tracking-wide text-text-tertiary">Two-factor authentication</h2>

      {mfaEnabled ? (
        <div className="mt-4">
          <p className="text-sm text-text-secondary">Two-factor authentication is enabled on your account.</p>
          {!showDisable ? (
            <Button variant="destructive" size="sm" className="mt-3" onClick={() => setShowDisable(true)}>
              Disable
            </Button>
          ) : (
            <form
              className="mt-4 flex max-w-sm flex-col gap-3"
              onSubmit={(e) => {
                e.preventDefault()
                disableMutation.mutate()
              }}
            >
              {disableMutation.isError ? <FormAlert>{getApiErrorMessage(disableMutation.error)}</FormAlert> : null}
              <Input
                label="Password"
                type="password"
                autoComplete="current-password"
                required
                value={disablePassword}
                onChange={(e) => setDisablePassword(e.target.value)}
              />
              <Input
                label="Authenticator code"
                required
                value={disableCode}
                onChange={(e) => setDisableCode(e.target.value)}
              />
              <div className="flex gap-2">
                <Button type="submit" variant="destructive" size="sm" loading={disableMutation.isPending}>
                  Confirm disable
                </Button>
                <Button type="button" variant="ghost" size="sm" onClick={() => setShowDisable(false)}>
                  Cancel
                </Button>
              </div>
            </form>
          )}
        </div>
      ) : setup ? (
        <form
          className="mt-4 flex max-w-sm flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault()
            enableMutation.mutate()
          }}
        >
          {enableMutation.isError ? <FormAlert>{getApiErrorMessage(enableMutation.error)}</FormAlert> : null}
          <p className="text-sm text-text-secondary">
            Scan this QR code with your authenticator app, then enter the 6-digit code it shows.
          </p>
          <img
            src={setup.qr_data_uri}
            alt="Two-factor authentication QR code"
            className="h-40 w-40 self-start rounded-(--radius-md) border border-border"
          />
          <p className="text-xs text-text-tertiary">
            Or enter this key manually: <span className="font-mono">{setup.secret}</span>
          </p>
          <Input label="6-digit code" required value={code} onChange={(e) => setCode(e.target.value)} />
          <div className="flex gap-2">
            <Button type="submit" size="sm" loading={enableMutation.isPending}>
              Confirm and enable
            </Button>
            <Button type="button" variant="ghost" size="sm" onClick={() => setSetup(null)}>
              Cancel
            </Button>
          </div>
        </form>
      ) : (
        <div className="mt-4">
          <p className="text-sm text-text-secondary">Add an extra layer of security using an authenticator app.</p>
          <Button size="sm" className="mt-3" onClick={() => setupMutation.mutate()} loading={setupMutation.isPending}>
            Enable two-factor authentication
          </Button>
        </div>
      )}
    </section>
  )
}

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
      // Calling order alone doesn't fix this — React batches both the router-state update and
      // the React Query cache notification into the same pass regardless of which line runs
      // first. The setTimeout defers clearing the cached user until after navigate('/')'s update
      // has actually committed and unmounted this ProtectedRoute-wrapped page; without it,
      // AccountPage briefly re-renders with a null user while still mounted, and ProtectedRoute's
      // own "no user -> redirect to login" guard wins the race, landing signed-out users on a
      // login prompt instead of home (caught by an E2E test, not by unit tests — a timing race).
      navigate('/', { replace: true })
      setTimeout(() => queryClient.setQueryData(['auth', 'me'], null), 0)
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
      <SeoHead
        title="Your Account"
        description="Manage your BlackCart profile, security settings, and active sessions."
        path="/account"
        noindex
      />
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

          <MfaSection mfaEnabled={user.mfa_enabled} />

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
