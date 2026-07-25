import type { ReactNode } from 'react'
import { Link } from 'react-router'

interface AuthLayoutProps {
  title: string
  subtitle?: ReactNode
  children: ReactNode
  footer?: ReactNode
}

export function AuthLayout({ title, subtitle, children, footer }: AuthLayoutProps) {
  return (
    <div className="container-page flex min-h-[calc(100dvh-4rem)] items-center justify-center py-12">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <Link to="/" className="text-lg font-semibold tracking-tight">
            BLACKCART
          </Link>
        </div>
        <h1 className="text-center text-3xl font-semibold tracking-tight">{title}</h1>
        {subtitle ? <p className="mt-2 text-center text-sm text-text-secondary">{subtitle}</p> : null}
        <div className="mt-8">{children}</div>
        {footer ? <div className="mt-6 text-center text-sm text-text-secondary">{footer}</div> : null}
      </div>
    </div>
  )
}
