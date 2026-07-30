import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { createFeatureFlag, listFeatureFlags, updateFeatureFlag } from '@/services/admin/featureFlags'
import { Button } from '@/components/ui/Button'
import { Checkbox } from '@/components/ui/Checkbox'
import { FormAlert } from '@/components/ui/FormAlert'
import { Skeleton } from '@/components/feedback/Skeleton'
import { EmptyState, ErrorState } from '@/components/feedback/EmptyState'
import { getApiErrorMessage } from '@/services/apiClient'

function NewFlagForm({ onDone }: { onDone: () => void }) {
  const queryClient = useQueryClient()
  const [key, setKey] = useState('')
  const [description, setDescription] = useState('')

  const mutation = useMutation({
    mutationFn: () => createFeatureFlag({ key: key.trim(), enabled: false, rollout_percent: 0, description: description.trim() || null }),
    onSuccess: () => {
      toast.success('Flag created.')
      queryClient.invalidateQueries({ queryKey: ['admin', 'feature-flags'] })
      onDone()
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  })

  return (
    <form
      className="mt-4 flex flex-col gap-3 rounded-(--radius-lg) border border-border p-4"
      onSubmit={(e) => {
        e.preventDefault()
        if (!key.trim()) return
        mutation.mutate()
      }}
    >
      {mutation.isError ? <FormAlert>{getApiErrorMessage(mutation.error)}</FormAlert> : null}
      <input
        value={key}
        onChange={(e) => setKey(e.target.value)}
        placeholder="key (e.g. promo.flash_sale)"
        className="h-10 rounded-(--radius-md) border border-border bg-surface-sunken px-3 text-sm text-text placeholder:text-text-tertiary"
      />
      <input
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        placeholder="Description (optional)"
        className="h-10 rounded-(--radius-md) border border-border bg-surface-sunken px-3 text-sm text-text placeholder:text-text-tertiary"
      />
      <div className="flex gap-2">
        <Button type="submit" size="sm" loading={mutation.isPending}>
          Create
        </Button>
        <Button type="button" size="sm" variant="ghost" onClick={onDone}>
          Cancel
        </Button>
      </div>
    </form>
  )
}

export function FeatureFlagsPage() {
  const [showNew, setShowNew] = useState(false)
  const queryClient = useQueryClient()
  const query = useQuery({ queryKey: ['admin', 'feature-flags'], queryFn: listFeatureFlags })

  const toggleMutation = useMutation({
    mutationFn: (vars: { key: string; enabled: boolean; rollout_percent: number }) =>
      updateFeatureFlag(vars.key, { enabled: vars.enabled, rollout_percent: vars.rollout_percent }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin', 'feature-flags'] }),
    onError: (error) => toast.error(getApiErrorMessage(error)),
  })

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Feature flags</h1>
          <p className="mt-1 text-sm text-text-tertiary">
            No Redis cache in this setup — every read is fresh, changes apply on the next request.
          </p>
        </div>
        {!showNew ? <Button onClick={() => setShowNew(true)}>+ New flag</Button> : null}
      </div>

      {showNew ? <NewFlagForm onDone={() => setShowNew(false)} /> : null}

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
          <EmptyState title="No feature flags yet" />
        </div>
      ) : (
        <div className="mt-6 flex flex-col divide-y divide-border rounded-(--radius-lg) border border-border">
          {query.data.map((flag) => (
            <div key={flag.key} className="flex items-center justify-between gap-4 px-5 py-4">
              <div>
                <p className="font-mono text-sm font-medium text-text">{flag.key}</p>
                {flag.description ? <p className="text-xs text-text-tertiary">{flag.description}</p> : null}
              </div>
              <div className="flex items-center gap-4">
                <label className="flex items-center gap-2 text-xs text-text-secondary">
                  Rollout
                  <input
                    type="number"
                    min={0}
                    max={100}
                    defaultValue={flag.rollout_percent}
                    onBlur={(e) => {
                      const value = Number(e.target.value)
                      if (value !== flag.rollout_percent) {
                        toggleMutation.mutate({ key: flag.key, enabled: flag.enabled, rollout_percent: value })
                      }
                    }}
                    className="h-8 w-16 rounded-(--radius-md) border border-border bg-surface-sunken px-2 text-sm text-text"
                  />
                  %
                </label>
                <Checkbox
                  label="Enabled"
                  checked={flag.enabled}
                  onChange={(e) =>
                    toggleMutation.mutate({ key: flag.key, enabled: e.target.checked, rollout_percent: flag.rollout_percent })
                  }
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
