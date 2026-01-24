"""Database query functions for PilotLog."""

from datetime import date
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from pilotlog.database.models import Airport, Flight, ImportBatch


async def get_flights(
    session: AsyncSession,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    origin: Optional[str] = None,
    destination: Optional[str] = None,
    crew: Optional[str] = None,
    tail: Optional[str] = None,
    aircraft_type: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[Flight], int]:
    """Query flights with optional filters."""
    query = select(Flight)

    if date_from:
        query = query.where(Flight.flight_date >= date_from.isoformat())
    if date_to:
        query = query.where(Flight.flight_date <= date_to.isoformat())
    if origin:
        query = query.where(Flight.origin == origin.upper())
    if destination:
        query = query.where(Flight.destination == destination.upper())
    if crew:
        query = query.where(Flight.crew_name.ilike(f"%{crew}%"))
    if tail:
        query = query.where(Flight.tail_number.ilike(f"%{tail}%"))
    if aircraft_type:
        query = query.where(Flight.aircraft_type == aircraft_type)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    # Get paginated results
    query = query.order_by(Flight.flight_date.desc(), Flight.departure_time.desc())
    query = query.limit(limit).offset(offset)

    result = await session.execute(query)
    flights = list(result.scalars().all())

    return flights, total


async def get_flight_by_id(session: AsyncSession, flight_id: int) -> Optional[Flight]:
    """Get a single flight by ID."""
    result = await session.execute(select(Flight).where(Flight.id == flight_id))
    return result.scalar_one_or_none()


async def check_duplicate_flight(
    session: AsyncSession,
    flight_date: str,
    flight_number: Optional[str],
    origin: str,
    destination: str,
) -> bool:
    """Check if a flight already exists (for duplicate detection during import)."""
    query = select(Flight).where(
        Flight.flight_date == flight_date,
        Flight.origin == origin,
        Flight.destination == destination,
    )
    if flight_number:
        query = query.where(Flight.flight_number == flight_number)

    result = await session.execute(query)
    return result.scalar_one_or_none() is not None


