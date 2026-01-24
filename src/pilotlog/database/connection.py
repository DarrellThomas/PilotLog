"""Database connection and session management."""

import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncGenerator

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from pilotlog.config import settings
from pilotlog.database.models import Base, SchemaVersion

logger = logging.getLogger(__name__)

CURRENT_SCHEMA_VERSION = 1

# Create async engine
engine = create_async_engine(
    f"sqlite+aiosqlite:///{settings.db_path}",
    echo=False,
)

# Session factory
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Enable SQLite WAL mode and foreign keys."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


async def init_db() -> None:
    """Initialize the database, creating tables if they don't exist."""
    settings.ensure_directories()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Initialize schema version if needed
    async with async_session() as session:
        result = await session.execute(text("SELECT version FROM schema_version LIMIT 1"))
        version_row = result.fetchone()

        if version_row is None:
            schema_version = SchemaVersion(
                version=CURRENT_SCHEMA_VERSION, applied_at=datetime.utcnow()
            )
            session.add(schema_version)
            await session.commit()
            logger.info(f"Database initialized with schema version {CURRENT_SCHEMA_VERSION}")
        else:
            logger.info(f"Database schema version: {version_row[0]}")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting database sessions."""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for database sessions."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
