from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.auth import User
from app.schemas.support import TicketCreateIn, TicketListItemOut, TicketMessageIn, TicketOut
from app.services.support_service import SupportService

router = APIRouter(prefix="/support/tickets", tags=["support"])


@router.get("", response_model=list[TicketListItemOut])
async def list_tickets(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    return await SupportService(db).list_own_tickets(user)


@router.post("", response_model=TicketOut, status_code=201)
async def create_ticket(
    payload: TicketCreateIn, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    return await SupportService(db).create_ticket(user, payload)


@router.get("/{public_id}", response_model=TicketOut)
async def get_ticket(
    public_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    return await SupportService(db).get_own_ticket(user, public_id)


@router.post("/{public_id}/messages", response_model=TicketOut, status_code=201)
async def add_message(
    public_id: str,
    payload: TicketMessageIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await SupportService(db).add_message(user, public_id, payload)
