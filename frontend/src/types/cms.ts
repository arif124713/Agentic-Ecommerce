export interface CmsPage {
  slug: string
  title: string
  body: string
  seo_title: string | null
  seo_description: string | null
  published_at: string | null
}

export interface Banner {
  id: number
  placement: string
  title: string
  image_url: string
  link_url: string | null
  sort_order: number
}
