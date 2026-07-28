import { apiClient } from './apiClient'
import type { Envelope } from '@/types/catalog'
import type { Banner, CmsPage } from '@/types/cms'

export async function getCmsPage(slug: string): Promise<CmsPage> {
  const { data } = await apiClient.get<Envelope<CmsPage>>(`/pages/${slug}`)
  return data.data
}

export async function getBanners(placement: string): Promise<Banner[]> {
  const { data } = await apiClient.get<Envelope<Banner[]>>('/banners', { params: { placement } })
  return data.data
}
