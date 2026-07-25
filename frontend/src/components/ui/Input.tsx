import { forwardRef, type InputHTMLAttributes } from 'react'
import { cn } from '@/lib/cn'

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string
  error?: string
  hint?: string
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, hint, id, required, className, name, ...props }, ref) => {
    const inputId = id ?? name
    const hintId = hint && !error ? `${inputId}-hint` : undefined
    const errorId = error ? `${inputId}-error` : undefined
    const describedBy = [hintId, errorId].filter(Boolean).join(' ') || undefined

    return (
      <div className="flex flex-col gap-1.5">
        <label htmlFor={inputId} className="text-sm font-medium text-text">
          {label}
          {required ? (
            <span className="text-danger" aria-hidden="true">
              {' '}
              *
            </span>
          ) : null}
        </label>
        <input
          ref={ref}
          id={inputId}
          name={name}
          required={required}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          className={cn(
            'h-11 w-full rounded-(--radius-md) border bg-surface-sunken px-3 text-sm text-text placeholder:text-text-tertiary',
            'transition-colors duration-150 ease-(--ease-standard)',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring',
            error ? 'border-danger' : 'border-border',
            className,
          )}
          {...props}
        />
        {hintId ? (
          <p id={hintId} className="text-xs text-text-tertiary">
            {hint}
          </p>
        ) : null}
        {errorId ? (
          <p id={errorId} role="alert" className="text-xs text-danger">
            {error}
          </p>
        ) : null}
      </div>
    )
  },
)
Input.displayName = 'Input'
