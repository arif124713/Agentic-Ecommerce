import { forwardRef, useId, useState, type InputHTMLAttributes } from 'react'
import { cn } from '@/lib/cn'

interface PasswordInputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label: string
  error?: string
  hint?: string
}

export const PasswordInput = forwardRef<HTMLInputElement, PasswordInputProps>(
  ({ label, error, hint, id, required, className, name, ...props }, ref) => {
    const [visible, setVisible] = useState(false)
    const autoId = useId()
    const inputId = id ?? name ?? autoId
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
        <div className="relative">
          <input
            ref={ref}
            id={inputId}
            name={name}
            type={visible ? 'text' : 'password'}
            required={required}
            aria-invalid={error ? true : undefined}
            aria-describedby={describedBy}
            className={cn(
              'h-11 w-full rounded-(--radius-md) border bg-surface-sunken px-3 pr-11 text-sm text-text placeholder:text-text-tertiary',
              'transition-colors duration-150 ease-(--ease-standard)',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring',
              error ? 'border-danger' : 'border-border',
              className,
            )}
            {...props}
          />
          <button
            type="button"
            onClick={() => setVisible((v) => !v)}
            aria-label={visible ? 'Hide password' : 'Show password'}
            aria-pressed={visible}
            className="absolute right-0 top-0 flex h-11 w-11 items-center justify-center text-text-tertiary hover:text-text"
          >
            {visible ? (
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden="true">
                <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z" />
                <circle cx="12" cy="12" r="3" />
              </svg>
            ) : (
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden="true">
                <path d="M3 3l18 18" />
                <path d="M10.6 5.2A10.9 10.9 0 0112 5c6.5 0 10 7 10 7a13.2 13.2 0 01-3.1 3.9M6.6 6.6C4 8.3 2 12 2 12s3.5 7 10 7a10.4 10.4 0 004.4-.9" />
                <path d="M9.9 9.9a3 3 0 104.2 4.2" />
              </svg>
            )}
          </button>
        </div>
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
PasswordInput.displayName = 'PasswordInput'
