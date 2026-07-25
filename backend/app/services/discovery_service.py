import secrets

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.core.mail import get_mail_backend
from app.models.auth import User
from app.repositories.catalog import ProductRepository
from app.repositories.discovery import (
    NewsletterRepository,
    RecentlyViewedRepository,
    StockAlertRepository,
    WishlistRepository,
)
from app.schemas.discovery import WishlistItemOut, WishlistOut
from app.services.catalog.product_service import to_product_card


class WishlistService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.wishlists = WishlistRepository(session)
        self.products = ProductRepository(session)

    async def get(self, user_id: int) -> WishlistOut:
        pairs = await self.wishlists.list_products(user_id)
        return WishlistOut(items=[WishlistItemOut(item_id=item_id, product=to_product_card(p)) for p, item_id in pairs])

    async def slugs(self, user_id: int) -> list[str]:
        return await self.wishlists.list_slugs(user_id)

    async def add(self, user_id: int, product_slug: str) -> WishlistOut:
        product = await self.products.get_by_slug(product_slug)
        if product is None:
            raise NotFoundError(f"Product '{product_slug}' was not found.")
        await self.wishlists.add(user_id, product.id)
        return await self.get(user_id)

    async def remove(self, user_id: int, product_slug: str) -> WishlistOut:
        product = await self.products.get_by_slug(product_slug)
        if product is None:
            raise NotFoundError(f"Product '{product_slug}' was not found.")
        await self.wishlists.remove(user_id, product.id)
        return await self.get(user_id)


class RecentlyViewedService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.views = RecentlyViewedRepository(session)
        self.products = ProductRepository(session)

    async def record(self, user_id: int, product_slug: str) -> None:
        product = await self.products.get_by_slug(product_slug)
        if product is None:
            return  # a view ping for a since-deleted product is a no-op, not an error
        await self.views.record(user_id, product.id)

    async def list(self, user_id: int, *, exclude_slug: str | None = None, limit: int = 12) -> list:
        exclude_id = None
        if exclude_slug:
            excluded = await self.products.get_by_slug(exclude_slug)
            exclude_id = excluded.id if excluded else None
        products = await self.views.list_products(user_id, exclude_product_id=exclude_id, limit=limit)
        return [to_product_card(p) for p in products]


class StockAlertService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.alerts = StockAlertRepository(session)
        self.products = ProductRepository(session)

    async def subscribe(self, *, variant_id: int, email: str | None, user: User | None) -> None:
        resolved_email = email or (user.email if user else None)
        if not resolved_email:
            raise NotFoundError("An email address is required to set up a back-in-stock alert.")
        await self.alerts.subscribe(email=resolved_email, variant_id=variant_id, user_id=user.id if user else None)

    async def notify_restocked(self, variant_id: int, *, product_title: str, product_slug: str) -> int:
        """Called from admin inventory adjustment when a variant crosses 0 -> available
        (spec §9.8's StockReplenished event). Returns how many alerts were notified."""
        from app.core.config import get_settings

        settings = get_settings()
        pending = await self.alerts.pending_for_variant(variant_id)
        if not pending:
            return 0
        mail = get_mail_backend()
        link = f"{settings.app_base_url}/p/{product_slug}"
        for alert in pending:
            mail.send(
                to=alert.email,
                subject=f"{product_title} is back in stock",
                body=f"Good news — the item you wanted is back in stock: {link}",
            )
        await self.alerts.mark_notified(pending)
        return len(pending)


class NewsletterService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.subscribers = NewsletterRepository(session)

    async def subscribe(self, email: str) -> None:
        await self.subscribers.subscribe(email.lower().strip(), token=secrets.token_urlsafe(32))
