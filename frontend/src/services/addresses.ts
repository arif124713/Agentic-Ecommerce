import { apiClient } from './apiClient'
import type { Address, AddressInput } from '@/types/address'
import type { Envelope } from '@/types/catalog'

export async function listAddresses(): Promise<Address[]> {
  const { data } = await apiClient.get<Envelope<Address[]>>('/addresses')
  return data.data
}

export async function createAddress(payload: AddressInput): Promise<Address> {
  const { data } = await apiClient.post<Envelope<Address>>('/addresses', payload)
  return data.data
}

export async function updateAddress(id: number, payload: AddressInput): Promise<Address> {
  const { data } = await apiClient.patch<Envelope<Address>>(`/addresses/${id}`, payload)
  return data.data
}

export async function deleteAddress(id: number): Promise<void> {
  await apiClient.delete(`/addresses/${id}`)
}
