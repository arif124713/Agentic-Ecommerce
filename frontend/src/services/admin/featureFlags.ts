import { apiClient } from '../apiClient'
import type { Envelope } from '@/types/catalog'

export interface FeatureFlag {
  key: string
  enabled: boolean
  rollout_percent: number
  targeting: Record<string, unknown> | null
  description: string | null
  updated_by: number | null
}

export interface FeatureFlagCreateInput {
  key: string
  enabled: boolean
  rollout_percent: number
  description?: string | null
}

export interface FeatureFlagUpdateInput {
  enabled: boolean
  rollout_percent: number
  description?: string | null
}

export async function listFeatureFlags(): Promise<FeatureFlag[]> {
  const { data } = await apiClient.get<Envelope<FeatureFlag[]>>('/admin/feature-flags')
  return data.data
}

export async function createFeatureFlag(payload: FeatureFlagCreateInput): Promise<FeatureFlag> {
  const { data } = await apiClient.post<Envelope<FeatureFlag>>('/admin/feature-flags', payload)
  return data.data
}

export async function updateFeatureFlag(key: string, payload: FeatureFlagUpdateInput): Promise<FeatureFlag> {
  const { data } = await apiClient.patch<Envelope<FeatureFlag>>(`/admin/feature-flags/${key}`, payload)
  return data.data
}
