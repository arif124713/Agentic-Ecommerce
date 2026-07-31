from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_mysql_ssl_connect_args, get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    pool_pre_ping=True,
    # Vercel's Python serverless runtime scales to zero and can spin up many concurrent function
    # instances, each holding its own small pool — recycling proactively (default 280s, under most
    # managed MySQL providers' idle-connection timeout) avoids "MySQL server has gone away" on a
    # pooled connection that's been sitting idle since the previous invocation. A no-op locally
    # (native dev MySQL doesn't drop idle connections that fast).
    pool_recycle=settings.database_pool_recycle_seconds,
    connect_args=get_mysql_ssl_connect_args(settings),
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
