import { apiClient } from '../apiClient'
import type { Envelope } from '@/types/catalog'

export interface AdminCmsPage {
  id: number
  slug: string
  title: string
  body: string
  status: 'draft' | 'published'
  seo_title: string | null
  seo_description: string | null
  published_at: string | null
  is_deleted: boolean
}

export interface CmsPageInput {
  slug: string
  title: string
  body: string
  status: 'draft' | 'published'
  seo_title?: string | null
  seo_description?: string | null
}

export interface AdminBanner {
  id: number
  placement: string
  title: string
  image_url: string
  link_url: string | null
  sort_order: number
  starts_at: string | null
  ends_at: string | null
  is_active: boolean
}

export interface BannerInput {
  placement: string
  title: string
  image_url: string
  link_url?: string | null
  sort_order: number
  starts_at?: string | null
  ends_at?: string | null
  is_active: boolean
}

export async function listPages(): Promise<AdminCmsPage[]> {
  const { data } = await apiClient.get<Envelope<AdminCmsPage[]>>('/admin/cms/pages')
  return data.data
}

export async function getPage(id: number): Promise<AdminCmsPage> {
  const { data } = await apiClient.get<Envelope<AdminCmsPage>>(`/admin/cms/pages/${id}`)
  return data.data
}

export async function createPage(payload: CmsPageInput): Promise<AdminCmsPage> {
  const { data } = await apiClient.post<Envelope<AdminCmsPage>>('/admin/cms/pages', payload)
  return data.data
}

export async function updatePage(id: number, payload: CmsPageInput): Promise<AdminCmsPage> {
  const { data } = await apiClient.patch<Envelope<AdminCmsPage>>(`/admin/cms/pages/${id}`, payload)
  return data.data
}

export async function deletePage(id: number): Promise<AdminCmsPage> {
  const { data } = await apiClient.delete<Envelope<AdminCmsPage>>(`/admin/cms/pages/${id}`)
  return data.data
}

export async function restorePage(id: number): Promise<AdminCmsPage> {
  const { data } = await apiClient.post<Envelope<AdminCmsPage>>(`/admin/cms/pages/${id}/restore`)
  return data.data
}

export async function listBanners(): Promise<AdminBanner[]> {
  const { data } = await apiClient.get<Envelope<AdminBanner[]>>('/admin/cms/banners')
  return data.data
}

export async function getBanner(id: number): Promise<AdminBanner> {
  const { data } = await apiClient.get<Envelope<AdminBanner>>(`/admin/cms/banners/${id}`)
  return data.data
}

export async function createBanner(payload: BannerInput): Promise<AdminBanner> {
  const { data } = await apiClient.post<Envelope<AdminBanner>>('/admin/cms/banners', payload)
  return data.data
}

export async function updateBanner(id: number, payload: BannerInput): Promise<AdminBanner> {
  const { data } = await apiClient.patch<Envelope<AdminBanner>>(`/admin/cms/banners/${id}`, payload)
  return data.data
}

export async function deleteBanner(id: number): Promise<AdminBanner> {
  const { data } = await apiClient.delete<Envelope<AdminBanner>>(`/admin/cms/banners/${id}`)
  return data.data
}
