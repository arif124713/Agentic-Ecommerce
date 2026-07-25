import { Input } from '@/components/ui/Input'
import { cn } from '@/lib/cn'

export type PaymentMethod = 'card' | 'cod'

interface PaymentMethodSelectorProps {
  method: PaymentMethod
  onMethodChange: (method: PaymentMethod) => void
  cardNumber: string
  onCardNumberChange: (value: string) => void
  cardError?: string
}

const OPTIONS: { value: PaymentMethod; label: string; description: string }[] = [
  { value: 'card', label: 'Credit / debit card', description: 'Simulated payment — no real charge' },
  { value: 'cod', label: 'Cash on delivery', description: 'Pay when your order arrives' },
]

export function PaymentMethodSelector({
  method,
  onMethodChange,
  cardNumber,
  onCardNumberChange,
  cardError,
}: PaymentMethodSelectorProps) {
  return (
    <div className="flex flex-col gap-3">
      <div role="radiogroup" aria-label="Payment method" className="flex flex-col gap-3">
        {OPTIONS.map((option) => {
          const checked = option.value === method
          return (
            <label
              key={option.value}
              className={cn(
                'flex min-h-11 cursor-pointer items-center gap-3 rounded-(--radius-md) border p-4 text-sm',
                checked ? 'border-white' : 'border-border-strong hover:border-text-tertiary',
              )}
            >
              <input
                type="radio"
                name="payment-method"
                checked={checked}
                onChange={() => onMethodChange(option.value)}
                className="h-4 w-4 shrink-0 accent-white"
              />
              <span>
                <span className="block font-medium text-text">{option.label}</span>
                <span className="block text-text-tertiary">{option.description}</span>
              </span>
            </label>
          )
        })}
      </div>

      {method === 'card' ? (
        <div className="rounded-(--radius-md) border border-border p-4">
          <Input
            label="Card number"
            inputMode="numeric"
            placeholder="4242 4242 4242 4242"
            value={cardNumber}
            onChange={(e) => onCardNumberChange(e.target.value)}
            error={cardError}
            hint="Simulator: 4242 4242 4242 4242 succeeds. 4000 0000 0000 0002 is declined."
          />
        </div>
      ) : null}
    </div>
  )
}
