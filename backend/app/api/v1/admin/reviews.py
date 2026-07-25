from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require
from app.models.auth import User
from app.schemas.review import AdminReviewListOut, AdminReviewModerateIn, AdminReviewOut
from app.services.review_service import AdminReviewService

router = APIRouter(prefix="/admin/reviews", tags=["admin-reviews"])


@router.get("", response_model=AdminReviewListOut)
async def list_reviews(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require("review:review:moderate")),
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
):
    return await AdminReviewService(db).list_for_moderation(status=status, page=page, per_page=per_page)


@router.post("/{review_id}/moderate", response_model=AdminReviewOut)
async def moderate_review(
    review_id: int,
    payload: AdminReviewModerateIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require("review:review:moderate")),
):
    return await AdminReviewService(db).moderate(review_id, user.id, payload.status)
