import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Link, useLocation, useNavigate, useParams } from 'react-router'
import { useMutation } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { AuthLayout } from './AuthLayout'
import { PasswordInput } from '@/components/ui/PasswordInput'
import { Button } from '@/components/ui/Button'
import { FormAlert } from '@/components/ui/FormAlert'
import { PasswordStrengthMeter } from '@/components/auth/PasswordStrengthMeter'
import { SeoHead } from '@/components/seo/SeoHead'
import { resetPassword } from '@/services/auth'
import { getApiErrorMessage } from '@/services/apiClient'

const schema = z
  .object({
    password: z.string().min(12, 'Use at least 12 characters').max(128),
    confirm_password: z.string().min(1, 'Please confirm your password'),
  })
  .refine((data) => data.password === data.confirm_password, {
    message: 'Passwords do not match',
    path: ['confirm_password'],
  })

type FormValues = z.infer<typeof schema>

export function ResetPasswordPage() {
  const { token } = useParams<{ token: string }>()
  const navigate = useNavigate()
  const location = useLocation()

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: { password: '', confirm_password: '' } })

  const mutation = useMutation({
    mutationFn: (values: FormValues) => resetPassword(token as string, values.password),
    onSuccess: () => {
      toast.success('Password updated. Please sign in again.')
      navigate('/auth/login', { replace: true })
    },
  })

  if (!token) {
    return (
      <AuthLayout title="Invalid link" subtitle="This password reset link is invalid or has expired.">
        <div className="text-center text-sm">
          <Link to="/auth/forgot" className="font-medium text-text hover:underline">
            Request a new link
          </Link>
        </div>
      </AuthLayout>
    )
  }

  return (
    <>
      <SeoHead
        title="Reset Password"
        description="Choose a new password for your BlackCart account."
        path={location.pathname}
        noindex
      />
      <AuthLayout title="Reset password" subtitle="Choose a new password for your account.">
      <form onSubmit={handleSubmit((values) => mutation.mutate(values))} noValidate className="flex flex-col gap-5">
        {mutation.isError ? <FormAlert>{getApiErrorMessage(mutation.error)}</FormAlert> : null}

        <div>
          <PasswordInput
            label="New password"
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
          label="Confirm new password"
          autoComplete="new-password"
          required
          error={errors.confirm_password?.message}
          {...register('confirm_password')}
        />

        <Button type="submit" loading={mutation.isPending} className="w-full">
          Update password
        </Button>
      </form>
      </AuthLayout>
    </>
  )
}
