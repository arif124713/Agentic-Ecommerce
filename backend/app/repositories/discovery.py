from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.timeutil import utcnow
from app.models.catalog import Product
from app.models.discovery import NewsletterSubscriber, RecentlyViewed, StockAlert, Wishlist, WishlistItem


class WishlistRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _get_or_create(self, user_id: int) -> Wishlist:
        stmt = select(Wishlist).where(Wishlist.user_id == user_id)
        wishlist = (await self.session.execute(stmt)).scalar_one_or_none()
        if wishlist is not None:
            return wishlist
        wishlist = Wishlist(user_id=user_id, created_at=utcnow())
        self.session.add(wishlist)
        await self.session.flush()
        return wishlist

    async def list_products(self, user_id: int) -> list[tuple[Product, int]]:
        """Returns (product, wishlist_item_id) pairs, most recently added first."""
        stmt = (
            select(Product, WishlistItem.id)
            .join(WishlistItem, WishlistItem.product_id == Product.id)
            .join(Wishlist, Wishlist.id == WishlistItem.wishlist_id)
            .where(Wishlist.user_id == user_id, Product.deleted_at.is_(None))
            .options(selectinload(Product.brand))
            .order_by(WishlistItem.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]

    async def list_slugs(self, user_id: int) -> list[str]:
        stmt = (
            select(Product.slug)
            .join(WishlistItem, WishlistItem.product_id == Product.id)
            .join(Wishlist, Wishlist.id == WishlistItem.wishlist_id)
            .where(Wishlist.user_id == user_id)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def add(self, user_id: int, product_id: int) -> None:
        wishlist = await self._get_or_create(user_id)
        exists_stmt = select(WishlistItem).where(
            WishlistItem.wishlist_id == wishlist.id, WishlistItem.product_id == product_id
        )
        if (await self.session.execute(exists_stmt)).scalar_one_or_none() is not None:
            return
        self.session.add(WishlistItem(wishlist_id=wishlist.id, product_id=product_id, created_at=utcnow()))
        await self.session.commit()

    async def remove(self, user_id: int, product_id: int) -> None:
        wishlist = await self._get_or_create(user_id)
        await self.session.execute(
            delete(WishlistItem).where(
                WishlistItem.wishlist_id == wishlist.id, WishlistItem.product_id == product_id
            )
        )
        await self.session.commit()


class RecentlyViewedRepository:
    MAX_PER_USER = 50

    def __init__(self, session: AsyncSession):
        self.session = session

    async def record(self, user_id: int, product_id: int) -> None:
        existing = (
            await self.session.execute(
                select(RecentlyViewed).where(
                    RecentlyViewed.user_id == user_id, RecentlyViewed.product_id == product_id
                )
            )
        ).scalar_one_or_none()
        now = utcnow()
        if existing is not None:
            existing.viewed_at = now
        else:
            self.session.add(RecentlyViewed(user_id=user_id, product_id=product_id, viewed_at=now))
        await self.session.commit()

        # Cap at MAX_PER_USER (spec §8.5's retention rule) — cheap enough to do inline since
        # there's no Celery to run it as a batch job.
        overflow_stmt = (
            select(RecentlyViewed.id)
            .where(RecentlyViewed.user_id == user_id)
            .order_by(RecentlyViewed.viewed_at.desc())
            .offset(self.MAX_PER_USER)
        )
        overflow_ids = list((await self.session.execute(overflow_stmt)).scalars().all())
        if overflow_ids:
            await self.session.execute(delete(RecentlyViewed).where(RecentlyViewed.id.in_(overflow_ids)))
            await self.session.commit()

    async def list_products(self, user_id: int, *, exclude_product_id: int | None = None, limit: int = 12) -> list[Product]:
        stmt = (
            select(Product)
            .join(RecentlyViewed, RecentlyViewed.product_id == Product.id)
            .where(
                RecentlyViewed.user_id == user_id,
                Product.status == "active",
                Product.deleted_at.is_(None),
            )
            .options(selectinload(Product.brand))
            .order_by(RecentlyViewed.viewed_at.desc())
            .limit(limit + 1 if exclude_product_id else limit)
        )
        result = await self.session.execute(stmt)
        products = list(result.scalars().all())
        if exclude_product_id is not None:
            products = [p for p in products if p.id != exclude_product_id][:limit]
        return products


class StockAlertRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def subscribe(self, *, email: str, variant_id: int, user_id: int | None) -> None:
        existing = (
            await self.session.execute(
                select(StockAlert).where(StockAlert.email == email, StockAlert.variant_id == variant_id)
            )
        ).scalar_one_or_none()
        if existing is not None:
            if existing.notified_at is not None:
                existing.notified_at = None  # re-subscribing after a previous notification
            await self.session.commit()
            return
        self.session.add(
            StockAlert(user_id=user_id, email=email, variant_id=variant_id, created_at=utcnow())
        )
        await self.session.commit()

    async def pending_for_variant(self, variant_id: int) -> list[StockAlert]:
        stmt = select(StockAlert).where(StockAlert.variant_id == variant_id, StockAlert.notified_at.is_(None))
        return list((await self.session.execute(stmt)).scalars().all())

    async def mark_notified(self, alerts: list[StockAlert]) -> None:
        now = utcnow()
        for alert in alerts:
            alert.notified_at = now
        await self.session.commit()


class NewsletterRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def subscribe(self, email: str, token: str) -> NewsletterSubscriber:
        existing = (
            await self.session.execute(select(NewsletterSubscriber).where(NewsletterSubscriber.email == email))
        ).scalar_one_or_none()
        if existing is not None:
            existing.status = "subscribed"
            existing.unsubscribed_at = None
            await self.session.commit()
            return existing
        subscriber = NewsletterSubscriber(email=email, token=token, created_at=utcnow())
        self.session.add(subscriber)
        await self.session.commit()
        return subscriber
