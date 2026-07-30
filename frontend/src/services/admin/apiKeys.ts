import { apiClient } from '../apiClient'
import type { Envelope } from '@/types/catalog'

export interface ApiKey {
  public_id: string
  name: string
  key_prefix: string
  scopes: string[]
  ip_allowlist: string[] | null
  expires_at: string | null
  last_used_at: string | null
  revoked_at: string | null
  created_at: string
}

export interface ApiKeyCreated extends ApiKey {
  raw_key: string
}

export interface ApiKeyCreateInput {
  name: string
  scopes: string[]
  ip_allowlist?: string[] | null
  expires_at?: string | null
}

export async function listApiKeys(): Promise<ApiKey[]> {
  const { data } = await apiClient.get<Envelope<ApiKey[]>>('/admin/api-keys')
  return data.data
}

export async function createApiKey(payload: ApiKeyCreateInput): Promise<ApiKeyCreated> {
  const { data } = await apiClient.post<Envelope<ApiKeyCreated>>('/admin/api-keys', payload)
  return data.data
}

export async function revokeApiKey(publicId: string): Promise<void> {
  await apiClient.delete(`/admin/api-keys/${publicId}`)
}
