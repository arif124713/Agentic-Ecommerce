from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require
from app.models.auth import User
from app.schemas.admin_support import AdminTicketListItemOut, AdminTicketOut, TicketAssignIn, TicketStatusIn
from app.schemas.support import TicketMessageIn
from app.services.admin.support_service import AdminSupportService

router = APIRouter(prefix="/admin/support/tickets", tags=["admin-support"])


@router.get("", response_model=list[AdminTicketListItemOut])
async def list_tickets(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require("support:ticket:manage")),
    status: str | None = Query(default=None),
    assignee_user_id: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
):
    items, _total = await AdminSupportService(db).list_tickets(
        status=status, assignee_user_id=assignee_user_id, page=page, per_page=per_page
    )
    return items


@router.get("/{public_id}", response_model=AdminTicketOut)
async def get_ticket(
    public_id: str, db: AsyncSession = Depends(get_db), _user: User = Depends(require("support:ticket:manage"))
):
    return await AdminSupportService(db).get_ticket(public_id)


@router.post("/{public_id}/assign", response_model=AdminTicketOut)
async def assign_ticket(
    public_id: str,
    payload: TicketAssignIn,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require("support:ticket:manage")),
):
    return await AdminSupportService(db).assign_ticket(public_id, payload)


@router.post("/{public_id}/status", response_model=AdminTicketOut)
async def update_status(
    public_id: str,
    payload: TicketStatusIn,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require("support:ticket:manage")),
):
    return await AdminSupportService(db).update_status(public_id, payload)


@router.post("/{public_id}/messages", response_model=AdminTicketOut, status_code=201)
async def add_message(
    public_id: str,
    payload: TicketMessageIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require("support:ticket:manage")),
):
    return await AdminSupportService(db).add_staff_message(user, public_id, payload)
