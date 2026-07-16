"""Async database utilities for whatsapp-emovur.

Provides an async SQLAlchemy engine, session factory, and a helper to create tables.
"""
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from pathlib import Path
import logging

from .models import Base


logger = logging.getLogger(__name__)

# Default sqlite file in project root
DB_FILE = Path("./whatsapp_emovur.db").resolve()
DATABASE_URL = f"sqlite+aiosqlite:///{DB_FILE.as_posix()}"

# Create async engine
engine = create_async_engine(DATABASE_URL, echo=False, future=True)

# Async session factory
AsyncSessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    """Create the webhook idempotency table. Safe to call on startup."""
    try:
        async with engine.begin() as conn:
            # run_sync executes the given callable in sync context
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables verified/created: %s", DB_FILE)
    except Exception as exc:
        logger.exception("Failed to initialize database: %s", exc)
        raise


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an Async SQLAlchemy session (dependency).

    Usage with FastAPI dependency injection:
        async def endpoint(db: AsyncSession = Depends(get_session)):
            ...
    """
    async with AsyncSessionLocal() as session:
        yield session
