import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { AuthLayout } from './AuthLayout'
import { Input } from '@/components/ui/Input'
import { PasswordInput } from '@/components/ui/PasswordInput'
import { Checkbox } from '@/components/ui/Checkbox'
import { Button } from '@/components/ui/Button'
import { FormAlert } from '@/components/ui/FormAlert'
import { login } from '@/services/auth'
import { getApiErrorMessage } from '@/services/apiClient'

const schema = z.object({
  email: z.string().min(1, 'Email is required').email('Enter a valid email address'),
  password: z.string().min(1, 'Password is required'),
  remember_me: z.boolean().optional(),
})

type FormValues = z.infer<typeof schema>

export function LoginPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const queryClient = useQueryClient()

  const {
    register,
    handleSubmit,
    setFocus,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { email: '', password: '', remember_me: false },
  })

  const mutation = useMutation({
    mutationFn: login,
    onSuccess: (user) => {
      queryClient.setQueryData(['auth', 'me'], user)
      toast.success(`Welcome back, ${user.first_name}`)
      const next = searchParams.get('next')
      navigate(next && next.startsWith('/') ? next : '/account', { replace: true })
    },
    onError: () => {
      setFocus('email')
    },
  })

  return (
    <AuthLayout
      title="Sign in"
      subtitle="Welcome back. Enter your details to continue."
      footer={
        <>
          Don&apos;t have an account?{' '}
          <Link to="/auth/register" className="font-medium text-text hover:underline">
            Create one
          </Link>
        </>
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

        <div>
          <PasswordInput
            label="Password"
            autoComplete="current-password"
            required
            error={errors.password?.message}
            {...register('password')}
          />
          <div className="mt-2 text-right">
            <Link to="/auth/forgot" className="text-sm text-text-secondary hover:text-text hover:underline">
              Forgot password?
            </Link>
          </div>
        </div>

        <Checkbox label="Remember me on this device" {...register('remember_me')} />

        <Button type="submit" loading={mutation.isPending} className="w-full">
          Sign in
        </Button>
      </form>
    </AuthLayout>
  )
}
