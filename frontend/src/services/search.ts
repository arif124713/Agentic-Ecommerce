import { apiClient } from './apiClient'
import type { Envelope } from '@/types/catalog'
import type { SearchSuggestResponse } from '@/types/search'

export async function suggestSearch(q: string): Promise<SearchSuggestResponse> {
  const { data } = await apiClient.get<Envelope<SearchSuggestResponse>>('/search/suggest', { params: { q } })
  return data.data
}
