import { apiClient } from '../apiClient'
import type { Envelope } from '@/types/catalog'
import type { AdminUserDetail, AdminUserListItem } from '@/types/admin'

export async function listAdminUsers(params: { q?: string; page?: number; per_page?: number } = {}) {
  const { data } = await apiClient.get<Envelope<AdminUserListItem[]>>('/admin/users', { params })
  return data.data
}

export async function getAdminUser(publicId: string): Promise<AdminUserDetail> {
  const { data } = await apiClient.get<Envelope<AdminUserDetail>>(`/admin/users/${publicId}`)
  return data.data
}

export async function assignRole(publicId: string, roleCode: string): Promise<AdminUserDetail> {
  const { data } = await apiClient.post<Envelope<AdminUserDetail>>(`/admin/users/${publicId}/roles`, {
    role_code: roleCode,
  })
  return data.data
}

export async function revokeRole(publicId: string, roleCode: string): Promise<AdminUserDetail> {
  const { data } = await apiClient.delete<Envelope<AdminUserDetail>>(`/admin/users/${publicId}/roles/${roleCode}`)
  return data.data
}

export async function suspendUser(publicId: string, reason?: string): Promise<AdminUserDetail> {
  const { data } = await apiClient.post<Envelope<AdminUserDetail>>(`/admin/users/${publicId}/suspend`, { reason })
  return data.data
}

export async function reactivateUser(publicId: string): Promise<AdminUserDetail> {
  const { data } = await apiClient.post<Envelope<AdminUserDetail>>(`/admin/users/${publicId}/reactivate`)
  return data.data
}
