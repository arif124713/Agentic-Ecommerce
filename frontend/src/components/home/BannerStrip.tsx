import { Link } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { getBanners } from '@/services/cms'

interface BannerStripProps {
  placement: string
}

/** Renders nothing if the placement has no active banners — same convention as ProductRail,
 * an empty merchandising slot is not an error state worth showing anything for. */
export function BannerStrip({ placement }: BannerStripProps) {
  const query = useQuery({
    queryKey: ['banners', placement],
    queryFn: () => getBanners(placement),
    staleTime: 5 * 60 * 1000,
  })

  const banners = query.data ?? []
  if (banners.length === 0) return null

  return (
    <section className="container-page py-8">
      <div className="flex gap-4 overflow-x-auto pb-2" style={{ scrollbarWidth: 'thin' }}>
        {banners.map((banner) => {
          const content = (
            <img
              src={banner.image_url}
              alt={banner.title}
              className="h-40 w-full rounded-(--radius-lg) object-cover sm:h-48"
            />
          )
          const isExternal = banner.link_url?.startsWith('http')

          return (
            <div key={banner.id} className="w-72 shrink-0 sm:w-96">
              {banner.link_url ? (
                isExternal ? (
                  <a href={banner.link_url} aria-label={banner.title} target="_blank" rel="noreferrer">
                    {content}
                  </a>
                ) : (
                  <Link to={banner.link_url} aria-label={banner.title}>
                    {content}
                  </Link>
                )
              ) : (
                content
              )}
            </div>
          )
        })}
      </div>
    </section>
  )
}
