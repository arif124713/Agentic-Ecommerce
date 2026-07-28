export interface TicketMessage {
  id: number
  author_type: 'customer' | 'staff'
  body: string
  created_at: string
}

export interface Ticket {
  public_id: string
  subject: string
  status: 'open' | 'pending' | 'resolved' | 'closed'
  priority: 'low' | 'medium' | 'high'
  created_at: string
  updated_at: string
  messages: TicketMessage[]
}

export interface TicketListItem {
  public_id: string
  subject: string
  status: Ticket['status']
  priority: Ticket['priority']
  created_at: string
  updated_at: string
}
