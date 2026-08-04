import { useEffect } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createCoupon, deactivateCoupon, getCoupon, updateCoupon } from '@/services/admin/coupons'
import { Input } from '@/components/ui/Input'
import { Checkbox } from '@/components/ui/Checkbox'
import { Button } from '@/components/ui/Button'
import { FormAlert } from '@/components/ui/FormAlert'
import { Skeleton } from '@/components/feedback/Skeleton'
import { getApiErrorMessage } from '@/services/apiClient'
import { SeoHead } from '@/components/seo/SeoHead'

// z.coerce.number() runs before .optional() ever sees the value, and Number('') is 0 rather
// than NaN — so a blank optional field silently became a stored 0 instead of null. Since the
// backend treats usage_limit_total/usage_limit_per_user of 0 as "0 uses allowed" (immediately
// exhausted) and max_discount_amount of 0 as "cap every discount at ₹0", that turned every
// coupon created with these fields left blank into a permanently unusable coupon. Preprocessing
// '' to undefined before coercion restores the intended "unlimited/no cap" meaning of blank.
const optionalNumber = z.preprocess(
  (val) => (val === '' || val === undefined || val === null ? undefined : val),
  z.coerce.number().optional(),
)
const optionalInt = z.preprocess(
  (val) => (val === '' || val === undefined || val === null ? undefined : val),
  z.coerce.number().int().optional(),
)

const schema = z.object({
  code: z.string().min(1, 'Code is required').max(40),
  description: z.string().optional(),
  discount_type: z.enum(['percent', 'fixed', 'free_shipping']),
  discount_value: z.coerce.number().min(0),
  max_discount_amount: optionalNumber,
  min_order_amount: optionalNumber,
  usage_limit_total: optionalInt,
  usage_limit_per_user: optionalInt,
  stackable: z.boolean().optional(),
  is_active: z.boolean().optional(),
})

// See ProductFormPage for why z.coerce.number() needs both the input and output types here.
type FormInput = z.input<typeof schema>
type FormValues = z.output<typeof schema>

export function CouponFormPage() {
  const { id } = useParams()
  const isNew = !id || id === 'new'
  const couponId = isNew ? null : Number(id)
  const navigate = useNavigate()
  const location = useLocation()
  const queryClient = useQueryClient()

  const couponQuery = useQuery({
    queryKey: ['admin', 'coupons', couponId],
    queryFn: () => getCoupon(couponId!),
    enabled: couponId !== null,
  })

  const {
    register,
    handleSubmit,
    reset,
    watch,
    formState: { errors },
  } = useForm<FormInput, unknown, FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { discount_type: 'percent', discount_value: 10, is_active: true, stackable: false },
  })

  useEffect(() => {
    if (couponQuery.data) {
      const c = couponQuery.data
      reset({
        code: c.code,
        description: c.description ?? '',
        discount_type: c.discount_type,
        discount_value: Number(c.discount_value),
        max_discount_amount: c.max_discount_amount ? Number(c.max_discount_amount) : undefined,
        min_order_amount: c.min_order_amount ? Number(c.min_order_amount) : undefined,
        usage_limit_total: c.usage_limit_total ?? undefined,
        usage_limit_per_user: c.usage_limit_per_user ?? undefined,
        stackable: c.stackable,
        is_active: c.is_active,
      })
    }
  }, [couponQuery.data, reset])

  const saveMutation = useMutation({
    mutationFn: (values: FormValues) => {
      const payload = {
        code: values.code,
        description: values.description || null,
        discount_type: values.discount_type,
        discount_value: String(values.discount_value),
        max_discount_amount: values.max_discount_amount != null ? String(values.max_discount_amount) : null,
        min_order_amount: values.min_order_amount != null ? String(values.min_order_amount) : null,
        usage_limit_total: values.usage_limit_total ?? null,
        usage_limit_per_user: values.usage_limit_per_user ?? null,
        stackable: values.stackable ?? false,
        is_active: values.is_active ?? true,
        starts_at: null,
        expires_at: null,
      }
      return isNew ? createCoupon(payload) : updateCoupon(couponId!, payload)
    },
    onSuccess: (coupon) => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'coupons'] })
      if (isNew) navigate(`/admin/coupons/${coupon.id}`, { replace: true })
    },
  })

  const deactivateMutation = useMutation({
    mutationFn: () => deactivateCoupon(couponId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'coupons'] })
      navigate('/admin/coupons')
    },
  })

  const discountType = watch('discount_type')

  if (!isNew && couponQuery.isLoading) {
    return <Skeleton className="h-72 w-full" />
  }

  return (
    <div className="max-w-lg">
      <SeoHead
        title={isNew ? 'New Coupon' : 'Edit Coupon'}
        description="Create or edit a discount coupon for the BlackCart storefront."
        path={location.pathname}
        noindex
      />
      <h1 className="text-2xl font-semibold tracking-tight">{isNew ? 'New coupon' : couponQuery.data?.code}</h1>

      <form onSubmit={handleSubmit((values) => saveMutation.mutate(values))} noValidate className="mt-6 flex flex-col gap-5">
        {saveMutation.isError ? <FormAlert>{getApiErrorMessage(saveMutation.error)}</FormAlert> : null}
        {saveMutation.isSuccess ? <FormAlert tone="success">Saved.</FormAlert> : null}

        <Input label="Code" required error={errors.code?.message} {...register('code')} />
        <Input label="Description" error={errors.description?.message} {...register('description')} />

        <div className="flex flex-col gap-1.5">
          <label htmlFor="discount_type" className="text-sm font-medium text-text">
            Discount type
          </label>
          <select
            id="discount_type"
            className="h-11 rounded-(--radius-md) border border-border bg-surface-sunken px-3 text-sm text-text"
            {...register('discount_type')}
          >
            <option value="percent">Percent off</option>
            <option value="fixed">Fixed amount off</option>
            <option value="free_shipping">Free shipping</option>
          </select>
        </div>

        {discountType !== 'free_shipping' ? (
          <div className="grid grid-cols-2 gap-4">
            <Input
              label={discountType === 'percent' ? 'Discount (%)' : 'Discount amount'}
              type="number"
              step="0.01"
              error={errors.discount_value?.message}
              {...register('discount_value')}
            />
            <Input label="Max discount (optional)" type="number" step="0.01" {...register('max_discount_amount')} />
          </div>
        ) : null}

        <div className="grid grid-cols-2 gap-4">
          <Input label="Minimum order amount (optional)" type="number" step="0.01" {...register('min_order_amount')} />
          <Input label="Total usage limit (optional)" type="number" {...register('usage_limit_total')} />
        </div>
        <Input label="Per-user usage limit (optional)" type="number" {...register('usage_limit_per_user')} />

        <div className="flex flex-wrap gap-6">
          <Checkbox label="Stackable with other coupons" {...register('stackable')} />
          <Checkbox label="Active" {...register('is_active')} />
        </div>

        <div className="flex items-center gap-3">
          <Button type="submit" loading={saveMutation.isPending}>
            {isNew ? 'Create coupon' : 'Save changes'}
          </Button>
          {!isNew && couponQuery.data?.is_active ? (
            <Button type="button" variant="destructive" loading={deactivateMutation.isPending} onClick={() => deactivateMutation.mutate()}>
              Deactivate
            </Button>
          ) : null}
        </div>
      </form>
    </div>
  )
}
