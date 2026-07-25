import type { ReactNode } from 'react'
import { cn } from '@/lib/cn'

type Tone = 'danger' | 'success' | 'info'

const toneClasses: Record<Tone, string> = {
  danger: 'border-danger/40 bg-danger/10 text-danger',
  success: 'border-success/40 bg-success/10 text-success',
  info: 'border-info/40 bg-info/10 text-info',
}

interface FormAlertProps {
  tone?: Tone
  children: ReactNode
}

export function FormAlert({ tone = 'danger', children }: FormAlertProps) {
  return (
    <div
      role={tone === 'danger' ? 'alert' : 'status'}
      className={cn('rounded-(--radius-md) border px-4 py-3 text-sm', toneClasses[tone])}
    >
      {children}
    </div>
  )
}
