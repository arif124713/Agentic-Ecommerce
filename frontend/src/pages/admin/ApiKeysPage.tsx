import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { createApiKey, listApiKeys, revokeApiKey } from '@/services/admin/apiKeys'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { FormAlert } from '@/components/ui/FormAlert'
import { Skeleton } from '@/components/feedback/Skeleton'
import { EmptyState, ErrorState } from '@/components/feedback/EmptyState'
import { getApiErrorMessage } from '@/services/apiClient'
import { SeoHead } from '@/components/seo/SeoHead'

function NewKeyForm({ onCreated }: { onCreated: (rawKey: string) => void }) {
  const queryClient = useQueryClient()
  const [name, setName] = useState('')
  const [scopes, setScopes] = useState('')
  const [ipAllowlist, setIpAllowlist] = useState('')

  const mutation = useMutation({
    mutationFn: () =>
      createApiKey({
        name: name.trim(),
        scopes: scopes
          .split(',')
          .map((s) => s.trim())
          .filter(Boolean),
        ip_allowlist: ipAllowlist.trim()
          ? ipAllowlist
              .split(',')
              .map((s) => s.trim())
              .filter(Boolean)
          : null,
      }),
    onSuccess: (created) => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'api-keys'] })
      onCreated(created.raw_key)
    },
  })

  return (
    <form
      className="mt-4 flex flex-col gap-3 rounded-(--radius-lg) border border-border p-4"
      onSubmit={(e) => {
        e.preventDefault()
        if (!name.trim() || !scopes.trim()) return
        mutation.mutate()
      }}
    >
      {mutation.isError ? <FormAlert>{getApiErrorMessage(mutation.error)}</FormAlert> : null}
      <Input label="Name" required value={name} onChange={(e) => setName(e.target.value)} placeholder="Reporting bot" />
      <Input
        label="Scopes (comma-separated permission codes)"
        required
        value={scopes}
        onChange={(e) => setScopes(e.target.value)}
        placeholder="catalog:product:read, order:order:read_all"
        hint="iam:* and system:* permissions can never be granted to an API key."
      />
      <Input
        label="IP allowlist (optional, comma-separated)"
        value={ipAllowlist}
        onChange={(e) => setIpAllowlist(e.target.value)}
        placeholder="203.0.113.5, 198.51.100.0/24"
      />
      <div className="flex gap-2">
        <Button type="submit" size="sm" loading={mutation.isPending}>
          Create key
        </Button>
      </div>
    </form>
  )
}

export function ApiKeysPage() {
  const [showNew, setShowNew] = useState(false)
  const [justCreated, setJustCreated] = useState<string | null>(null)
  const queryClient = useQueryClient()
  const query = useQuery({ queryKey: ['admin', 'api-keys'], queryFn: listApiKeys })

  const revokeMutation = useMutation({
    mutationFn: revokeApiKey,
    onSuccess: () => {
      toast.success('API key revoked.')
      queryClient.invalidateQueries({ queryKey: ['admin', 'api-keys'] })
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  })

  return (
    <div>
      <SeoHead
        title="API Keys"
        description="Create and manage machine credentials for BlackCart's admin API."
        path="/admin/api-keys"
        noindex
      />
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Admin API keys</h1>
          <p className="mt-1 text-sm text-text-tertiary">
            Machine credentials for admin endpoints, sent as an X-API-Key header. Never displayed again after
            creation.
          </p>
        </div>
        {!showNew && !justCreated ? <Button onClick={() => setShowNew(true)}>+ New key</Button> : null}
      </div>

      {justCreated ? (
        <div className="mt-4 rounded-(--radius-lg) border border-border p-4">
          <FormAlert tone="success">
            Copy this key now — it won&apos;t be shown again.
          </FormAlert>
          <p className="mt-3 break-all rounded-(--radius-md) bg-surface-raised px-3 py-2 font-mono text-sm">
            {justCreated}
          </p>
          <Button
            size="sm"
            className="mt-3"
            onClick={() => {
              setJustCreated(null)
              setShowNew(false)
            }}
          >
            Done
          </Button>
        </div>
      ) : showNew ? (
        <NewKeyForm onCreated={(rawKey) => setJustCreated(rawKey)} />
      ) : null}

      {query.isError ? (
        <div className="mt-8">
          <ErrorState message={getApiErrorMessage(query.error)} onRetry={() => query.refetch()} />
        </div>
      ) : query.isLoading || !query.data ? (
        <div className="mt-6 space-y-2">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
      ) : query.data.length === 0 ? (
        <div className="mt-8">
          <EmptyState title="No API keys yet" />
        </div>
      ) : (
        <div className="mt-6 flex flex-col divide-y divide-border rounded-(--radius-lg) border border-border">
          {query.data.map((key) => (
            <div key={key.public_id} className="flex items-center justify-between gap-4 px-5 py-4">
              <div className="min-w-0">
                <p className="text-sm font-medium text-text">
                  {key.name}{' '}
                  <span className="font-mono text-xs text-text-tertiary">{key.key_prefix}…</span>
                  {key.revoked_at ? (
                    <span className="ml-2 rounded-full bg-surface-raised px-2 py-0.5 text-xs text-text-tertiary">
                      Revoked
                    </span>
                  ) : null}
                </p>
                <p className="mt-1 truncate text-xs text-text-tertiary">{key.scopes.join(', ')}</p>
                <p className="mt-1 text-xs text-text-tertiary">
                  Last used {key.last_used_at ? new Date(key.last_used_at).toLocaleString() : 'never'}
                </p>
              </div>
              {!key.revoked_at ? (
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={() => revokeMutation.mutate(key.public_id)}
                  loading={revokeMutation.isPending}
                >
                  Revoke
                </Button>
              ) : null}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
