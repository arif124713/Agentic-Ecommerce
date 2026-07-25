"""Test infrastructure (spec §24.4). Points the whole app at a dedicated `blackcart_test`
MySQL database instead of the dev DB — set via environment variables BEFORE any `app.*` module
is imported, since `app.core.config.get_settings()` is `@lru_cache`d and `app.db.session` builds
its engine at import time from whatever Settings resolves to at that moment.

Two isolation strategies, used by different tests:
- Most tests get `db_session`/`client`: a single DB connection wrapped in an outer transaction,
  with the SQLAlchemy session joining it in "create_savepoint" mode so the service layer's own
  `session.commit()` calls just close a savepoint instead of ending the outer transaction — the
  whole test's writes are rolled back at teardown. Fast, and no test can see another test's data.
- The inventory-concurrency test needs REAL separate DB connections (that's the whole point — it's
  testing MySQL's row locking under concurrent transactions), so it uses `real_client` instead,
  which does not override `get_db` at all and lets the app's normal connection pool do its job.
"""

import os

os.environ["MYSQL_DB"] = "blackcart_test"
os.environ["APP_ENV"] = "test"
# Headroom for the concurrency test's ~50 simultaneous requests, each wanting its own pooled
# connection under `real_client` — the default pool_size=10/max_overflow=5 would just make most
# of those 50 checkouts queue for a free connection rather than run concurrently.
os.environ["DATABASE_POOL_SIZE"] = "40"
os.environ["DATABASE_MAX_OVERFLOW"] = "40"

import asyncio  # noqa: E402
import decimal  # noqa: E402

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402
from ulid import ULID  # noqa: E402

from app.api.deps import get_db  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.timeutil import utcnow  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.main import app  # noqa: E402
from app.models.catalog import Brand, Category, Product, ProductVariant  # noqa: E402
from app.models.commerce import Address  # noqa: E402

settings = get_settings()


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    """The in-process rate limiter (core/rate_limit.py) keeps its counters in a plain module-level
    dict for the lifetime of the whole test process — without clearing it between tests, whichever
    test happens to run 6th-or-later against a 5/hour-limited endpoint (e.g. register, hit by
    nearly every test via register_and_login()) would get a spurious 429 depending on test order.
    Autouse so no individual test file needs to remember this."""
    from app.core.rate_limit import _buckets

    _buckets.clear()
    yield


def _make_engine(*, pool_size: int = 5, max_overflow: int = 5):
    return create_async_engine(
        settings.database_url, pool_size=pool_size, max_overflow=max_overflow, pool_pre_ping=True, echo=False
    )


async def _create_test_database() -> None:
    admin_url = f"mysql+aiomysql://{settings.mysql_user}:{settings.mysql_password}@{settings.mysql_host}:{settings.mysql_port}/"
    admin_engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    async with admin_engine.connect() as conn:
        await conn.exec_driver_sql(f"DROP DATABASE IF EXISTS `{settings.mysql_db}`")
        await conn.exec_driver_sql(
            f"CREATE DATABASE `{settings.mysql_db}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
        )
    await admin_engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def _prepare_database():
    """Fresh schema once per test run, via a throwaway engine that lives entirely inside this one
    `asyncio.run()` call. Deliberately NOT the module-level `app.db.session.engine`: pytest-asyncio
    gives every test function its own fresh event loop by default, and an async SQLAlchemy engine
    binds its internal asyncio primitives (pool locks, etc.) to whichever loop first touches it —
    reusing one engine across a session-scoped setup step and many function-scoped tests is the
    classic way to hit "Future attached to a different loop" errors. Each of db_session/client/
    real_client below instead builds and disposes its own engine within the current test's own
    loop, so nothing here is ever touched again after setup finishes."""

    async def _setup():
        await _create_test_database()
        setup_engine = _make_engine()
        try:
            async with setup_engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        finally:
            await setup_engine.dispose()

        # scripts.seed_rbac.seed() opens its own session via app.db.session.AsyncSessionLocal —
        # fine here since this whole function runs inside one throwaway asyncio.run() loop and
        # nothing else touches that module-level engine afterward.
        from scripts.seed_rbac import seed as seed_rbac

        await seed_rbac()

    asyncio.run(_setup())


