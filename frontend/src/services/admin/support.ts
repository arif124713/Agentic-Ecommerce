import { apiClient } from '../apiClient'
import type { Envelope } from '@/types/catalog'
import type { TicketMessage } from '@/types/support'

export interface AdminTicketListItem {
  public_id: string
  subject: string
  status: 'open' | 'pending' | 'resolved' | 'closed'
  priority: 'low' | 'medium' | 'high'
  contact_email: string
  assignee_name: string | null
  created_at: string
  updated_at: string
}

export interface AdminTicket {
  public_id: string
  subject: string
  status: AdminTicketListItem['status']
  priority: AdminTicketListItem['priority']
  contact_email: string
  assignee_user_id: number | null
  assignee_name: string | null
  created_at: string
  updated_at: string
  messages: TicketMessage[]
}

export async function listAllTickets(params?: { status?: string }): Promise<AdminTicketListItem[]> {
  const { data } = await apiClient.get<Envelope<AdminTicketListItem[]>>('/admin/support/tickets', { params })
  return data.data
}

export async function getAdminTicket(publicId: string): Promise<AdminTicket> {
  const { data } = await apiClient.get<Envelope<AdminTicket>>(`/admin/support/tickets/${publicId}`)
  return data.data
}

export async function assignTicket(publicId: string, assigneeUserId: number | null): Promise<AdminTicket> {
  const { data } = await apiClient.post<Envelope<AdminTicket>>(`/admin/support/tickets/${publicId}/assign`, {
    assignee_user_id: assigneeUserId,
  })
  return data.data
}

export async function updateTicketStatus(publicId: string, status: string): Promise<AdminTicket> {
  const { data } = await apiClient.post<Envelope<AdminTicket>>(`/admin/support/tickets/${publicId}/status`, {
    status,
  })
  return data.data
}

export async function replyAsStaff(publicId: string, body: string): Promise<AdminTicket> {
  const { data } = await apiClient.post<Envelope<AdminTicket>>(`/admin/support/tickets/${publicId}/messages`, {
    body,
  })
  return data.data
}
