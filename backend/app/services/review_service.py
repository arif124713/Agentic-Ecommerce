import math
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ReviewEditWindowClosedError, ReviewNotEligibleError
from app.core.timeutil import utcnow
from app.models.review import Review
from app.repositories.catalog import ProductRepository
from app.repositories.review import ReviewRepository
from app.schemas.review import (
    AdminReviewListOut,
    AdminReviewOut,
    RatingBreakdownBucket,
    ReviewCreateIn,
    ReviewEligibilityOut,
    ReviewEligibleItemOut,
    ReviewListMeta,
    ReviewListOut,
    ReviewOut,
    ReviewSummaryOut,
    ReviewUpdateIn,
)

EDIT_WINDOW = timedelta(hours=24)


async def _recompute_and_commit(reviews: ReviewRepository, products: ProductRepository, product_id: int) -> None:
    """Spec §9.7: "on approval/rejection, a job recomputes rating_avg/rating_count/review_count
    for the product." Done inline (no Celery here) right after any write that changes a review's
    status or existence."""
    rating_avg, rating_count, review_count = await reviews.recompute_product_aggregates(product_id)
    product = await products.get_by_id(product_id)
    if product is None:
        return
    product.rating_avg = round(rating_avg, 2) if rating_avg is not None else None
    product.rating_count = rating_count
    product.review_count = review_count
    await products.session.commit()


def _to_review_out(review: Review, author_name: str, *, viewer_user_id: int | None) -> ReviewOut:
    return ReviewOut(
        id=review.id,
        author_name=author_name,
        rating=review.rating,
        title=review.title,
        comment=review.comment,
        is_verified_purchase=review.is_verified_purchase,
        status=review.status,
        helpful_count=review.helpful_count,
        created_at=review.created_at,
        is_own=viewer_user_id is not None and review.user_id == viewer_user_id,
    )


class ReviewService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.reviews = ReviewRepository(session)
        self.products = ProductRepository(session)

    async def eligibility(self, product_slug: str, user_id: int) -> ReviewEligibilityOut:
        product = await self.products.get_by_slug(product_slug)
        if product is None:
            raise NotFoundError(f"Product '{product_slug}' was not found.")

        items = await self.reviews.eligible_order_items(user_id=user_id, product_id=product.id)
        existing = await self.reviews.get_own_review(product_id=product.id, user_id=user_id)
        return ReviewEligibilityOut(
            can_review=len(items) > 0,
            eligible_items=[
                ReviewEligibleItemOut(
                    order_item_id=item.order_item_id,
                    order_number=item.order_number,
                    title_snapshot=item.title_snapshot,
                    image_snapshot=item.image_snapshot,
                    delivered_at=item.delivered_at,
                )
                for item in items
            ],
            existing_review=_to_review_out(existing, "", viewer_user_id=user_id) if existing else None,
        )

    async def create(self, product_slug: str, user_id: int, payload: ReviewCreateIn) -> ReviewOut:
        product = await self.products.get_by_slug(product_slug)
        if product is None:
            raise NotFoundError(f"Product '{product_slug}' was not found.")
        product_id = product.id

        order_item = await self.reviews.get_order_item_for_user(
            order_item_id=payload.order_item_id, user_id=user_id
        )
        if order_item is None or order_item.product_id != product_id:
            raise ReviewNotEligibleError()
        if await self.reviews.get_by_order_item(order_item.id) is not None:
            raise ReviewNotEligibleError("You've already reviewed this purchase.")

        review = Review(
            product_id=product_id,
            user_id=user_id,
            order_item_id=order_item.id,
            rating=payload.rating,
            title=payload.title,
            comment=payload.comment,
            is_verified_purchase=True,
            status="pending",
        )
        self.reviews.add(review)
        await self.session.commit()
        # Session-wide expire-on-commit means every attribute on every tracked object (not just
        # `review`) is now stale until re-read; `created_at` is server_default-computed (MySQL has
        # no RETURNING), so an explicit awaited refresh is required before it can be touched again
        # — the same MissingGreenlet trap hit repeatedly elsewhere in this codebase (see done.MD),
        # here caught live via curl rather than by inspection.
        await self.session.refresh(review)

        result = _to_review_out(review, "You", viewer_user_id=user_id)
        await self._recompute_aggregates(product_id)
        return result

    async def update_own(self, review_id: int, user_id: int, payload: ReviewUpdateIn) -> ReviewOut:
        review = await self.reviews.get_by_id(review_id)
        if review is None or review.user_id != user_id:
            raise NotFoundError("Review was not found.")
        if utcnow() - review.created_at > EDIT_WINDOW:
            raise ReviewEditWindowClosedError()

        review.rating = payload.rating
        review.title = payload.title
        review.comment = payload.comment
        review.status = "pending"
        review.moderated_by = None
        review.moderated_at = None

        # Build the response from the in-memory, not-yet-expired values *before* committing —
        # every field it needs was just set in Python or loaded before this method's first
        # commit, so there's nothing left to safely re-read afterward without an extra refresh.
        product_id = review.product_id
        result = _to_review_out(review, "You", viewer_user_id=user_id)

        await self.session.commit()
        await self._recompute_aggregates(product_id)
        return result

    async def list_for_product(
        self, product_slug: str, *, viewer_user_id: int | None, page: int, per_page: int
    ) -> ReviewListOut:
        product = await self.products.get_by_slug(product_slug)
        if product is None:
            raise NotFoundError(f"Product '{product_slug}' was not found.")

        rows, total = await self.reviews.list_for_product(
            product_id=product.id, viewer_user_id=viewer_user_id, page=page, per_page=per_page
        )
        breakdown = await self.reviews.rating_breakdown(product.id)
        return ReviewListOut(
            data=[_to_review_out(review, name, viewer_user_id=viewer_user_id) for review, name in rows],
            meta=ReviewListMeta(
                page=page,
                per_page=per_page,
                total=total,
                total_pages=max(1, math.ceil(total / per_page)),
                has_next=page * per_page < total,
            ),
            summary=ReviewSummaryOut(
                rating_avg=float(product.rating_avg) if product.rating_avg is not None else None,
                rating_count=product.rating_count,
                review_count=product.review_count,
                breakdown=[
                    RatingBreakdownBucket(rating=r, count=breakdown.get(r, 0)) for r in range(5, 0, -1)
                ],
            ),
        )

    async def _recompute_aggregates(self, product_id: int) -> None:
        await _recompute_and_commit(self.reviews, self.products, product_id)


