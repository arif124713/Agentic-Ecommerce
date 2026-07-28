import { useParams } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { getCmsPage } from '@/services/cms'
import { EmptyState } from '@/components/feedback/EmptyState'
import { Skeleton } from '@/components/feedback/Skeleton'
import { SeoHead } from '@/components/seo/SeoHead'

export function CmsPage() {
  const { slug = '' } = useParams<{ slug: string }>()
  const query = useQuery({
    queryKey: ['cms', 'page', slug],
    queryFn: () => getCmsPage(slug),
    retry: false,
  })

  if (query.isLoading) {
    return (
      <div className="container-page max-w-2xl py-10">
        <Skeleton className="h-9 w-2/3" />
        <Skeleton className="mt-6 h-4 w-full" />
        <Skeleton className="mt-2 h-4 w-5/6" />
      </div>
    )
  }

  if (query.isError) {
    return (
      <div className="container-page max-w-2xl py-10">
        <EmptyState title="Page not found" description="This page doesn't exist or hasn't been published yet." />
      </div>
    )
  }

  const page = query.data!

  return (
    <div className="container-page max-w-2xl py-10">
      <SeoHead
        title={page.seo_title ?? page.title}
        description={page.seo_description ?? page.title}
        path={`/pages/${page.slug}`}
      />
      <h1 className="text-3xl font-semibold tracking-tight text-text">{page.title}</h1>
      {/* Trusted content: body is admin-authored only (cms:page:write is RBAC-gated), never
          user-submitted — same trust boundary as any other admin-entered catalogue content. */}
      <div
        className="prose prose-invert mt-8 max-w-none text-text-secondary [&_a]:text-text [&_a]:underline [&_h2]:mt-6 [&_h2]:text-xl [&_h2]:font-semibold [&_h2]:text-text [&_p]:leading-relaxed"
        // eslint-disable-next-line react/no-danger
        dangerouslySetInnerHTML={{ __html: page.body }}
      />
    </div>
  )
}
