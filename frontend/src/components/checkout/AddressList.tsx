import type { Address } from '@/types/address'
import { cn } from '@/lib/cn'

interface AddressListProps {
  addresses: Address[]
  selectedId: number | null
  onSelect: (id: number) => void
}

export function AddressList({ addresses, selectedId, onSelect }: AddressListProps) {
  return (
    <div role="radiogroup" aria-label="Shipping address" className="flex flex-col gap-3">
      {addresses.map((address) => {
        const checked = address.id === selectedId
        return (
          <label
            key={address.id}
            className={cn(
              'flex min-h-11 cursor-pointer items-start gap-3 rounded-(--radius-md) border p-4 text-sm',
              checked ? 'border-white' : 'border-border-strong hover:border-text-tertiary',
            )}
          >
            <input
              type="radio"
              name="shipping-address"
              checked={checked}
              onChange={() => onSelect(address.id)}
              className="mt-1 h-4 w-4 shrink-0 accent-white"
            />
            <span>
              <span className="block font-medium text-text">
                {address.recipient_name}
                {address.is_default_shipping ? (
                  <span className="ml-2 rounded-full bg-surface-raised px-2 py-0.5 text-xs font-normal text-text-tertiary">
                    Default
                  </span>
                ) : null}
              </span>
              <span className="mt-0.5 block text-text-secondary">
                {address.street_line1}
                {address.street_line2 ? `, ${address.street_line2}` : ''}, {address.city}, {address.division}
                {address.postal_code ? ` ${address.postal_code}` : ''}
              </span>
              <span className="mt-0.5 block text-text-tertiary">{address.phone}</span>
            </span>
          </label>
        )
      })}
    </div>
  )
}
