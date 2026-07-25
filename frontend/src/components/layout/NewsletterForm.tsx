import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { subscribeNewsletter } from '@/services/discovery'
import { getApiErrorMessage } from '@/services/apiClient'

export function NewsletterForm() {
  const [email, setEmail] = useState('')
  const [subscribed, setSubscribed] = useState(false)

  const mutation = useMutation({
    mutationFn: subscribeNewsletter,
    onSuccess: () => {
      setSubscribed(true)
      setEmail('')
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  })

  if (subscribed) {
    return <p className="mt-3 text-sm text-success">You&rsquo;re subscribed.</p>
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        if (email.trim()) mutation.mutate(email.trim())
      }}
      className="mt-3 flex gap-2"
    >
      <label htmlFor="newsletter-email" className="sr-only">
        Email address
      </label>
      <input
        id="newsletter-email"
        type="email"
        required
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="you@example.com"
        className="h-11 min-w-0 flex-1 rounded-(--radius-md) border border-border bg-surface-sunken px-3 text-sm text-text placeholder:text-text-tertiary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring"
      />
      <button
        type="submit"
        disabled={!email.trim() || mutation.isPending}
        className="h-11 shrink-0 rounded-(--radius-md) border border-border-strong px-4 text-sm text-text hover:bg-surface-raised disabled:opacity-40"
      >
        {mutation.isPending ? '…' : 'Join'}
      </button>
    </form>
  )
}
