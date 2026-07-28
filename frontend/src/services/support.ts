import { apiClient } from './apiClient'
import type { Envelope } from '@/types/catalog'
import type { Ticket, TicketListItem } from '@/types/support'

export async function listMyTickets(): Promise<TicketListItem[]> {
  const { data } = await apiClient.get<Envelope<TicketListItem[]>>('/support/tickets')
  return data.data
}

export async function createTicket(payload: {
  subject: string
  body: string
  priority?: 'low' | 'medium' | 'high'
}): Promise<Ticket> {
  const { data } = await apiClient.post<Envelope<Ticket>>('/support/tickets', payload)
  return data.data
}

export async function getTicket(publicId: string): Promise<Ticket> {
  const { data } = await apiClient.get<Envelope<Ticket>>(`/support/tickets/${publicId}`)
  return data.data
}

export async function replyToTicket(publicId: string, body: string): Promise<Ticket> {
  const { data } = await apiClient.post<Envelope<Ticket>>(`/support/tickets/${publicId}/messages`, { body })
  return data.data
}
