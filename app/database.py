"""Async database utilities for whatsapp-emovur.

Provides an async SQLAlchemy engine, session factory, and a helper to create tables.
"""
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from pathlib import Path
import logging

from .models import Base
from .config import get_settings


logger = logging.getLogger(__name__)

settings = get_settings()

# Default sqlite file in project root
DB_FILE = Path("./whatsapp_emovur.db").resolve()
DATABASE_URL = f"sqlite+aiosqlite:///{DB_FILE.as_posix()}"

# Create async engine
engine = create_async_engine(DATABASE_URL, echo=False, future=True)

# Async session factory
AsyncSessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


async def migrate_db() -> None:
    """Migrate the database schema by adding missing columns to the candidates table."""
    try:
        async with engine.begin() as conn:
            def _migrate(sync_conn):
                result = sync_conn.exec_driver_sql("PRAGMA table_info(candidates)")
                columns = [row[1] for row in result.fetchall()]
                
                migrations = [
                    ("candidate_response", "TEXT"),
                    ("response_received_at", "DATETIME"),
                    ("message_id", "VARCHAR(128)"),
                    ("reminder1_sent", "INTEGER NOT NULL DEFAULT 0"),
                    ("reminder2_sent", "INTEGER NOT NULL DEFAULT 0"),
                ]
                
                for col_name, col_type in migrations:
                    if col_name not in columns:
                        logger.info("Database migration: adding column %s to candidates table", col_name)
                        sync_conn.exec_driver_sql(f"ALTER TABLE candidates ADD COLUMN {col_name} {col_type}")
                        
            await conn.run_sync(_migrate)
    except Exception as exc:
        logger.exception("Failed to migrate database: %s", exc)
        raise


async def init_db() -> None:
    """Create all database tables and migrate schema. Safe to call on startup."""
    try:
        async with engine.begin() as conn:
            # run_sync executes the given callable in sync context
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables verified/created: %s", DB_FILE)
        await migrate_db()
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