class AdminReviewService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.reviews = ReviewRepository(session)
        self.products = ProductRepository(session)

    async def list_for_moderation(self, *, status: str | None, page: int, per_page: int) -> AdminReviewListOut:
        rows, total = await self.reviews.list_for_moderation(status=status, page=page, per_page=per_page)
        return AdminReviewListOut(
            data=[
                AdminReviewOut(
                    id=review.id,
                    product_id=review.product_id,
                    product_slug=product.slug,
                    product_title=product.title,
                    author_name=author_name,
                    rating=review.rating,
                    title=review.title,
                    comment=review.comment,
                    is_verified_purchase=review.is_verified_purchase,
                    status=review.status,
                    helpful_count=review.helpful_count,
                    reported_count=review.reported_count,
                    moderated_at=review.moderated_at,
                    created_at=review.created_at,
                )
                for review, product, author_name in rows
            ],
            meta=ReviewListMeta(
                page=page,
                per_page=per_page,
                total=total,
                total_pages=max(1, math.ceil(total / per_page)),
                has_next=page * per_page < total,
            ),
        )

    async def moderate(self, review_id: int, moderator_id: int, status: str) -> AdminReviewOut:
        context = await self.reviews.get_with_context(review_id)
        if context is None:
            raise NotFoundError("Review was not found.")
        review, product, author_name = context
        product_id = review.product_id

        review.status = status
        review.moderated_by = moderator_id
        review.moderated_at = utcnow()

        # Same rule as ReviewService.update_own: build the result from current in-memory state
        # before the first commit, since expire-on-commit would otherwise make every attribute
        # read below (on either `review` or `product`) an unsafe unawaited lazy-load.
        result = AdminReviewOut(
            id=review.id,
            product_id=product_id,
            product_slug=product.slug,
            product_title=product.title,
            author_name=author_name,
            rating=review.rating,
            title=review.title,
            comment=review.comment,
            is_verified_purchase=review.is_verified_purchase,
            status=review.status,
            helpful_count=review.helpful_count,
            reported_count=review.reported_count,
            moderated_at=review.moderated_at,
            created_at=review.created_at,
        )

        await self.session.commit()
        await _recompute_and_commit(self.reviews, self.products, product_id)
        return result
