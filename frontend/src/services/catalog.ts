import { apiClient } from './apiClient'
import type {
  Brand,
  Category,
  Envelope,
  ProductDetail,
  ProductListResponse,
} from '@/types/catalog'

export interface ListProductsParams {
  category?: string
  brand?: string
  price_min?: number
  price_max?: number
  gender?: string
  q?: string
  sort?: string
  page?: number
  per_page?: number
}

export async function listProducts(params: ListProductsParams = {}): Promise<ProductListResponse> {
  const { data } = await apiClient.get<ProductListResponse>('/products', { params })
  return data
}

export async function getProduct(slug: string): Promise<ProductDetail> {
  const { data } = await apiClient.get<Envelope<ProductDetail>>(`/products/${slug}`)
  return data.data
}

export async function listCategories(): Promise<Category[]> {
  const { data } = await apiClient.get<Envelope<Category[]>>('/categories')
  return data.data
}

export async function listBrands(): Promise<Brand[]> {
  const { data } = await apiClient.get<Envelope<Brand[]>>('/brands')
  return data.data
}
