from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.commerce import Address


class AddressRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_for_user(self, user_id: int) -> list[Address]:
        stmt = (
            select(Address)
            .where(Address.user_id == user_id, Address.deleted_at.is_(None))
            .order_by(Address.is_default_shipping.desc(), Address.created_at.desc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_for_user(self, address_id: int, user_id: int) -> Address | None:
        stmt = select(Address).where(
            Address.id == address_id, Address.user_id == user_id, Address.deleted_at.is_(None)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    def add(self, address: Address) -> None:
        self.session.add(address)

    async def clear_default(self, user_id: int, *, shipping: bool, billing: bool) -> None:
        stmt = select(Address).where(Address.user_id == user_id, Address.deleted_at.is_(None))
        for existing in (await self.session.execute(stmt)).scalars().all():
            if shipping:
                existing.is_default_shipping = False
            if billing:
                existing.is_default_billing = False
