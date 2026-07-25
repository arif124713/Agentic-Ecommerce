import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { useApplyCoupon, useRemoveCoupon } from '@/hooks/useCart'

interface CouponInputProps {
  appliedCode: string | null
  error: string | null
}

export function CouponInput({ appliedCode, error }: CouponInputProps) {
  const [code, setCode] = useState('')
  const applyMutation = useApplyCoupon()
  const removeMutation = useRemoveCoupon()

  if (appliedCode) {
    return (
      <div className="flex items-center justify-between gap-2 rounded-(--radius-md) border border-border-strong px-3 py-2.5">
        <div>
          <p className="text-sm font-medium text-text">{appliedCode}</p>
          {error ? <p className="text-xs text-danger">{error}</p> : <p className="text-xs text-success">Applied</p>}
        </div>
        <button
          type="button"
          onClick={() => removeMutation.mutate()}
          disabled={removeMutation.isPending}
          className="text-xs font-medium text-text-secondary hover:text-text hover:underline"
        >
          Remove
        </button>
      </div>
    )
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        if (code.trim()) applyMutation.mutate(code.trim(), { onSuccess: () => setCode('') })
      }}
      className="flex gap-2"
    >
      <label htmlFor="coupon-code" className="sr-only">
        Coupon code
      </label>
      <input
        id="coupon-code"
        value={code}
        onChange={(e) => setCode(e.target.value.toUpperCase())}
        placeholder="Coupon code"
        className="h-11 flex-1 rounded-(--radius-md) border border-border bg-surface-sunken px-3 text-sm uppercase text-text placeholder:normal-case placeholder:text-text-tertiary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring"
      />
      <Button type="submit" variant="secondary" loading={applyMutation.isPending} disabled={!code.trim()}>
        Apply
      </Button>
    </form>
  )
}
