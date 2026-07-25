import type { ProductDetail } from '@/types/catalog'

function absoluteUrl(path: string): string {
  if (typeof window === 'undefined') return path
  return new URL(path, window.location.origin).toString()
}

export function organizationAndWebsiteSchema() {
  const site = typeof window !== 'undefined' ? window.location.origin : ''
  return [
    {
      '@context': 'https://schema.org',
      '@type': 'Organization',
      name: 'BlackCart',
      url: site,
    },
    {
      '@context': 'https://schema.org',
      '@type': 'WebSite',
      name: 'BlackCart',
      url: site,
      potentialAction: {
        '@type': 'SearchAction',
        target: `${site}/search?q={search_term_string}`,
        'query-input': 'required name=search_term_string',
      },
    },
  ]
}

export function breadcrumbListSchema(items: { name: string; path: string }[]) {
  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: items.map((item, i) => ({
      '@type': 'ListItem',
      position: i + 1,
      name: item.name,
      item: absoluteUrl(item.path),
    })),
  }
}

export function productSchema(product: ProductDetail) {
  const primaryImage = product.images.find((i) => i.is_primary) ?? product.images[0]
  return {
    '@context': 'https://schema.org',
    '@type': 'Product',
    name: product.title,
    description: product.description ?? product.title,
    image: primaryImage ? [primaryImage.url] : undefined,
    brand: { '@type': 'Brand', name: product.brand.name },
    sku: product.variants[0]?.sku,
    aggregateRating: product.rating_avg
      ? {
          '@type': 'AggregateRating',
          ratingValue: product.rating_avg,
          reviewCount: product.review_count || product.rating_count,
        }
      : undefined,
    offers: {
      '@type': 'Offer',
      url: absoluteUrl(`/p/${product.slug}`),
      priceCurrency: product.currency,
      price: product.price,
      availability: product.variants.some((v) => v.available > 0)
        ? 'https://schema.org/InStock'
        : 'https://schema.org/OutOfStock',
    },
  }
}

export function itemListSchema(products: { title: string; slug: string }[]) {
  return {
    '@context': 'https://schema.org',
    '@type': 'ItemList',
    itemListElement: products.map((p, i) => ({
      '@type': 'ListItem',
      position: i + 1,
      url: absoluteUrl(`/p/${p.slug}`),
      name: p.title,
    })),
  }
}
