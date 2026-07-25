import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Input } from '@/components/ui/Input'
import { Checkbox } from '@/components/ui/Checkbox'
import { Button } from '@/components/ui/Button'
import type { AddressInput } from '@/types/address'

const schema = z.object({
  recipient_name: z.string().min(1, 'Recipient name is required').max(120),
  phone: z.string().min(1, 'Phone number is required').max(24),
  division: z.string().min(1, 'Division is required').max(80),
  district: z.string().max(80).optional(),
  city: z.string().min(1, 'City is required').max(80),
  area: z.string().max(80).optional(),
  postal_code: z.string().max(16).optional(),
  street_line1: z.string().min(1, 'Street address is required').max(255),
  street_line2: z.string().max(255).optional(),
  landmark: z.string().max(255).optional(),
  label: z.string().max(40).optional(),
  is_default_shipping: z.boolean().optional(),
  is_default_billing: z.boolean().optional(),
})

type FormValues = z.infer<typeof schema>

interface AddressFormProps {
  onSubmit: (payload: AddressInput) => void
  isSubmitting?: boolean
  onCancel?: () => void
}

export function AddressForm({ onSubmit, isSubmitting, onCancel }: AddressFormProps) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { is_default_shipping: true, is_default_billing: true },
  })

  return (
    <form
      onSubmit={handleSubmit((values) =>
        onSubmit({
          ...values,
          district: values.district || null,
          area: values.area || null,
          postal_code: values.postal_code || null,
          street_line2: values.street_line2 || null,
          landmark: values.landmark || null,
          label: values.label || null,
          is_default_shipping: values.is_default_shipping ?? false,
          is_default_billing: values.is_default_billing ?? false,
        }),
      )}
      noValidate
      className="flex flex-col gap-4"
    >
      <div className="grid grid-cols-2 gap-4">
        <Input label="Full name" required error={errors.recipient_name?.message} {...register('recipient_name')} />
        <Input label="Phone" type="tel" required error={errors.phone?.message} {...register('phone')} />
      </div>
      <Input label="Street address" required error={errors.street_line1?.message} {...register('street_line1')} />
      <Input label="Apartment, suite, etc. (optional)" error={errors.street_line2?.message} {...register('street_line2')} />
      <div className="grid grid-cols-2 gap-4">
        <Input label="City" required error={errors.city?.message} {...register('city')} />
        <Input label="Area (optional)" error={errors.area?.message} {...register('area')} />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <Input label="Division" required error={errors.division?.message} {...register('division')} />
        <Input label="Postal code (optional)" error={errors.postal_code?.message} {...register('postal_code')} />
      </div>
      <Input label="Landmark (optional)" error={errors.landmark?.message} {...register('landmark')} />
      <Checkbox label="Set as default address" {...register('is_default_shipping')} />

      <div className="mt-2 flex gap-3">
        <Button type="submit" loading={isSubmitting}>
          Save address
        </Button>
        {onCancel ? (
          <Button type="button" variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
        ) : null}
      </div>
    </form>
  )
}
