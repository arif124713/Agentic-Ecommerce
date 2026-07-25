import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Link, useNavigate } from 'react-router'
import { useMutation } from '@tanstack/react-query'
import { AuthLayout } from './AuthLayout'
import { Input } from '@/components/ui/Input'
import { PasswordInput } from '@/components/ui/PasswordInput'
import { Checkbox } from '@/components/ui/Checkbox'
import { Button } from '@/components/ui/Button'
import { FormAlert } from '@/components/ui/FormAlert'
import { PasswordStrengthMeter } from '@/components/auth/PasswordStrengthMeter'
import { registerAccount } from '@/services/auth'
import { getApiErrorMessage } from '@/services/apiClient'

const schema = z
  .object({
    first_name: z.string().min(1, 'First name is required').max(80),
    last_name: z.string().max(80).optional(),
    email: z.string().min(1, 'Email is required').email('Enter a valid email address'),
    password: z.string().min(12, 'Use at least 12 characters').max(128),
    confirm_password: z.string().min(1, 'Please confirm your password'),
    marketing_opt_in: z.boolean().optional(),
    accept_terms: z.boolean().refine((v) => v === true, { message: 'You must accept the terms to continue' }),
  })
  .refine((data) => data.password === data.confirm_password, {
    message: 'Passwords do not match',
    path: ['confirm_password'],
  })

type FormValues = z.infer<typeof schema>

export function RegisterPage() {
  const navigate = useNavigate()

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      first_name: '',
      last_name: '',
      email: '',
      password: '',
      confirm_password: '',
      marketing_opt_in: false,
      accept_terms: false,
    },
  })

  const mutation = useMutation({
    mutationFn: (values: FormValues) =>
      registerAccount({
        first_name: values.first_name,
        last_name: values.last_name || undefined,
        email: values.email,
        password: values.password,
        marketing_opt_in: values.marketing_opt_in,
      }),
    onSuccess: (_, values) => {
      navigate(`/auth/verify?email=${encodeURIComponent(values.email)}`, { replace: true })
    },
  })

  return (
    <AuthLayout
      title="Create your account"
      subtitle="Join BlackCart to check out faster and track your orders."
      footer={
        <>
          Already have an account?{' '}
          <Link to="/auth/login" className="font-medium text-text hover:underline">
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={handleSubmit((values) => mutation.mutate(values))} noValidate className="flex flex-col gap-5">
        {mutation.isError ? <FormAlert>{getApiErrorMessage(mutation.error)}</FormAlert> : null}

        <div className="grid grid-cols-2 gap-4">
          <Input
            label="First name"
            autoComplete="given-name"
            required
            error={errors.first_name?.message}
            {...register('first_name')}
          />
          <Input label="Last name" autoComplete="family-name" error={errors.last_name?.message} {...register('last_name')} />
        </div>

        <Input
          label="Email"
          type="email"
          autoComplete="email"
          required
          error={errors.email?.message}
          {...register('email')}
        />

        <div>
          <PasswordInput
            label="Password"
            autoComplete="new-password"
            required
            error={errors.password?.message}
            {...register('password')}
          />
          <div className="mt-2">
            <PasswordStrengthMeter password={watch('password')} />
          </div>
        </div>

        <PasswordInput
          label="Confirm password"
          autoComplete="new-password"
          required
          error={errors.confirm_password?.message}
          {...register('confirm_password')}
        />

        <div className="flex flex-col gap-3">
          <Checkbox
            label={
              <>
                I agree to the{' '}
                <Link to="/pages/terms" className="font-medium text-text hover:underline">
                  Terms of Service
                </Link>{' '}
                and{' '}
                <Link to="/pages/privacy" className="font-medium text-text hover:underline">
                  Privacy Policy
                </Link>
              </>
            }
            error={errors.accept_terms?.message}
            {...register('accept_terms')}
          />
          <Checkbox label="Send me offers and product updates" {...register('marketing_opt_in')} />
        </div>

        <Button type="submit" loading={mutation.isPending} className="w-full">
          Create account
        </Button>
      </form>
    </AuthLayout>
  )
}
