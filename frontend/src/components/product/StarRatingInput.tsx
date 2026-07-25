import { useState } from 'react'
import { cn } from '@/lib/cn'

interface StarRatingInputProps {
  value: number
  onChange: (value: number) => void
  label?: string
}

const STAR_PATH = 'M12 2l2.9 6.6L22 9.3l-5 4.9 1.2 7L12 17.8 5.8 21.2 7 14.2 2 9.3l7.1-.7z'

export function StarRatingInput({ value, onChange, label = 'Rating' }: StarRatingInputProps) {
  const [hovered, setHovered] = useState<number | null>(null)
  const display = hovered ?? value

  return (
    <div role="radiogroup" aria-label={label} className="flex items-center gap-1">
      {[1, 2, 3, 4, 5].map((star) => (
        <button
          key={star}
          type="button"
          role="radio"
          aria-checked={value === star}
          aria-label={`${star} star${star === 1 ? '' : 's'}`}
          onClick={() => onChange(star)}
          onMouseEnter={() => setHovered(star)}
          onMouseLeave={() => setHovered(null)}
          onFocus={() => setHovered(star)}
          onBlur={() => setHovered(null)}
          className="flex h-11 w-11 items-center justify-center rounded-(--radius-md) focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring"
        >
          <svg
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill={star <= display ? 'var(--text)' : 'none'}
            stroke="var(--text-tertiary)"
            strokeWidth="1.5"
            aria-hidden="true"
            className={cn('transition-colors duration-150 ease-(--ease-standard)')}
          >
            <path d={STAR_PATH} />
          </svg>
        </button>
      ))}
    </div>
  )
}
