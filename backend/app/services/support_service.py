from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from ulid import ULID

from app.core.errors import NotFoundError
from app.core.timeutil import utcnow
from app.models.auth import User
from app.models.support import SupportTicket, TicketMessage
from app.repositories.support import SupportTicketRepository
from app.schemas.support import TicketCreateIn, TicketListItemOut, TicketMessageIn, TicketOut


class SupportService:
    """Customer-facing only — every read is scoped to the requesting user's own tickets.
    Login is required to create or view a ticket (no guest ticket flow in this scope, unlike
    spec §8.3's `contact_email`-only guest path — a documented simplification consistent with
    every other account-scoped feature in this project, e.g. reviews/wishlist)."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.tickets = SupportTicketRepository(session)

    async def create_ticket(self, user: User, payload: TicketCreateIn) -> TicketOut:
        now = utcnow()
        ticket = SupportTicket(
            public_id=str(ULID()),
            user_id=user.id,
            contact_email=user.email,
            subject=payload.subject,
            status="open",
            priority=payload.priority,
            # Assigned at construction, while still transient — a pure in-memory op, avoiding the
            # illegal-lazy-load-after-flush pattern documented throughout this project (RBAC seed,
            # Cart construction) for relationship collections touched right after persistence.
            messages=[TicketMessage(author_user_id=user.id, author_type="customer", body=payload.body, created_at=now)],
        )
        self.tickets.add(ticket)
        await self.session.commit()
        return await self._reload_out(ticket.id)

    async def list_own_tickets(self, user: User) -> list[TicketListItemOut]:
        tickets = await self.tickets.list_for_user(user.id)
        return [TicketListItemOut.model_validate(t) for t in tickets]

    async def get_own_ticket(self, user: User, public_id: str) -> TicketOut:
        ticket = await self._get_owned(user, public_id)
        return TicketOut.model_validate(ticket)

    async def add_message(self, user: User, public_id: str, payload: TicketMessageIn) -> TicketOut:
        ticket = await self._get_owned(user, public_id)
        message = TicketMessage(
            ticket_id=ticket.id, author_user_id=user.id, author_type="customer", body=payload.body, created_at=utcnow()
        )
        self.tickets.add_message(message)
        # Replying reopens a resolved/closed ticket from the customer's own side — matches the
        # spirit of order_service's single-source-of-truth transition tables: no ad-hoc status
        # writes elsewhere, but this file is the one place a customer message legitimately changes
        # ticket state.
        if ticket.status in ("resolved", "closed"):
            ticket.status = "open"
        ticket.updated_at = utcnow()
        await self.session.commit()
        return await self._reload_out(ticket.id)

    async def _get_owned(self, user: User, public_id: str) -> SupportTicket:
        ticket = await self.tickets.get_by_public_id(public_id)
        if ticket is None or ticket.user_id != user.id:
            raise NotFoundError("Ticket was not found.")
        return ticket

    async def _reload_out(self, ticket_id: int) -> TicketOut:
        # populate_existing: this is always called right after mutating a ticket already sitting
        # in this session's identity map (just-created, or just-replied-to) — without it, the
        # already-loaded `messages` collection would be left stale rather than reflecting the
        # message just added (the exact bug class documented in done.MD's cart/inventory fixes).
        stmt = (
            select(SupportTicket)
            .where(SupportTicket.id == ticket_id)
            .options(selectinload(SupportTicket.messages))
            .execution_options(populate_existing=True)
        )
        ticket = (await self.session.execute(stmt)).scalar_one()
        return TicketOut.model_validate(ticket)
