from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import User
from app.models.catalog import Product
from app.models.commerce import Order, OrderItem
from app.models.review import Review


@dataclass
class EligibleOrderItem:
    """Plain data, not an ORM object with a lazy `.order` relationship — selecting the exact
    columns needed avoids the classic async-SQLAlchemy MissingGreenlet trap this codebase has
    hit repeatedly on relationship access outside an eager-loaded query (see done.MD)."""

    order_item_id: int
    order_number: str
    title_snapshot: str
    image_snapshot: str | None
    delivered_at: datetime | None


class ReviewRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def eligible_order_items(self, *, user_id: int, product_id: int) -> list[EligibleOrderItem]:
        """Order items for this product, on this user's DELIVERED orders, that don't already
        have a review attached — spec §9.7's "only a DELIVERED order item may be reviewed"
        eligibility rule, one review per line item."""
        reviewed_subq = select(Review.order_item_id).where(
            Review.order_item_id.is_not(None), Review.user_id == user_id
        )
        stmt = (
            select(
                OrderItem.id, Order.order_number, OrderItem.title_snapshot, OrderItem.image_snapshot, Order.delivered_at
            )
            .join(Order, Order.id == OrderItem.order_id)
            .where(
                Order.user_id == user_id,
                Order.status == "delivered",
                OrderItem.product_id == product_id,
                OrderItem.id.not_in(reviewed_subq),
            )
            .order_by(OrderItem.created_at.desc())
        )
        rows = (await self.session.execute(stmt)).all()
        return [
            EligibleOrderItem(
                order_item_id=r[0], order_number=r[1], title_snapshot=r[2], image_snapshot=r[3], delivered_at=r[4]
            )
            for r in rows
        ]

    async def get_order_item_for_user(self, *, order_item_id: int, user_id: int) -> OrderItem | None:
        stmt = (
            select(OrderItem)
            .join(Order, Order.id == OrderItem.order_id)
            .where(OrderItem.id == order_item_id, Order.user_id == user_id, Order.status == "delivered")
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_own_review(self, *, product_id: int, user_id: int) -> Review | None:
        """A user can legitimately have more than one review for the same product — one per
        purchased line item (spec §9.7, `UNIQUE(product_id, user_id, order_item_id)`) — so a
        repeat purchaser who reviewed both deliveries would blow up a plain `scalar_one_or_none()`
        with MultipleResultsFound (caught live: Ada, product review-tested twice in this same
        session, hit exactly this on the eligibility endpoint). Surfacing all of a user's own
        reviews for one "which purchase is this" quick-edit affordance is a bigger UI change than
        this pass covers, so this returns just the most recent one — every review is still fully
        visible and editable through the ordinary review list, nothing is hidden."""
        stmt = (
            select(Review)
            .where(Review.product_id == product_id, Review.user_id == user_id)
            .order_by(Review.created_at.desc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_order_item(self, order_item_id: int) -> Review | None:
        stmt = select(Review).where(Review.order_item_id == order_item_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_id(self, review_id: int) -> Review | None:
        stmt = select(Review).where(Review.id == review_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_with_context(self, review_id: int) -> tuple[Review, Product, str] | None:
        stmt = (
            select(Review, Product, User.first_name, User.last_name)
            .join(Product, Product.id == Review.product_id)
            .join(User, User.id == Review.user_id)
            .where(Review.id == review_id)
        )
        row = (await self.session.execute(stmt)).first()
        if row is None:
            return None
        return row[0], row[1], _display_name(row[2], row[3])

    def add(self, review: Review) -> None:
        self.session.add(review)

    async def list_for_product(
        self, *, product_id: int, viewer_user_id: int | None, page: int, per_page: int
    ) -> tuple[list[tuple[Review, str]], int]:
        """Approved reviews for everyone, plus the viewer's own review regardless of its status
        (spec §9.7: "the author always sees their own pending review"). Returns (review, author
        display name) pairs, newest first."""
        visibility = Review.status == "approved"
        if viewer_user_id is not None:
            visibility = visibility | (Review.user_id == viewer_user_id)

        base = select(Review).where(Review.product_id == product_id, visibility)
        total = (await self.session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()

        stmt = (
            select(Review, User.first_name, User.last_name)
            .join(User, User.id == Review.user_id)
            .where(Review.product_id == product_id, visibility)
            .order_by(Review.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        rows = (await self.session.execute(stmt)).all()
        results = [(row[0], _display_name(row[1], row[2])) for row in rows]
        return results, total

    async def rating_breakdown(self, product_id: int) -> dict[int, int]:
        stmt = (
            select(Review.rating, func.count())
            .where(Review.product_id == product_id, Review.status == "approved")
            .group_by(Review.rating)
        )
        rows = (await self.session.execute(stmt)).all()
        return {int(rating): count for rating, count in rows}

    async def recompute_product_aggregates(self, product_id: int) -> tuple[float | None, int, int]:
        """Recomputes rating_avg/rating_count from APPROVED reviews only, and review_count from
        every review regardless of status (spec §8.3's distinct rating_count vs review_count
        columns) — called after any moderation decision (spec §9.7)."""
        approved_stmt = select(func.avg(Review.rating), func.count()).where(
            Review.product_id == product_id, Review.status == "approved"
        )
        rating_avg, rating_count = (await self.session.execute(approved_stmt)).one()
        total_stmt = select(func.count()).where(Review.product_id == product_id)
        review_count = (await self.session.execute(total_stmt)).scalar_one()
        return (float(rating_avg) if rating_avg is not None else None, rating_count, review_count)

    async def list_for_moderation(
        self, *, status: str | None, page: int, per_page: int
    ) -> tuple[list[tuple[Review, Product, str]], int]:
        base = select(Review)
        if status:
            base = base.where(Review.status == status)
        total = (await self.session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()

        stmt = (
            select(Review, Product, User.first_name, User.last_name)
            .join(Product, Product.id == Review.product_id)
            .join(User, User.id == Review.user_id)
        )
        if status:
            stmt = stmt.where(Review.status == status)
        stmt = stmt.order_by(Review.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
        rows = (await self.session.execute(stmt)).all()
        results = [(row[0], row[1], _display_name(row[2], row[3])) for row in rows]
        return results, total


def _display_name(first_name: str, last_name: str | None) -> str:
    initial = f" {last_name[0]}." if last_name else ""
    return f"{first_name}{initial}"
