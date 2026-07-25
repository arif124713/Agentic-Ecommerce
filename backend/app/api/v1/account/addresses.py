from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.auth import User
from app.schemas.address import AddressIn, AddressOut
from app.services.address_service import AddressService

router = APIRouter(prefix="/addresses", tags=["addresses"])


@router.get("", response_model=list[AddressOut])
async def list_addresses(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    return await AddressService(db).list_addresses(user.id)


@router.post("", response_model=AddressOut, status_code=201)
async def create_address(
    payload: AddressIn, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    return await AddressService(db).create_address(user.id, payload)


@router.patch("/{address_id}", response_model=AddressOut)
async def update_address(
    address_id: int,
    payload: AddressIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await AddressService(db).update_address(user.id, address_id, payload)


@router.delete("/{address_id}", status_code=204)
async def delete_address(
    address_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    await AddressService(db).delete_address(user.id, address_id)
    return Response(status_code=204)
