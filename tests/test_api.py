"""Tests for FastAPI API endpoints."""

from datetime import date
from pathlib import Path
from tempfile import NamedTemporaryFile

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from pilotlog.main import create_app
from pilotlog.database.models import Flight
from pilotlog.database.connection import get_db


@pytest.fixture
def app(db_session):
    """Create test application with overridden database dependency."""
    app = create_app()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    return app


@pytest.fixture
async def client(app):
    """Create test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
async def sample_flights(db_session):
    """Create sample flights in the database."""
    flights = [
        Flight(
            source="swa",
            flight_date="2025-01-10",
            flight_number="WN1052",
            origin="KHOU",
            destination="KSAN",
            block_minutes=312,
            tail_number="N8867Q",
            aircraft_type="B737-MAX7",
            is_deadhead=False,
            pic_takeoff=True,
            pic_landing=True,
            crew_name="ZURCA JULIAN",
            crew_id="114706",
        ),
        Flight(
            source="swa",
            flight_date="2025-01-10",
            flight_number="WN2361",
            origin="KSAN",
            destination="KMSY",
            block_minutes=333,
            tail_number="N8772M",
            aircraft_type="B737-MAX7",
            is_deadhead=False,
            crew_name="ZURCA JULIAN",
            crew_id="114706",
        ),
        Flight(
            source="swa",
            flight_date="2025-01-15",
            flight_number="WN100",
            origin="KHOU",
            destination="KDEN",
            block_minutes=200,
            tail_number="N12345",
            aircraft_type="B737-700",
            is_deadhead=False,
            crew_name="SMITH JOHN",
            crew_id="99999",
        ),
    ]

    for flight in flights:
        db_session.add(flight)
    await db_session.commit()

    return flights


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    @pytest.mark.asyncio
    async def test_health_check(self, client):
        """Test health check returns healthy status."""
        response = await client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


class TestFlightsEndpoint:
    """Tests for flights endpoint."""

    @pytest.mark.asyncio
    async def test_get_flights_empty(self, client):
        """Test getting flights when database is empty."""
        response = await client.get("/api/flights")
        assert response.status_code == 200
        data = response.json()
        assert data["flights"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_get_flights_with_data(self, client, sample_flights):
        """Test getting flights with data."""
        response = await client.get("/api/flights")
        assert response.status_code == 200
        data = response.json()
        assert len(data["flights"]) == 3
        assert data["total"] == 3

    @pytest.mark.asyncio
    async def test_get_flights_filter_by_crew(self, client, sample_flights):
        """Test filtering flights by crew name."""
        response = await client.get("/api/flights?crew=ZURCA")
        assert response.status_code == 200
        data = response.json()
        assert len(data["flights"]) == 2
        for flight in data["flights"]:
            assert "ZURCA" in flight["crew_name"]

    @pytest.mark.asyncio
    async def test_get_flights_filter_by_date(self, client, sample_flights):
        """Test filtering flights by date range."""
        response = await client.get("/api/flights?date_from=2025-01-12")
        assert response.status_code == 200
        data = response.json()
        assert len(data["flights"]) == 1
        assert data["flights"][0]["flight_date"] == "2025-01-15"

    @pytest.mark.asyncio
    async def test_get_flights_pagination(self, client, sample_flights):
        """Test flight pagination."""
        response = await client.get("/api/flights?limit=2&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert len(data["flights"]) == 2
        assert data["total"] == 3
        assert data["limit"] == 2
        assert data["offset"] == 0


class TestStatsEndpoint:
    """Tests for statistics endpoint."""

    @pytest.mark.asyncio
    async def test_get_stats_empty(self, client):
        """Test getting stats when database is empty."""
        response = await client.get("/api/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total_flights"] == 0
        assert data["total_block_minutes"] == 0

    @pytest.mark.asyncio
    async def test_get_stats_with_data(self, client, sample_flights):
        """Test getting stats with data."""
        response = await client.get("/api/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total_flights"] == 3
        assert data["total_block_minutes"] == 312 + 333 + 200


class TestRollingEndpoint:
    """Tests for rolling totals endpoint."""

    @pytest.mark.asyncio
    async def test_get_rolling(self, client, sample_flights):
        """Test getting rolling totals."""
        response = await client.get("/api/rolling?as_of=2025-01-20")
        assert response.status_code == 200
        data = response.json()
        assert data["as_of"] == "2025-01-20"
        assert "7" in data["windows"]
        assert "30" in data["windows"]
        assert "365" in data["windows"]


class TestRoutesEndpoint:
    """Tests for routes endpoint."""

    @pytest.mark.asyncio
    async def test_get_routes_empty(self, client):
        """Test getting routes when database is empty."""
        response = await client.get("/api/routes")
        assert response.status_code == 200
        data = response.json()
        assert data["routes"] == []
        assert data["airports"] == []

    @pytest.mark.asyncio
    async def test_get_routes_with_data(self, client, sample_flights):
        """Test getting routes with data."""
        response = await client.get("/api/routes")
        assert response.status_code == 200
        data = response.json()
        assert len(data["routes"]) == 3  # 3 unique city pairs


class TestImportEndpoint:
    """Tests for import endpoint."""

    @pytest.mark.asyncio
    async def test_import_invalid_file_type(self, client):
        """Test importing non-CSV file."""
        response = await client.post(
            "/api/import",
            files={"file": ("test.txt", b"not a csv", "text/plain")},
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_import_csv(self, client, sample_csv_content):
        """Test importing a valid CSV file."""
        response = await client.post(
            "/api/import",
            files={"file": ("test.csv", sample_csv_content.encode(), "text/csv")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["rows_processed"] == 3
        assert data["rows_imported"] == 3
