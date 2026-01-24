"""FastAPI routes for PilotLog API."""

import logging
from datetime import date
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from pilotlog.api.schemas import (
    AirportResponse,
    AirportStats,
    AirportsListResponse,
    FlightResponse,
    FlightsListResponse,
    ImportError,
    ImportResponse,
    ImportSummary,
    RollingResponse,
    RollingWindowStats,
    RouteStats,
    RoutesResponse,
    StatsResponse,
    AircraftTypeStats,
    YearStats,
    DateRange,
)
from pilotlog.database.connection import get_db
from pilotlog.database.queries import (
    get_airports,
    get_career_statistics,
    get_flights,
    get_rolling_totals,
    get_route_statistics,
    get_airport_statistics,
    get_statistics_by_aircraft_type,
    get_statistics_by_year,
)
from pilotlog.importers.swa_csv import SWACSVImporter

logger = logging.getLogger(__name__)

router = APIRouter()


def format_block_time(minutes: int) -> str:
    """Format minutes as H:MM."""
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours}:{mins:02d}"


@router.get("/flights", response_model=FlightsListResponse)
async def list_flights(
    db: Annotated[AsyncSession, Depends(get_db)],
    date_from: Optional[date] = Query(None, description="Filter flights on or after this date"),
    date_to: Optional[date] = Query(None, description="Filter flights on or before this date"),
    origin: Optional[str] = Query(None, description="Filter by origin airport"),
    destination: Optional[str] = Query(None, description="Filter by destination airport"),
    crew: Optional[str] = Query(None, description="Filter by crew name (partial match)"),
    tail: Optional[str] = Query(None, description="Filter by tail number"),
    aircraft_type: Optional[str] = Query(None, description="Filter by aircraft type"),
    limit: int = Query(100, ge=1, le=1000, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
):
    """Query flights with optional filters."""
    flights, total = await get_flights(
        db,
        date_from=date_from,
        date_to=date_to,
        origin=origin,
        destination=destination,
        crew=crew,
        tail=tail,
        aircraft_type=aircraft_type,
        limit=limit,
        offset=offset,
    )

    return FlightsListResponse(
        flights=[
            FlightResponse(
                id=f.id,
                flight_date=f.flight_date,
                flight_number=f.flight_number,
                origin=f.origin,
                destination=f.destination,
                block_minutes=f.block_minutes,
                block_formatted=format_block_time(f.block_minutes),
                tail_number=f.tail_number,
                aircraft_type=f.aircraft_type,
                crew_name=f.crew_name,
                crew_position=f.crew_position,
                is_deadhead=f.is_deadhead,
                pic_takeoff=f.pic_takeoff,
                pic_landing=f.pic_landing,
            )
            for f in flights
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    date_from: Optional[date] = Query(None, description="Filter range start"),
    date_to: Optional[date] = Query(None, description="Filter range end"),
):
    """Get aggregate career statistics."""
    career_stats = await get_career_statistics(db, date_from, date_to)
    by_aircraft = await get_statistics_by_aircraft_type(db, date_from, date_to)
    by_year = await get_statistics_by_year(db)

    return StatsResponse(
        total_flights=career_stats["total_flights"],
        total_block_minutes=career_stats["total_block_minutes"],
        total_block_formatted=career_stats["total_block_formatted"],
        unique_airports=career_stats["unique_airports"],
        unique_aircraft=career_stats["unique_aircraft"],
        date_range=DateRange(
            first_flight=career_stats["date_range"]["first_flight"],
            last_flight=career_stats["date_range"]["last_flight"],
        ),
        by_aircraft_type=[
            AircraftTypeStats(type=a["type"], flights=a["flights"], minutes=a["minutes"])
            for a in by_aircraft
        ],
        by_year=[
            YearStats(year=y["year"], flights=y["flights"], minutes=y["minutes"])
            for y in by_year
        ],
    )


@router.get("/rolling", response_model=RollingResponse)
async def get_rolling(
    db: Annotated[AsyncSession, Depends(get_db)],
    as_of: Optional[date] = Query(None, description="Calculate as of this date (default: today)"),
):
    """Get rolling window totals."""
    as_of_date = as_of or date.today()
    # 672 hours = 28 days (FAR 117 lookback)
    windows = [7, 28, 60, 90, 365]

    rolling = await get_rolling_totals(db, as_of_date, windows)

    return RollingResponse(
        as_of=as_of_date.isoformat(),
        windows={
            str(w): RollingWindowStats(
                flights=rolling[w]["flights"],
                minutes=rolling[w]["minutes"],
                formatted=rolling[w]["formatted"],
            )
            for w in windows
        },
    )


@router.get("/routes", response_model=RoutesResponse)
async def get_routes(
    db: Annotated[AsyncSession, Depends(get_db)],
    date_from: Optional[date] = Query(None, description="Filter range start"),
    date_to: Optional[date] = Query(None, description="Filter range end"),
):
    """Get aggregated route data for map visualization."""
    route_stats = await get_route_statistics(db, date_from, date_to)
    airport_stats = await get_airport_statistics(db, date_from, date_to)

    return RoutesResponse(
        routes=[
            RouteStats(
                origin=r["origin"],
                destination=r["destination"],
                count=r["count"],
                total_minutes=r["total_minutes"],
                first_flown=r["first_flown"],
                last_flown=r["last_flown"],
            )
            for r in route_stats
        ],
        airports=[
            AirportStats(
                icao=a["icao"],
                name=a["name"],
                latitude=a["latitude"],
                longitude=a["longitude"],
                departures=a["departures"],
                arrivals=a["arrivals"],
            )
            for a in airport_stats
        ],
    )


@router.post("/import", response_model=ImportResponse)
async def import_csv(
    db: Annotated[AsyncSession, Depends(get_db)],
    file: UploadFile = File(..., description="CSV file to import"),
):
    """Import a CSV file."""
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV file")

    # Save uploaded file to temp location
    content = await file.read()

    with NamedTemporaryFile(mode="wb", suffix=".csv", delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        # Import the file
        importer = SWACSVImporter()
        result = await importer.import_file(tmp_path, db)

        # Build date range string
        date_range = ""
        if result.date_range_start and result.date_range_end:
            date_range = f"{result.date_range_start} to {result.date_range_end}"

        return ImportResponse(
            batch_id=result.batch_id,
            filename=result.filename,
            rows_processed=result.rows_processed,
            rows_imported=result.rows_imported,
            rows_skipped=result.rows_skipped,
            rows_duplicate=result.rows_duplicate,
            errors=[ImportError(row=e["row"], message=e["message"]) for e in result.errors],
            summary=ImportSummary(
                new_block_minutes=result.new_block_minutes,
                new_block_formatted=result.new_block_formatted,
                date_range=date_range,
            ),
        )
    finally:
        # Clean up temp file
        tmp_path.unlink(missing_ok=True)


@router.get("/airports", response_model=AirportsListResponse)
async def list_airports(
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get airport lookup data."""
    airports = await get_airports(db)

    return AirportsListResponse(
        airports=[
            AirportResponse(
                icao=a.icao,
                iata=a.iata,
                name=a.name,
                city=a.city,
                latitude=a.latitude,
                longitude=a.longitude,
            )
            for a in airports
        ]
    )


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
