"""Pytest configuration and fixtures."""

import asyncio
from pathlib import Path
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from pilotlog.database.models import Base


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create an in-memory database session for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        yield session

    await engine.dispose()


@pytest.fixture
def fixtures_dir() -> Path:
    """Return the path to the test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_csv_content() -> str:
    """Return sample SWA CSV content for testing."""
    return """TotalBlockhrsmins
10:30

TAFB_RadialScale1_MinimumValue,TAFB_RadialScale1_MaximumValue,TAFB_RadialPointer2_GaugeInputValue,TAFB_RadialRange1_StartValue,TAFB_RadialRange1_EndValue
0,1000,10,800,1000

DATE,Flight,dhd,From,Depart,To,Arrive,Block,Tail_Number,A_C_Type,TakeOff,Landing,CoPilot
2025-01-10,WN1052,,KHOU,8:58,KSAN,12:10,312,N8867Q,737-7M8,1,1,FO  ZURCA JULIAN [114706]
2025-01-10,WN2361,,KSAN,13:25,KMSY,16:58,333,N8772M,737-7T8, , ,FO  ZURCA JULIAN [114706]
2025-01-12,WN1203,DH,MROC,14:23,KHOU,17:50,0,N8318F,737-738, , ,Deadheading
"""
