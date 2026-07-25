import { type ButtonHTMLAttributes, forwardRef } from 'react'
import { cn } from '@/lib/cn'

type Variant = 'primary' | 'secondary' | 'ghost' | 'destructive'
type Size = 'sm' | 'md' | 'lg'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
  loading?: boolean
}

const variantClasses: Record<Variant, string> = {
  primary: 'bg-accent text-accent-fg hover:opacity-90 active:opacity-80',
  secondary: 'bg-transparent text-text border border-border-strong hover:bg-surface-raised',
  ghost: 'bg-transparent text-text-secondary hover:text-text hover:bg-surface-raised',
  destructive: 'bg-transparent text-danger border border-danger/40 hover:bg-danger/10',
}

const sizeClasses: Record<Size, string> = {
  sm: 'h-9 px-3 text-sm',
  md: 'h-11 px-5 text-sm',
  lg: 'h-12 px-6 text-base',
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'primary', size = 'md', loading, disabled, children, ...props }, ref) => {
    return (
      <button
        ref={ref}
        disabled={disabled || loading}
        className={cn(
          'relative inline-flex items-center justify-center rounded-(--radius-md) font-medium',
          'transition-[opacity,background-color,color] duration-150 ease-(--ease-standard)',
          'disabled:opacity-40 disabled:cursor-not-allowed',
          'min-w-11',
          variantClasses[variant],
          sizeClasses[size],
          className,
        )}
        {...props}
      >
        {loading ? (
          <span
            className="absolute h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent"
            aria-hidden="true"
          />
        ) : null}
        <span className={cn(loading && 'opacity-0')}>{children}</span>
      </button>
    )
  },
)
Button.displayName = 'Button'
