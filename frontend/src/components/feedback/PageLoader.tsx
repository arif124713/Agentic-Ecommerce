import { Skeleton } from '@/components/feedback/Skeleton'

/** Suspense fallback for lazy-loaded route chunks (see app/router.tsx) — kept intentionally
 * generic (not page-shaped) since it briefly covers every route, not just one page type. */
export function PageLoader() {
  return (
    <div className="container-page space-y-4 py-16" aria-busy="true" aria-live="polite">
      <span className="sr-only">Loading…</span>
      <Skeleton className="h-6 w-40" />
      <Skeleton className="h-40 w-full" />
      <Skeleton className="h-40 w-full" />
    </div>
  )
}
