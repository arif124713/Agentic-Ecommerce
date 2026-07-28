from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import NotFoundError
from app.core.timeutil import utcnow
from app.models.auth import User
from app.models.support import SupportTicket, TicketMessage
from app.repositories.support import SupportTicketRepository
from app.schemas.admin_support import AdminTicketListItemOut, AdminTicketOut, TicketAssignIn, TicketStatusIn
from app.schemas.support import TicketMessageIn


class AdminSupportService:
    """Unscoped by user — every ticket, gated entirely by the `support:ticket:manage` permission
    at the router layer, matching the same "no separate admin bypass" principle as the order
    state machine (admin transitions reuse the exact same rules, just without the ownership
    check customer-facing reads apply)."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.tickets = SupportTicketRepository(session)

    async def list_tickets(
        self, *, status: str | None, assignee_user_id: int | None, page: int, per_page: int
    ) -> tuple[list[AdminTicketListItemOut], int]:
        tickets, total = await self.tickets.list_all(
            status=status, assignee_user_id=assignee_user_id, page=page, per_page=per_page
        )
        items = [
            AdminTicketListItemOut(
                public_id=t.public_id,
                subject=t.subject,
                status=t.status,
                priority=t.priority,
                contact_email=t.contact_email,
                assignee_name=t.assignee.first_name if t.assignee else None,
                created_at=t.created_at,
                updated_at=t.updated_at,
            )
            for t in tickets
        ]
        return items, total

    async def get_ticket(self, public_id: str) -> AdminTicketOut:
        ticket = await self._get_or_404(public_id, with_messages=True)
        return self._to_out(ticket)

    async def assign_ticket(self, public_id: str, payload: TicketAssignIn) -> AdminTicketOut:
        ticket = await self._get_or_404(public_id, with_messages=False)
        ticket.assignee_user_id = payload.assignee_user_id
        ticket.updated_at = utcnow()
        await self.session.commit()
        return await self._reload_out(ticket.id)

    async def update_status(self, public_id: str, payload: TicketStatusIn) -> AdminTicketOut:
        ticket = await self._get_or_404(public_id, with_messages=False)
        ticket.status = payload.status
        ticket.updated_at = utcnow()
        await self.session.commit()
        return await self._reload_out(ticket.id)

    async def add_staff_message(self, staff_user: User, public_id: str, payload: TicketMessageIn) -> AdminTicketOut:
        ticket = await self._get_or_404(public_id, with_messages=False)
        message = TicketMessage(
            ticket_id=ticket.id,
            author_user_id=staff_user.id,
            author_type="staff",
            body=payload.body,
            created_at=utcnow(),
        )
        self.tickets.add_message(message)
        # A staff reply moves an untouched ticket out of "open" into "pending" (awaiting the
        # customer) — mirrors a real helpdesk's default behaviour without inventing a separate
        # transition table for two states; explicit status changes still go through update_status.
        if ticket.status == "open":
            ticket.status = "pending"
        ticket.updated_at = utcnow()
        await self.session.commit()
        return await self._reload_out(ticket.id)

    async def _get_or_404(self, public_id: str, *, with_messages: bool) -> SupportTicket:
        ticket = await self.tickets.get_by_public_id(public_id, with_messages=with_messages)
        if ticket is None:
            raise NotFoundError("Ticket was not found.")
        return ticket

    async def _reload_out(self, ticket_id: int) -> AdminTicketOut:
        stmt = (
            select(SupportTicket)
            .where(SupportTicket.id == ticket_id)
            .options(selectinload(SupportTicket.messages), selectinload(SupportTicket.assignee))
            .execution_options(populate_existing=True)
        )
        ticket = (await self.session.execute(stmt)).scalar_one()
        return self._to_out(ticket)

    @staticmethod
    def _to_out(ticket: SupportTicket) -> AdminTicketOut:
        return AdminTicketOut(
            public_id=ticket.public_id,
            subject=ticket.subject,
            status=ticket.status,
            priority=ticket.priority,
            contact_email=ticket.contact_email,
            assignee_user_id=ticket.assignee_user_id,
            assignee_name=ticket.assignee.first_name if ticket.assignee else None,
            created_at=ticket.created_at,
            updated_at=ticket.updated_at,
            messages=list(ticket.messages),
        )
