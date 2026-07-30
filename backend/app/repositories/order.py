from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.catalog import Product, ProductVariant
from app.models.commerce import Order, OrderStatusHistory, Payment, PaymentEvent, Refund, Shipment, ShipmentEvent


class OrderRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    def add(self, order: Order) -> None:
        self.session.add(order)

    def add_status(self, entry: OrderStatusHistory) -> None:
        self.session.add(entry)

    async def get_by_idempotency_key(self, key: str) -> Order | None:
        stmt = select(Order).where(Order.idempotency_key == key).options(selectinload(Order.items))
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_order_number(self, order_number: str, *, user_id: int | None = None) -> Order | None:
        stmt = select(Order).where(Order.order_number == order_number).options(selectinload(Order.items))
        if user_id is not None:
            stmt = stmt.where(Order.user_id == user_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_id(self, order_id: int) -> Order | None:
        stmt = (
            select(Order)
            .where(Order.id == order_id)
            .options(selectinload(Order.items))
            .execution_options(populate_existing=True)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_for_user(self, user_id: int, *, page: int, per_page: int) -> tuple[list[Order], int]:
        base = select(Order).where(Order.user_id == user_id)
        total = (await self.session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
        stmt = (
            base.options(selectinload(Order.items))
            .order_by(Order.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        return list((await self.session.execute(stmt)).scalars().all()), total

    async def lock_variants(self, variant_ids: list[int]) -> dict[int, ProductVariant]:
        """SELECT ... FOR UPDATE, ordered by id, so concurrent checkouts touching overlapping
        variants can never deadlock (spec §9.4).

        `populate_existing=True` is load-bearing, not cosmetic: the caller always already has
        this same cart's `CartItem.variant` eager-loaded (see CartRepository's selectinload
        chain) by the time this runs, so the ProductVariant row is already sitting in the
        session's identity map with whatever `.stock` it had *before* this lock was acquired.
        Without this option, SQLAlchemy's default "don't clobber already-loaded state" behaviour
        means the FOR UPDATE lock is real at the database level (it does block a concurrent
        transaction) but the freshly-locked, freshly-committed row data coming back from this
        query is silently discarded in favour of the stale cached object — every concurrent
        request reads the same pre-lock stock value, and the last writer to commit wins,
        clobbering everyone else's decrement. That's a real lost-update oversell bug, caught by
        the 50-concurrent-checkouts test (spec §9.4/§24.3) — see done.MD.

        The eager-load options below matter for the same reason: populate_existing refreshes the
        *whole* object, which would otherwise expire the already-loaded `.product`/`.product.brand`
        relationships the caller reads right after this (e.g. order-line snapshots) — an expired
        relationship triggers an implicit lazy-load on next access, illegal under async
        SQLAlchemy outside an awaited context (MissingGreenlet)."""
        stmt = (
            select(ProductVariant)
            .where(ProductVariant.id.in_(variant_ids))
            .order_by(ProductVariant.id)
            .with_for_update()
            .options(selectinload(ProductVariant.product).selectinload(Product.brand))
            .execution_options(populate_existing=True)
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        return {v.id: v for v in rows}

    async def get_status_history(self, order_id: int) -> list[OrderStatusHistory]:
        stmt = (
            select(OrderStatusHistory)
            .where(OrderStatusHistory.order_id == order_id)
            .order_by(OrderStatusHistory.created_at)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_all(
        self, *, status: str | None, q: str | None, page: int, per_page: int
    ) -> tuple[list[Order], int]:
        stmt = select(Order)
        if status:
            stmt = stmt.where(Order.status == status)
        if q:
            like = f"%{q}%"
            stmt = stmt.where(or_(Order.order_number.ilike(like), Order.customer_email.ilike(like)))

        total = (await self.session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
        stmt = (
            stmt.options(selectinload(Order.items))
            .order_by(Order.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        return list((await self.session.execute(stmt)).scalars().all()), total


class PaymentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    def add(self, payment: Payment) -> None:
        self.session.add(payment)

    def add_event(self, event: PaymentEvent) -> None:
        self.session.add(event)

    async def get_by_order(self, order_id: int) -> Payment | None:
        # populate_existing=True is load-bearing, not cosmetic: the payment webhook (spec §12.5)
        # settles this row on its own DB session/transaction, so the calling session's identity
        # map still holds the pre-webhook object (e.g. status="processing") unless forced to
        # refresh — the exact same stale-object trap as lock_variants() above, just for payments
        # instead of stock. Without this, create_order()'s own response showed order.status
        # "confirmed" next to a nested payment.status still "processing" — caught by a live curl
        # check, not by pytest (see done.MD).
        stmt = (
            select(Payment)
            .where(Payment.order_id == order_id)
            .order_by(Payment.created_at.desc())
            .execution_options(populate_existing=True)
        )
        return (await self.session.execute(stmt)).scalars().first()

    async def get_event_by_id(self, event_id: str) -> PaymentEvent | None:
        stmt = select(PaymentEvent).where(PaymentEvent.event_id == event_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()


class ShipmentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    def add(self, shipment: Shipment) -> None:
        self.session.add(shipment)

    def add_event(self, event: ShipmentEvent) -> None:
        self.session.add(event)

    async def get_by_order(self, order_id: int) -> Shipment | None:
        stmt = (
            select(Shipment)
            .where(Shipment.order_id == order_id)
            .options(selectinload(Shipment.events))
            .execution_options(populate_existing=True)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()


class RefundRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    def add(self, refund: Refund) -> None:
        self.session.add(refund)

    async def total_refunded(self, order_id: int) -> int:
        stmt = select(func.count()).where(Refund.order_id == order_id)
        return (await self.session.execute(stmt)).scalar_one()
