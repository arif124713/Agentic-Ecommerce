from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, get_optional_user
from app.models.auth import User
from app.schemas.review import ReviewCreateIn, ReviewEligibilityOut, ReviewListOut, ReviewOut, ReviewUpdateIn
from app.services.review_service import ReviewService

router = APIRouter(tags=["reviews"])


@router.get("/products/{slug}/reviews", response_model=ReviewListOut)
async def list_reviews(
    slug: str,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_user),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=10, ge=1, le=50),
):
    return await ReviewService(db).list_for_product(
        slug, viewer_user_id=user.id if user else None, page=page, per_page=per_page
    )


@router.get("/products/{slug}/reviews/eligibility", response_model=ReviewEligibilityOut)
async def review_eligibility(slug: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    return await ReviewService(db).eligibility(slug, user.id)


@router.post("/products/{slug}/reviews", response_model=ReviewOut, status_code=201)
async def create_review(
    slug: str,
    payload: ReviewCreateIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await ReviewService(db).create(slug, user.id, payload)


@router.patch("/reviews/{review_id}", response_model=ReviewOut)
async def update_review(
    review_id: int,
    payload: ReviewUpdateIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await ReviewService(db).update_own(review_id, user.id, payload)
