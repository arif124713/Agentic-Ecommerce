import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Link } from 'react-router'
import { useMutation } from '@tanstack/react-query'
import { AuthLayout } from './AuthLayout'
import { Input } from '@/components/ui/Input'
import { Button } from '@/components/ui/Button'
import { FormAlert } from '@/components/ui/FormAlert'
import { SeoHead } from '@/components/seo/SeoHead'
import { forgotPassword } from '@/services/auth'
import { getApiErrorMessage } from '@/services/apiClient'

const schema = z.object({
  email: z.string().min(1, 'Email is required').email('Enter a valid email address'),
})

type FormValues = z.infer<typeof schema>

export function ForgotPasswordPage() {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: { email: '' } })

  const mutation = useMutation({
    mutationFn: (values: FormValues) => forgotPassword(values.email),
  })

  if (mutation.isSuccess) {
    return (
      <AuthLayout title="Check your email">
        <FormAlert tone="success">
          If an account exists for that email, a password reset link is on its way. It may take a few minutes to
          arrive.
        </FormAlert>
        <div className="mt-6 text-center text-sm">
          <Link to="/auth/login" className="font-medium text-text hover:underline">
            Back to sign in
          </Link>
        </div>
      </AuthLayout>
    )
  }

  return (
    <>
      <SeoHead
        title="Forgot Password"
        description="Request a link to reset the password for your BlackCart account."
        path="/auth/forgot"
        noindex
      />
      <AuthLayout
      title="Forgot password"
      subtitle="Enter your email and we'll send you a link to reset it."
      footer={
        <Link to="/auth/login" className="font-medium text-text hover:underline">
          Back to sign in
        </Link>
      }
    >
      <form onSubmit={handleSubmit((values) => mutation.mutate(values))} noValidate className="flex flex-col gap-5">
        {mutation.isError ? <FormAlert>{getApiErrorMessage(mutation.error)}</FormAlert> : null}

        <Input
          label="Email"
          type="email"
          autoComplete="email"
          required
          error={errors.email?.message}
          {...register('email')}
        />

        <Button type="submit" loading={mutation.isPending} className="w-full">
          Send reset link
        </Button>
      </form>
      </AuthLayout>
    </>
  )
}
