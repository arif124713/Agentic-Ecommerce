import { forwardRef, type InputHTMLAttributes, type ReactNode } from 'react'
import { useId } from 'react'
import { cn } from '@/lib/cn'

interface CheckboxProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label: ReactNode
  error?: string
}

export const Checkbox = forwardRef<HTMLInputElement, CheckboxProps>(
  ({ label, error, id, name, className, ...props }, ref) => {
    const autoId = useId()
    const inputId = id ?? name ?? autoId

    return (
      <div>
        <label htmlFor={inputId} className="flex min-h-11 cursor-pointer items-start gap-3 text-sm text-text-secondary">
          <input
            ref={ref}
            id={inputId}
            name={name}
            type="checkbox"
            aria-invalid={error ? true : undefined}
            className={cn(
              'mt-0.5 h-4 w-4 shrink-0 rounded-sm border-border-strong accent-white',
              className,
            )}
            {...props}
          />
          <span>{label}</span>
        </label>
        {error ? (
          <p role="alert" className="mt-1 text-xs text-danger">
            {error}
          </p>
        ) : null}
      </div>
    )
  },
)
Checkbox.displayName = 'Checkbox'
