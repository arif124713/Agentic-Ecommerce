import { apiClient } from '../apiClient'
import type { Envelope } from '@/types/catalog'
import type {
  AdminProductDetail,
  AdminProductListResponse,
  AdminVariant,
  BrandOption,
  CategoryOption,
  LowStockVariant,
  ProductBulkActionResult,
  ProductImportSummary,
  ProductInput,
  VariantInput,
} from '@/types/admin'

export interface AdminProductListParams {
  q?: string
  status?: string
  category_id?: number
  page?: number
  per_page?: number
}

export async function listAdminProducts(params: AdminProductListParams = {}): Promise<AdminProductListResponse> {
  const { data } = await apiClient.get<AdminProductListResponse>('/admin/products', { params })
  return data
}

export async function getAdminProduct(id: number): Promise<AdminProductDetail> {
  const { data } = await apiClient.get<Envelope<AdminProductDetail>>(`/admin/products/${id}`)
  return data.data
}

export async function createAdminProduct(payload: ProductInput): Promise<AdminProductDetail> {
  const { data } = await apiClient.post<Envelope<AdminProductDetail>>('/admin/products', payload)
  return data.data
}

export async function updateAdminProduct(id: number, payload: ProductInput): Promise<AdminProductDetail> {
  const { data } = await apiClient.patch<Envelope<AdminProductDetail>>(`/admin/products/${id}`, payload)
  return data.data
}

export async function deleteAdminProduct(id: number): Promise<void> {
  await apiClient.delete(`/admin/products/${id}`)
}

export async function restoreAdminProduct(id: number): Promise<AdminProductDetail> {
  const { data } = await apiClient.post<Envelope<AdminProductDetail>>(`/admin/products/${id}/restore`)
  return data.data
}

export async function addVariant(productId: number, payload: VariantInput): Promise<AdminVariant> {
  const { data } = await apiClient.post<Envelope<AdminVariant>>(`/admin/products/${productId}/variants`, payload)
  return data.data
}

export async function updateVariant(variantId: number, payload: VariantInput): Promise<AdminVariant> {
  const { data } = await apiClient.patch<Envelope<AdminVariant>>(`/admin/variants/${variantId}`, payload)
  return data.data
}

export async function deleteVariant(variantId: number): Promise<void> {
  await apiClient.delete(`/admin/variants/${variantId}`)
}

export async function adjustInventory(
  variantId: number,
  payload: { delta: number; reason: string; note?: string },
): Promise<AdminVariant> {
  const { data } = await apiClient.post<Envelope<AdminVariant>>(`/admin/inventory/${variantId}/adjust`, payload)
  return data.data
}

export async function listLowStock(limit = 50): Promise<LowStockVariant[]> {
  const { data } = await apiClient.get<Envelope<LowStockVariant[]>>('/admin/inventory/low-stock', {
    params: { limit },
  })
  return data.data
}

export async function listBrandOptions(): Promise<BrandOption[]> {
  const { data } = await apiClient.get<Envelope<BrandOption[]>>('/admin/catalog-options/brands')
  return data.data
}

export async function listCategoryOptions(): Promise<CategoryOption[]> {
  const { data } = await apiClient.get<Envelope<CategoryOption[]>>('/admin/catalog-options/categories')
  return data.data
}

export async function exportProductsCsv(): Promise<Blob> {
  const { data } = await apiClient.get<Blob>('/admin/products/export', { responseType: 'blob' })
  return data
}

export async function importProductsCsv(file: File): Promise<ProductImportSummary> {
  const formData = new FormData()
  formData.append('file', file)
  const { data } = await apiClient.post<Envelope<ProductImportSummary>>('/admin/products/import', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data.data
}

export async function bulkProductAction(
  productIds: number[],
  action: 'activate' | 'archive' | 'delete',
): Promise<ProductBulkActionResult> {
  const { data } = await apiClient.post<Envelope<ProductBulkActionResult>>('/admin/products/bulk', {
    product_ids: productIds,
    action,
  })
  return data.data
}
