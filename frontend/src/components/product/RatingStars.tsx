import { cn } from '@/lib/cn'

interface RatingStarsProps {
  value: number
  count?: number
  className?: string
}

export function RatingStars({ value, count, className }: RatingStarsProps) {
  return (
    <div className={cn('flex items-center gap-1', className)}>
      <span className="flex items-center gap-0.5" role="img" aria-label={`Rated ${value.toFixed(1)} out of 5`}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="var(--text)" aria-hidden="true">
          <path d="M12 2l2.9 6.6L22 9.3l-5 4.9 1.2 7L12 17.8 5.8 21.2 7 14.2 2 9.3l7.1-.7z" />
        </svg>
        <span className="text-xs text-text-secondary">{value.toFixed(1)}</span>
      </span>
      {count !== undefined ? (
        <span className="text-xs text-text-tertiary">({count.toLocaleString()})</span>
      ) : null}
    </div>
  )
}
