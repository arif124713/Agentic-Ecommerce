import { useState } from 'react'
import { Link, useLocation, useParams } from 'react-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { assignRole, getAdminUser, reactivateUser, revokeRole, suspendUser } from '@/services/admin/users'
import { getApiErrorMessage } from '@/services/apiClient'
import { Button } from '@/components/ui/Button'
import { FormAlert } from '@/components/ui/FormAlert'
import { Skeleton } from '@/components/feedback/Skeleton'
import { ErrorState } from '@/components/feedback/EmptyState'
import { ROLE_CODES } from '@/types/admin'
import { SeoHead } from '@/components/seo/SeoHead'

export function UserDetailPage() {
  const { publicId } = useParams()
  const location = useLocation()
  const queryClient = useQueryClient()
  const [roleToAdd, setRoleToAdd] = useState('')
  const [suspendReason, setSuspendReason] = useState('')
  const [showSuspendForm, setShowSuspendForm] = useState(false)

  const query = useQuery({
    queryKey: ['admin', 'users', 'detail', publicId],
    queryFn: () => getAdminUser(publicId!),
    enabled: Boolean(publicId),
  })

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['admin', 'users', 'detail', publicId] })
    queryClient.invalidateQueries({ queryKey: ['admin', 'users'] })
  }

  const assignMutation = useMutation({
    mutationFn: () => assignRole(publicId!, roleToAdd),
    onSuccess: () => {
      invalidate()
      setRoleToAdd('')
    },
  })
  const revokeMutation = useMutation({
    mutationFn: (role: string) => revokeRole(publicId!, role),
    onSuccess: invalidate,
  })
  const suspendMutation = useMutation({
    mutationFn: () => suspendUser(publicId!, suspendReason || undefined),
    onSuccess: () => {
      invalidate()
      setShowSuspendForm(false)
    },
  })
  const reactivateMutation = useMutation({
    mutationFn: () => reactivateUser(publicId!),
    onSuccess: invalidate,
  })

  if (query.isError) {
    return <ErrorState message={getApiErrorMessage(query.error)} onRetry={() => query.refetch()} />
  }
  if (query.isLoading || !query.data) {
    return <Skeleton className="h-64 w-full" />
  }

  const user = query.data
  const assignableRoles = ROLE_CODES.filter((r) => !user.roles.includes(r))

  return (
    <div className="max-w-2xl">
      <SeoHead
        title="User Details"
        description="View and manage a BlackCart customer's roles and account access."
        path={location.pathname}
        noindex
      />
      <Link to="/admin/users" className="text-sm text-text-secondary hover:text-text hover:underline">
        ← All users
      </Link>

      <h1 className="mt-4 text-2xl font-semibold tracking-tight">
        {user.first_name} {user.last_name ?? ''}
      </h1>
      <p className="mt-1 text-sm text-text-secondary">{user.email}</p>

      <div className="mt-6 rounded-(--radius-lg) border border-border p-5 text-sm">
        <dl className="grid grid-cols-2 gap-3">
          <div>
            <dt className="text-text-tertiary">Status</dt>
            <dd className="text-text capitalize">{user.status}</dd>
          </div>
          <div>
            <dt className="text-text-tertiary">Email verified</dt>
            <dd className="text-text">{user.email_verified_at ? 'Yes' : 'No'}</dd>
          </div>
          <div>
            <dt className="text-text-tertiary">Last login</dt>
            <dd className="text-text">{user.last_login_at ? new Date(user.last_login_at).toLocaleString() : 'Never'}</dd>
          </div>
          <div>
            <dt className="text-text-tertiary">Joined</dt>
            <dd className="text-text">{new Date(user.created_at).toLocaleDateString()}</dd>
          </div>
        </dl>
      </div>

      <section className="mt-8">
        <h2 className="text-xs font-medium uppercase tracking-wide text-text-tertiary">Roles</h2>
        {assignMutation.isError ? (
          <div className="mt-2">
            <FormAlert>{getApiErrorMessage(assignMutation.error)}</FormAlert>
          </div>
        ) : null}
        <ul className="mt-3 flex flex-wrap gap-2">
          {user.roles.map((role) => (
            <li
              key={role}
              className="flex items-center gap-2 rounded-full border border-border-strong px-3 py-1.5 text-sm text-text"
            >
              {role}
              {role !== 'customer' ? (
                <button
                  type="button"
                  onClick={() => revokeMutation.mutate(role)}
                  aria-label={`Remove ${role} role`}
                  className="text-text-tertiary hover:text-danger"
                >
                  ×
                </button>
              ) : null}
            </li>
          ))}
        </ul>
        <div className="mt-3 flex gap-2">
          <select
            value={roleToAdd}
            onChange={(e) => setRoleToAdd(e.target.value)}
            aria-label="Role to add"
            className="h-10 rounded-(--radius-md) border border-border bg-surface-sunken px-3 text-sm text-text"
          >
            <option value="">Add a role…</option>
            {assignableRoles.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
          <Button size="sm" disabled={!roleToAdd} loading={assignMutation.isPending} onClick={() => assignMutation.mutate()}>
            Add
          </Button>
        </div>
      </section>

      <section className="mt-8">
        <h2 className="text-xs font-medium uppercase tracking-wide text-text-tertiary">Account access</h2>
        {suspendMutation.isError ? (
          <div className="mt-2">
            <FormAlert>{getApiErrorMessage(suspendMutation.error)}</FormAlert>
          </div>
        ) : null}
        <div className="mt-3">
          {user.status === 'suspended' ? (
            <Button variant="secondary" loading={reactivateMutation.isPending} onClick={() => reactivateMutation.mutate()}>
              Reactivate account
            </Button>
          ) : showSuspendForm ? (
            <div className="flex flex-col gap-3">
              <input
                value={suspendReason}
                onChange={(e) => setSuspendReason(e.target.value)}
                placeholder="Reason (optional)"
                className="h-10 w-72 rounded-(--radius-md) border border-border bg-surface-sunken px-3 text-sm text-text placeholder:text-text-tertiary"
              />
              <div className="flex gap-2">
                <Button variant="destructive" loading={suspendMutation.isPending} onClick={() => suspendMutation.mutate()}>
                  Confirm suspend
                </Button>
                <Button variant="ghost" onClick={() => setShowSuspendForm(false)}>
                  Cancel
                </Button>
              </div>
            </div>
          ) : (
            <Button variant="destructive" onClick={() => setShowSuspendForm(true)}>
              Suspend account
            </Button>
          )}
        </div>
      </section>
    </div>
  )
}
