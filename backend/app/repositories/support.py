from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.support import SupportTicket, TicketMessage


class SupportTicketRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    def add(self, ticket: SupportTicket) -> None:
        self.session.add(ticket)

    async def get_by_public_id(self, public_id: str, *, with_messages: bool = True) -> SupportTicket | None:
        # assignee is always eager-loaded (a cheap single-row join) since every caller that reads
        # a ticket back out to a schema needs it; messages is the heavier, optional load.
        stmt = select(SupportTicket).where(SupportTicket.public_id == public_id).options(
            selectinload(SupportTicket.assignee)
        )
        if with_messages:
            stmt = stmt.options(selectinload(SupportTicket.messages))
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_id(self, ticket_id: int, *, with_messages: bool = True) -> SupportTicket | None:
        stmt = select(SupportTicket).where(SupportTicket.id == ticket_id).options(
            selectinload(SupportTicket.assignee)
        )
        if with_messages:
            stmt = stmt.options(selectinload(SupportTicket.messages))
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_for_user(self, user_id: int) -> list[SupportTicket]:
        stmt = select(SupportTicket).where(SupportTicket.user_id == user_id).order_by(SupportTicket.created_at.desc())
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_all(
        self, *, status: str | None, assignee_user_id: int | None, page: int, per_page: int
    ) -> tuple[list[SupportTicket], int]:
        stmt = select(SupportTicket).options(selectinload(SupportTicket.assignee))
        if status:
            stmt = stmt.where(SupportTicket.status == status)
        if assignee_user_id is not None:
            stmt = stmt.where(SupportTicket.assignee_user_id == assignee_user_id)
        total = (await self.session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
        stmt = stmt.order_by(SupportTicket.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
        return list((await self.session.execute(stmt)).scalars().all()), total

    def add_message(self, message: TicketMessage) -> None:
        self.session.add(message)
