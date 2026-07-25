import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { Button } from '@/components/ui/Button'
import { subscribeStockAlert } from '@/services/discovery'
import { getApiErrorMessage } from '@/services/apiClient'
import { useCurrentUser } from '@/hooks/useAuth'

interface NotifyMeFormProps {
  productSlug: string
  variantId: number
}

export function NotifyMeForm({ productSlug, variantId }: NotifyMeFormProps) {
  const { data: user } = useCurrentUser()
  const [email, setEmail] = useState('')
  const [done, setDone] = useState(false)

  const mutation = useMutation({
    mutationFn: (payload: { variant_id: number; email?: string }) => subscribeStockAlert(productSlug, payload),
    onSuccess: () => {
      setDone(true)
      toast.success("We'll email you when it's back in stock")
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  })

  if (done) {
    return <p className="mt-3 text-sm text-success">You&rsquo;re on the list — we&rsquo;ll email you when this is back.</p>
  }

  if (user) {
    return (
      <Button
        type="button"
        variant="secondary"
        size="lg"
        className="mt-3 w-full"
        loading={mutation.isPending}
        onClick={() => mutation.mutate({ variant_id: variantId })}
      >
        Notify me when back in stock
      </Button>
    )
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        if (email.trim()) mutation.mutate({ variant_id: variantId, email: email.trim() })
      }}
      className="mt-3 flex gap-2"
    >
      <label htmlFor="stock-alert-email" className="sr-only">
        Email address
      </label>
      <input
        id="stock-alert-email"
        type="email"
        required
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="you@example.com"
        className="h-11 flex-1 rounded-(--radius-md) border border-border bg-surface-sunken px-3 text-sm text-text placeholder:text-text-tertiary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring"
      />
      <Button type="submit" variant="secondary" loading={mutation.isPending} disabled={!email.trim()}>
        Notify me
      </Button>
    </form>
  )
}
