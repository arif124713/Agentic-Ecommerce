import { cn } from '@/lib/cn'

function scorePassword(password: string): number {
  if (!password) return 0
  let score = 0
  if (password.length >= 12) score++
  if (password.length >= 16) score++
  if (/[a-z]/.test(password) && /[A-Z]/.test(password)) score++
  if (/\d/.test(password)) score++
  if (/[^A-Za-z0-9]/.test(password)) score++
  return Math.min(score, 4)
}

const LABELS = ['Too weak', 'Weak', 'Fair', 'Good', 'Strong']
const BAR_COLORS = ['bg-danger', 'bg-danger', 'bg-warning', 'bg-info', 'bg-success']

interface PasswordStrengthMeterProps {
  password: string
}

export function PasswordStrengthMeter({ password }: PasswordStrengthMeterProps) {
  if (!password) return null
  const score = scorePassword(password)

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex gap-1" aria-hidden="true">
        {[0, 1, 2, 3].map((i) => (
          <span
            key={i}
            className={cn('h-1 flex-1 rounded-full bg-border transition-colors duration-150', i < score && BAR_COLORS[score])}
          />
        ))}
      </div>
      <p className="text-xs text-text-tertiary" aria-live="polite">
        {LABELS[score]} — use 12+ characters with a mix of letters, numbers &amp; symbols
      </p>
    </div>
  )
}
