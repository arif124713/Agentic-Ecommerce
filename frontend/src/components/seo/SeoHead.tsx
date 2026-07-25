/**
 * Per-page SEO metadata (spec §20). React 19 hoists <title>/<meta>/<link> rendered anywhere in
 * the tree up into <head> automatically — no react-helmet or similar needed. JSON-LD structured
 * data is rendered as a plain inline <script> (valid anywhere in the DOM, not just <head>, per
 * how crawlers actually parse it) via a defensively-escaped dangerouslySetInnerHTML: the payload
 * is always JSON we built ourselves, never raw user input, but a product title containing a
 * literal "</script>" sequence could otherwise break out of the tag, so "<" is escaped to its
 * unicode form first (the standard JSON-LD XSS mitigation).
 */
export interface SeoHeadProps {
  title: string
  description: string
  path: string
  image?: string | null
  type?: 'website' | 'product' | 'article'
  noindex?: boolean
  structuredData?: object | object[]
}

function toAbsoluteUrl(path: string): string {
  if (typeof window === 'undefined') return path
  return new URL(path, window.location.origin).toString()
}

function safeJsonLd(data: object): string {
  return JSON.stringify(data).replace(/</g, '\\u003c')
}

export function SeoHead({ title, description, path, image, type = 'website', noindex, structuredData }: SeoHeadProps) {
  const url = toAbsoluteUrl(path)
  const fullTitle = title.includes('BlackCart') ? title : `${title} | BlackCart`
  const entries = Array.isArray(structuredData) ? structuredData : structuredData ? [structuredData] : []

  return (
    <>
      <title>{fullTitle}</title>
      <meta name="description" content={description} />
      <link rel="canonical" href={url} />
      {noindex ? <meta name="robots" content="noindex, nofollow" /> : null}

      <meta property="og:site_name" content="BlackCart" />
      <meta property="og:title" content={fullTitle} />
      <meta property="og:description" content={description} />
      <meta property="og:type" content={type === 'product' ? 'product' : 'website'} />
      <meta property="og:url" content={url} />
      {image ? <meta property="og:image" content={toAbsoluteUrl(image)} /> : null}

      <meta name="twitter:card" content={image ? 'summary_large_image' : 'summary'} />
      <meta name="twitter:title" content={fullTitle} />
      <meta name="twitter:description" content={description} />
      {image ? <meta name="twitter:image" content={toAbsoluteUrl(image)} /> : null}

      {entries.map((data, i) => (
        // eslint-disable-next-line react/no-danger
        <script key={i} type="application/ld+json" dangerouslySetInnerHTML={{ __html: safeJsonLd(data) }} />
      ))}
    </>
  )
}
