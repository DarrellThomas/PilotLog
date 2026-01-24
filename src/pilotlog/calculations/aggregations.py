"""Aggregation calculations for flight statistics."""

from datetime import date
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from pilotlog.database.queries import (
    get_career_statistics as db_get_career_statistics,
    get_route_statistics as db_get_route_statistics,
    get_statistics_by_aircraft_type,
    get_statistics_by_year,
)


async def calculate_career_statistics(
    session: AsyncSession,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> dict:
    """
    Calculate overall career statistics.

    Args:
        session: Database session
        date_from: Filter start date
        date_to: Filter end date

    Returns:
        Dictionary with career stats:
        {
            "total_flights": 4388,
            "total_block_minutes": 503102,
            "total_block_formatted": "8385:02",
            "unique_airports": 125,
            "unique_aircraft": 874,
            "date_range": {"first_flight": "2014-02-19", "last_flight": "2025-12-31"},
            "by_aircraft_type": [...],
            "by_year": [...]
        }
    """
    stats = await db_get_career_statistics(session, date_from, date_to)
    by_aircraft = await get_statistics_by_aircraft_type(session, date_from, date_to)
    by_year = await get_statistics_by_year(session)

    stats["by_aircraft_type"] = by_aircraft
    stats["by_year"] = by_year

    return stats


async def calculate_route_statistics(
    session: AsyncSession,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> list[dict]:
    """
    Calculate route statistics for map visualization.

    Args:
        session: Database session
        date_from: Filter start date
        date_to: Filter end date

    Returns:
        List of route statistics:
        [
            {
                "origin": "KHOU",
                "destination": "KDEN",
                "count": 367,
                "total_minutes": 42000,
                "first_flown": "2014-03-15",
                "last_flown": "2025-01-30"
            },
            ...
        ]
    """
    return await db_get_route_statistics(session, date_from, date_to)


def calculate_route_intensity(count: int, max_count: int) -> float:
    """
    Calculate route intensity for visualization (0.0 to 1.0).

    Uses logarithmic scaling for better visual distribution.

    Args:
        count: Number of times this route was flown
        max_count: Maximum count across all routes

    Returns:
        Intensity value between 0.0 and 1.0
    """
    if max_count <= 0 or count <= 0:
        return 0.0

    import math

    # Log scale for better distribution
    log_count = math.log10(count + 1)
    log_max = math.log10(max_count + 1)

    return log_count / log_max if log_max > 0 else 0.0


def calculate_most_frequent_routes(routes: list[dict], top_n: int = 10) -> list[dict]:
    """
    Get the most frequently flown routes.

    Args:
        routes: List of route statistics
        top_n: Number of top routes to return

    Returns:
        Top N routes sorted by count
    """
    sorted_routes = sorted(routes, key=lambda r: r["count"], reverse=True)
    return sorted_routes[:top_n]


def calculate_most_frequent_airports(airports: list[dict], top_n: int = 10) -> list[dict]:
    """
    Get the most frequently visited airports.

    Args:
        airports: List of airport statistics
        top_n: Number of top airports to return

    Returns:
        Top N airports sorted by total visits (departures + arrivals)
    """
    for airport in airports:
        airport["total_visits"] = airport.get("departures", 0) + airport.get("arrivals", 0)

    sorted_airports = sorted(airports, key=lambda a: a["total_visits"], reverse=True)
    return sorted_airports[:top_n]
