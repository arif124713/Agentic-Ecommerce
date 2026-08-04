import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import axios from 'axios'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { AuthLayout } from './AuthLayout'
import { Input } from '@/components/ui/Input'
import { PasswordInput } from '@/components/ui/PasswordInput'
import { Checkbox } from '@/components/ui/Checkbox'
import { Button } from '@/components/ui/Button'
import { FormAlert } from '@/components/ui/FormAlert'
import { SeoHead } from '@/components/seo/SeoHead'
import { login, mfaLoginVerify } from '@/services/auth'
import { getApiErrorMessage } from '@/services/apiClient'
import type { ApiErrorPayload } from '@/services/apiClient'
import type { AuthUser } from '@/types/auth'

const schema = z.object({
  email: z.string().min(1, 'Email is required').email('Enter a valid email address'),
  password: z.string().min(1, 'Password is required'),
  remember_me: z.boolean().optional(),
})

type FormValues = z.infer<typeof schema>

function MfaStep({ challengeToken, onSuccess }: { challengeToken: string; onSuccess: (user: AuthUser) => void }) {
  const [useRecoveryCode, setUseRecoveryCode] = useState(false)
  const [value, setValue] = useState('')

  const mutation = useMutation({
    mutationFn: () =>
      mfaLoginVerify(challengeToken, useRecoveryCode ? { recovery_code: value.trim() } : { code: value.trim() }),
    onSuccess,
  })

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        if (value.trim()) mutation.mutate()
      }}
      className="flex flex-col gap-5"
    >
      {mutation.isError ? <FormAlert>{getApiErrorMessage(mutation.error)}</FormAlert> : null}

      <Input
        label={useRecoveryCode ? 'Recovery code' : 'Authenticator code'}
        autoComplete="one-time-code"
        autoFocus
        value={value}
        onChange={(e) => setValue(e.target.value)}
      />

      <button
        type="button"
        onClick={() => {
          setUseRecoveryCode((v) => !v)
          setValue('')
        }}
        className="self-start text-sm text-text-secondary hover:text-text hover:underline"
      >
        {useRecoveryCode ? 'Use your authenticator app instead' : 'Use a recovery code instead'}
      </button>

      <Button type="submit" loading={mutation.isPending} className="w-full">
        Verify and sign in
      </Button>
    </form>
  )
}

export function LoginPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const queryClient = useQueryClient()
  const [mfaChallengeToken, setMfaChallengeToken] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    setFocus,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { email: '', password: '', remember_me: false },
  })

  function handleSignedIn(user: AuthUser) {
    queryClient.setQueryData(['auth', 'me'], user)
    toast.success(`Welcome back, ${user.first_name}`)
    const next = searchParams.get('next')
    navigate(next && next.startsWith('/') ? next : '/account', { replace: true })
  }

  const mutation = useMutation({
    mutationFn: login,
    onSuccess: handleSignedIn,
    onError: (error) => {
      const payload = axios.isAxiosError(error) ? (error.response?.data as ApiErrorPayload | undefined) : undefined
      if (payload?.error?.code === 'MFA_REQUIRED' && axios.isAxiosError(error)) {
        const challenge = error.response?.headers['x-mfa-challenge'] as string | undefined
        if (challenge) {
          setMfaChallengeToken(challenge)
          return
        }
      }
      setFocus('email')
    },
  })

  if (mfaChallengeToken) {
    return (
      <AuthLayout title="Two-factor authentication" subtitle="Enter the code from your authenticator app.">
        <MfaStep challengeToken={mfaChallengeToken} onSuccess={handleSignedIn} />
      </AuthLayout>
    )
  }

  return (
    <>
      <SeoHead
        title="Sign In"
        description="Sign in to your BlackCart account to track orders and manage your profile."
        path="/auth/login"
        noindex
      />
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
    </>
  )
}
