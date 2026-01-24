"""Rolling window calculations for flight time totals."""

from datetime import date, timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from pilotlog.database.queries import get_rolling_totals as db_get_rolling_totals


async def calculate_rolling_totals(
    session: AsyncSession,
    as_of_date: Optional[date] = None,
    windows: Optional[list[int]] = None,
) -> dict[int, dict]:
    """
    Calculate flight time totals for rolling windows.

    Args:
        session: Database session
        as_of_date: Calculate totals as of this date (default: today)
        windows: List of window sizes in days (default: [7, 30, 60, 90, 365])

    Returns:
        Dictionary mapping window size to stats:
        {
            7: {"flights": 12, "minutes": 1850, "formatted": "30:50"},
            30: {"flights": 45, "minutes": 7200, "formatted": "120:00"},
            ...
        }
    """
    if as_of_date is None:
        as_of_date = date.today()

    if windows is None:
        windows = [7, 30, 60, 90, 365]

    return await db_get_rolling_totals(session, as_of_date, windows)


def calculate_burn_rate(
    current_minutes: int,
    window_days: int,
    limit_minutes: int,
) -> dict:
    """
    Calculate burn rate and projected limit date.

    Args:
        current_minutes: Minutes flown in the window
        window_days: Number of days in the window
        limit_minutes: Regulatory or contractual limit

    Returns:
        Dictionary with burn rate info:
        {
            "daily_rate": 4.5,  # hours per day
            "remaining_minutes": 1200,
            "days_to_limit": 45,
            "projected_limit_date": "2025-03-15"
        }
    """
    if window_days <= 0:
        return {
            "daily_rate": 0,
            "remaining_minutes": limit_minutes,
            "days_to_limit": None,
            "projected_limit_date": None,
        }

    daily_rate_minutes = current_minutes / window_days
    remaining_minutes = max(0, limit_minutes - current_minutes)

    if daily_rate_minutes > 0:
        days_to_limit = int(remaining_minutes / daily_rate_minutes)
        projected_date = date.today() + timedelta(days=days_to_limit)
        projected_limit_date = projected_date.isoformat()
    else:
        days_to_limit = None
        projected_limit_date = None

    return {
        "daily_rate": round(daily_rate_minutes / 60, 2),  # Convert to hours
        "remaining_minutes": remaining_minutes,
        "days_to_limit": days_to_limit,
        "projected_limit_date": projected_limit_date,
    }


def format_minutes(minutes: int) -> str:
    """Format minutes as H:MM."""
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours}:{mins:02d}"
