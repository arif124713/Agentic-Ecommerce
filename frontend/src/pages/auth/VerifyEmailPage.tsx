import { useEffect, useRef, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router'
import { useMutation } from '@tanstack/react-query'
import { AuthLayout } from './AuthLayout'
import { Button } from '@/components/ui/Button'
import { FormAlert } from '@/components/ui/FormAlert'
import { resendVerification, verifyEmail } from '@/services/auth'
import { getApiErrorMessage } from '@/services/apiClient'

const RESEND_COOLDOWN_SECONDS = 60

export function VerifyEmailPage() {
  const { token } = useParams<{ token?: string }>()
  const [searchParams] = useSearchParams()
  const email = searchParams.get('email')
  const [cooldown, setCooldown] = useState(0)
  const hasAttemptedRef = useRef(false)

  const [verifyStatus, setVerifyStatus] = useState<'pending' | 'success' | 'error'>('pending')
  const [verifyError, setVerifyError] = useState<unknown>(null)

  const resendMutation = useMutation({
    mutationFn: () => resendVerification(email as string),
    onSuccess: () => setCooldown(RESEND_COOLDOWN_SECONDS),
  })

  useEffect(() => {
    if (!token || hasAttemptedRef.current) return
    hasAttemptedRef.current = true
    verifyEmail(token)
      .then(() => setVerifyStatus('success'))
      .catch((error) => {
        setVerifyError(error)
        setVerifyStatus('error')
      })
  }, [token])

  useEffect(() => {
    if (cooldown <= 0) return
    const id = window.setInterval(() => setCooldown((c) => Math.max(0, c - 1)), 1000)
    return () => window.clearInterval(id)
  }, [cooldown])

  if (token) {
    if (verifyStatus === 'pending') {
      return (
        <AuthLayout title="Verifying your email">
          <p className="text-center text-sm text-text-secondary">One moment while we confirm your address…</p>
        </AuthLayout>
      )
    }

    if (verifyStatus === 'success') {
      return (
        <AuthLayout title="Email verified">
          <FormAlert tone="success">Your email address has been verified.</FormAlert>
          <Link
            to="/auth/login"
            className="mt-6 inline-flex h-11 w-full items-center justify-center rounded-(--radius-md) bg-accent text-sm font-medium text-accent-fg transition-opacity duration-150 ease-(--ease-standard) hover:opacity-90 active:opacity-80"
          >
            Continue to sign in
          </Link>
        </AuthLayout>
      )
    }

    return (
      <AuthLayout title="Verification failed">
        <FormAlert>{getApiErrorMessage(verifyError)}</FormAlert>
        <p className="mt-4 text-center text-sm text-text-secondary">
          This link may have expired. Request a new one below.
        </p>
        {email ? (
          <Button
            className="mt-4 w-full"
            loading={resendMutation.isPending}
            disabled={cooldown > 0}
            onClick={() => resendMutation.mutate()}
          >
            {cooldown > 0 ? `Resend available in ${cooldown}s` : 'Resend verification email'}
          </Button>
        ) : (
          <div className="mt-4 text-center">
            <Link to="/auth/login" className="text-sm font-medium text-text hover:underline">
              Back to sign in
            </Link>
          </div>
        )}
      </AuthLayout>
    )
  }

  return (
    <AuthLayout
      title="Check your inbox"
      subtitle={
        email ? (
          <>
            We sent a verification link to <span className="text-text">{email}</span>. Click it to activate your
            account.
          </>
        ) : (
          'We sent you a verification link. Click it to activate your account.'
        )
      }
    >
      {resendMutation.isError ? <FormAlert>{getApiErrorMessage(resendMutation.error)}</FormAlert> : null}
      {resendMutation.isSuccess ? <FormAlert tone="success">Verification email resent.</FormAlert> : null}

      {email ? (
        <Button
          className="mt-2 w-full"
          variant="secondary"
          loading={resendMutation.isPending}
          disabled={cooldown > 0}
          onClick={() => resendMutation.mutate()}
        >
          {cooldown > 0 ? `Resend available in ${cooldown}s` : "Didn't get it? Resend email"}
        </Button>
      ) : null}

      <div className="mt-6 text-center text-sm">
        <Link to="/auth/login" className="font-medium text-text hover:underline">
          Back to sign in
        </Link>
      </div>
    </AuthLayout>
  )
}