@pytest_asyncio.fixture
async def db_session():
    test_engine = _make_engine()
    try:
        async with test_engine.connect() as conn:
            trans = await conn.begin()
            session = AsyncSession(bind=conn, join_transaction_mode="create_savepoint", expire_on_commit=False)
            try:
                yield session
            finally:
                await session.close()
                await trans.rollback()
    finally:
        await test_engine.dispose()


@pytest_asyncio.fixture
async def client(db_session):
    """Every request in a test shares the one rolled-back-at-teardown transaction above."""

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def real_db_session():
    """A plain, non-rolled-back session on its own engine — for setting up fixture data (e.g. a
    product) that must be visible to `real_client`'s independent per-request connections. Callers
    must `await session.commit()` explicitly; nothing here is torn down automatically."""
    test_engine = _make_engine()
    session_factory = async_sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)
    try:
        async with session_factory() as session:
            yield session
    finally:
        await test_engine.dispose()


@pytest_asyncio.fixture
async def real_client():
    """A dedicated per-test engine with real (non-shared, non-rolled-back) sessions — one per
    request, exactly like production — so concurrent requests genuinely contend for row locks
    instead of serialising through one shared session. Only the concurrency test should use this;
    everything it writes is real and stays committed, so that test cleans up its own rows."""
    test_engine = _make_engine(pool_size=60, max_overflow=20)
    session_factory = async_sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)

    async def _override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    finally:
        app.dependency_overrides.clear()
        await test_engine.dispose()


# -- fixture data helpers -----------------------------------------------------------------------


async def make_product_with_variant(
    session: AsyncSession,
    *,
    title: str = "Test Product",
    price: str = "999.00",
    mrp: str = "1999.00",
    stock: int = 10,
    search_keywords: str | None = None,
) -> tuple[Product, ProductVariant]:
    """Creates (and flushes) a minimal but real brand/category/product/variant chain — the
    checkout path touches brand.name/category on the product, so a bare Product() without these
    relationships populated would blow up mid-test with an unrelated-looking lazy-load error."""
    suffix = str(ULID())[-8:]
    brand = Brand(name=f"TestBrand-{suffix}", slug=f"testbrand-{suffix}", is_active=True)
    category = Category(name=f"TestCategory-{suffix}", slug=f"testcategory-{suffix}", path=f"/testcategory-{suffix}", depth=0)
    session.add_all([brand, category])
    await session.flush()

    product = Product(
        public_id=str(ULID()),
        slug=f"{title.lower().replace(' ', '-')}-{suffix}",
        title=title,
        brand_id=brand.id,
        category_id=category.id,
        currency="INR",
        mrp=decimal.Decimal(mrp),
        price=decimal.Decimal(price),
        stock_total=stock,
        status="active",
        search_keywords=search_keywords or title,
        published_at=utcnow(),
    )
    session.add(product)
    await session.flush()

    variant = ProductVariant(
        product_id=product.id,
        sku=f"SKU-{suffix}",
        size="M",
        mrp=decimal.Decimal(mrp),
        price=decimal.Decimal(price),
        stock=stock,
        is_active=True,
    )
    session.add(variant)
    await session.flush()
    return product, variant


async def make_address(session: AsyncSession, user_id: int) -> Address:
    address = Address(
        user_id=user_id,
        recipient_name="Test Recipient",
        phone="+8801700000000",
        division="Dhaka",
        city="Dhaka",
        street_line1="123 Test Street",
        is_default_shipping=True,
        is_default_billing=True,
    )
    session.add(address)
    await session.flush()
    return address


def unique_email(prefix: str = "test") -> str:
    return f"{prefix}-{ULID()!s}".lower() + "@example.com"


async def register_and_login(client: AsyncClient, *, email: str | None = None, password: str = "Str0ng!Passw0rd") -> dict:
    """Registers + logs in a fresh customer through the real endpoints (so the auth flow itself
    stays exercised by every other test that needs a logged-in user), returns the csrf token."""
    email = email or unique_email()
    resp = await client.post(
        "/api/v1/auth/register",
        json={"first_name": "Test", "last_name": "User", "email": email, "password": password},
    )
    assert resp.status_code == 201, resp.text
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    csrf = client.cookies.get("csrf_token")
    return {"email": email, "password": password, "csrf": csrf, "user": resp.json()["data"]}
