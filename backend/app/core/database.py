"""
Async database configuration and session management.
"""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from app.config.settings import settings

# Create async SQLAlchemy engine
# Convert sync PostgreSQL URL to async
if settings.DATABASE_URL.startswith("postgresql://"):
    async_database_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
elif settings.DATABASE_URL.startswith("postgres://"):
    async_database_url = settings.DATABASE_URL.replace("postgres://", "postgresql+asyncpg://")
else:
    async_database_url = settings.DATABASE_URL

engine = create_async_engine(async_database_url, pool_pre_ping=True, pool_size=10, max_overflow=20)

# Create AsyncSession factory
AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False, autocommit=False, autoflush=False
)

# Create Base class for models
Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency function to get async database session for FastAPI dependency injection.

    Yields:
        AsyncSession: SQLAlchemy async database session
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