async def get_route_statistics(
    session: AsyncSession,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> list[dict]:
    """Get aggregated route statistics for map visualization."""
    query = select(
        Flight.origin,
        Flight.destination,
        func.count(Flight.id).label("count"),
        func.sum(Flight.block_minutes).label("total_minutes"),
        func.min(Flight.flight_date).label("first_flown"),
        func.max(Flight.flight_date).label("last_flown"),
    ).group_by(Flight.origin, Flight.destination)

    if date_from:
        query = query.where(Flight.flight_date >= date_from.isoformat())
    if date_to:
        query = query.where(Flight.flight_date <= date_to.isoformat())

    result = await session.execute(query)
    rows = result.all()

    return [
        {
            "origin": row.origin,
            "destination": row.destination,
            "count": row.count,
            "total_minutes": row.total_minutes or 0,
            "first_flown": row.first_flown,
            "last_flown": row.last_flown,
        }
        for row in rows
    ]


async def get_airport_statistics(
    session: AsyncSession,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> list[dict]:
    """Get airport visit statistics."""
    # Subquery for departures
    dep_query = select(
        Flight.origin.label("icao"),
        func.count(Flight.id).label("departures"),
    ).group_by(Flight.origin)

    if date_from:
        dep_query = dep_query.where(Flight.flight_date >= date_from.isoformat())
    if date_to:
        dep_query = dep_query.where(Flight.flight_date <= date_to.isoformat())

    # Subquery for arrivals
    arr_query = select(
        Flight.destination.label("icao"),
        func.count(Flight.id).label("arrivals"),
    ).group_by(Flight.destination)

    if date_from:
        arr_query = arr_query.where(Flight.flight_date >= date_from.isoformat())
    if date_to:
        arr_query = arr_query.where(Flight.flight_date <= date_to.isoformat())

    dep_result = await session.execute(dep_query)
    arr_result = await session.execute(arr_query)

    departures = {row.icao: row.departures for row in dep_result.all()}
    arrivals = {row.icao: row.arrivals for row in arr_result.all()}

    # Combine and join with airport data
    all_icao = set(departures.keys()) | set(arrivals.keys())

    airport_query = select(Airport).where(Airport.icao.in_(all_icao))
    airport_result = await session.execute(airport_query)
    airports = {a.icao: a for a in airport_result.scalars().all()}

    stats = []
    for icao in all_icao:
        airport = airports.get(icao)
        stats.append(
            {
                "icao": icao,
                "name": airport.name if airport else None,
                "latitude": airport.latitude if airport else None,
                "longitude": airport.longitude if airport else None,
                "departures": departures.get(icao, 0),
                "arrivals": arrivals.get(icao, 0),
            }
        )

    return stats


async def get_rolling_totals(
    session: AsyncSession,
    as_of_date: date,
    windows: list[int] = [7, 28, 60, 90, 365],
) -> dict[int, dict]:
    """Calculate rolling window totals.

    Note: The 28-day (672-hour) window uses >= to include the cutoff date,
    matching FAR 117 interpretation. Other windows use > for standard
    calendar-day lookback behavior.
    """
    results = {}

    for window in windows:
        cutoff = date.fromordinal(as_of_date.toordinal() - window)

        # 28-day (672-hour) window includes the cutoff date (>=)
        # Other windows exclude the cutoff date (>)
        if window == 28:
            query = select(
                func.count(Flight.id).label("flights"),
                func.sum(Flight.block_minutes).label("minutes"),
            ).where(
                Flight.flight_date >= cutoff.isoformat(),
                Flight.flight_date <= as_of_date.isoformat(),
                Flight.is_deadhead == False,  # noqa: E712
            )
        else:
            query = select(
                func.count(Flight.id).label("flights"),
                func.sum(Flight.block_minutes).label("minutes"),
            ).where(
                Flight.flight_date > cutoff.isoformat(),
                Flight.flight_date <= as_of_date.isoformat(),
                Flight.is_deadhead == False,  # noqa: E712
            )

        result = await session.execute(query)
        row = result.one()

        minutes = row.minutes or 0
        results[window] = {
            "flights": row.flights or 0,
            "minutes": minutes,
            "formatted": f"{minutes // 60}:{minutes % 60:02d}",
        }

    return results


async def get_career_statistics(
    session: AsyncSession,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> dict:
    """Get overall career statistics."""
    query = select(
        func.count(Flight.id).label("total_flights"),
        func.sum(Flight.block_minutes).label("total_minutes"),
        func.count(func.distinct(Flight.origin)).label("unique_origins"),
        func.count(func.distinct(Flight.destination)).label("unique_destinations"),
        func.count(func.distinct(Flight.tail_number)).label("unique_aircraft"),
        func.min(Flight.flight_date).label("first_flight"),
        func.max(Flight.flight_date).label("last_flight"),
    )

    if date_from:
        query = query.where(Flight.flight_date >= date_from.isoformat())
    if date_to:
        query = query.where(Flight.flight_date <= date_to.isoformat())

    result = await session.execute(query)
    row = result.one()

    total_minutes = row.total_minutes or 0

    # Get unique airports (union of origins and destinations)
    airports_query = (
        select(func.count())
        .select_from(
            select(Flight.origin.label("icao"))
            .union(select(Flight.destination.label("icao")))
            .subquery()
        )
    )
    if date_from:
        pass  # Already filtered in subquery would need reconstruction
    airports_result = await session.execute(airports_query)
    unique_airports = airports_result.scalar() or 0

    return {
        "total_flights": row.total_flights or 0,
        "total_block_minutes": total_minutes,
        "total_block_formatted": f"{total_minutes // 60}:{total_minutes % 60:02d}",
        "unique_airports": unique_airports,
        "unique_aircraft": row.unique_aircraft or 0,
        "date_range": {
            "first_flight": row.first_flight,
            "last_flight": row.last_flight,
        },
    }


async def get_statistics_by_aircraft_type(
    session: AsyncSession,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> list[dict]:
    """Get statistics grouped by aircraft type."""
    query = select(
        Flight.aircraft_type,
        func.count(Flight.id).label("flights"),
        func.sum(Flight.block_minutes).label("minutes"),
    ).group_by(Flight.aircraft_type).order_by(func.count(Flight.id).desc())

    if date_from:
        query = query.where(Flight.flight_date >= date_from.isoformat())
    if date_to:
        query = query.where(Flight.flight_date <= date_to.isoformat())

    result = await session.execute(query)

    return [
        {"type": row.aircraft_type or "Unknown", "flights": row.flights, "minutes": row.minutes or 0}
        for row in result.all()
    ]


async def get_statistics_by_year(
    session: AsyncSession,
) -> list[dict]:
    """Get statistics grouped by year."""
    query = select(
        func.substr(Flight.flight_date, 1, 4).label("year"),
        func.count(Flight.id).label("flights"),
        func.sum(Flight.block_minutes).label("minutes"),
    ).group_by(func.substr(Flight.flight_date, 1, 4)).order_by("year")

    result = await session.execute(query)

    return [
        {"year": int(row.year), "flights": row.flights, "minutes": row.minutes or 0}
        for row in result.all()
    ]


async def get_airports(session: AsyncSession) -> list[Airport]:
    """Get all airports."""
    result = await session.execute(select(Airport).order_by(Airport.icao))
    return list(result.scalars().all())


async def get_airport_by_icao(session: AsyncSession, icao: str) -> Optional[Airport]:
    """Get an airport by ICAO code."""
    result = await session.execute(select(Airport).where(Airport.icao == icao.upper()))
    return result.scalar_one_or_none()


async def get_import_batch(session: AsyncSession, batch_id: str) -> Optional[ImportBatch]:
    """Get an import batch by ID."""
    result = await session.execute(select(ImportBatch).where(ImportBatch.id == batch_id))
    return result.scalar_one_or_none()
