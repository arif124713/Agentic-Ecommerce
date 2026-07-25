from datetime import datetime

from pydantic import BaseModel, Field


class ReviewOut(BaseModel):
    id: int
    author_name: str
    rating: int
    title: str | None
    comment: str | None
    is_verified_purchase: bool
    status: str
    helpful_count: int
    created_at: datetime
    is_own: bool = False


class RatingBreakdownBucket(BaseModel):
    rating: int
    count: int


class ReviewSummaryOut(BaseModel):
    rating_avg: float | None
    rating_count: int
    review_count: int
    breakdown: list[RatingBreakdownBucket]


class ReviewListMeta(BaseModel):
    page: int
    per_page: int
    total: int
    total_pages: int
    has_next: bool


class ReviewListOut(BaseModel):
    data: list[ReviewOut]
    meta: ReviewListMeta
    summary: ReviewSummaryOut


class ReviewCreateIn(BaseModel):
    order_item_id: int
    rating: int = Field(ge=1, le=5)
    title: str | None = Field(default=None, max_length=150)
    comment: str | None = Field(default=None, max_length=2000)


class ReviewUpdateIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    title: str | None = Field(default=None, max_length=150)
    comment: str | None = Field(default=None, max_length=2000)


class ReviewEligibleItemOut(BaseModel):
    order_item_id: int
    order_number: str
    title_snapshot: str
    image_snapshot: str | None
    delivered_at: datetime | None


class ReviewEligibilityOut(BaseModel):
    can_review: bool
    eligible_items: list[ReviewEligibleItemOut]
    existing_review: ReviewOut | None = None


class AdminReviewOut(BaseModel):
    id: int
    product_id: int
    product_slug: str
    product_title: str
    author_name: str
    rating: int
    title: str | None
    comment: str | None
    is_verified_purchase: bool
    status: str
    helpful_count: int
    reported_count: int
    moderated_at: datetime | None
    created_at: datetime


class AdminReviewListOut(BaseModel):
    data: list[AdminReviewOut]
    meta: ReviewListMeta


class AdminReviewModerateIn(BaseModel):
    status: str = Field(pattern="^(approved|rejected|hidden)$")
