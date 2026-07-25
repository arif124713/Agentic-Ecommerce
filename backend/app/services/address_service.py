import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models.commerce import Address
from app.repositories.address import AddressRepository
from app.schemas.address import AddressIn, AddressOut


class AddressService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.addresses = AddressRepository(session)

    async def list_addresses(self, user_id: int) -> list[AddressOut]:
        addresses = await self.addresses.list_for_user(user_id)
        return [AddressOut.model_validate(a) for a in addresses]

    async def create_address(self, user_id: int, payload: AddressIn) -> AddressOut:
        if payload.is_default_shipping or payload.is_default_billing:
            await self.addresses.clear_default(
                user_id, shipping=payload.is_default_shipping, billing=payload.is_default_billing
            )
        address = Address(user_id=user_id, **payload.model_dump())
        self.addresses.add(address)
        await self.session.commit()
        await self.session.refresh(address)
        return AddressOut.model_validate(address)

    async def update_address(self, user_id: int, address_id: int, payload: AddressIn) -> AddressOut:
        address = await self.addresses.get_for_user(address_id, user_id)
        if address is None:
            raise NotFoundError("Address was not found.")

        if payload.is_default_shipping or payload.is_default_billing:
            await self.addresses.clear_default(
                user_id, shipping=payload.is_default_shipping, billing=payload.is_default_billing
            )
        for field, value in payload.model_dump().items():
            setattr(address, field, value)
        await self.session.commit()
        await self.session.refresh(address)
        return AddressOut.model_validate(address)

    async def delete_address(self, user_id: int, address_id: int) -> None:
        address = await self.addresses.get_for_user(address_id, user_id)
        if address is None:
            raise NotFoundError("Address was not found.")
        address.deleted_at = datetime.datetime.now(datetime.UTC)
        await self.session.commit()

    async def get_owned_address(self, user_id: int, address_id: int) -> Address:
        address = await self.addresses.get_for_user(address_id, user_id)
        if address is None:
            raise NotFoundError("Address was not found.")
        return address
