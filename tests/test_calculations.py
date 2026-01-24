"""Tests for calculation functions."""

from datetime import date

import pytest

from pilotlog.calculations.rolling import calculate_burn_rate, format_minutes
from pilotlog.calculations.aggregations import (
    calculate_route_intensity,
    calculate_most_frequent_routes,
)


class TestRollingCalculations:
    """Tests for rolling window calculations."""

    def test_format_minutes_simple(self):
        """Test formatting minutes to H:MM."""
        assert format_minutes(0) == "0:00"
        assert format_minutes(30) == "0:30"
        assert format_minutes(60) == "1:00"
        assert format_minutes(90) == "1:30"

    def test_format_minutes_large(self):
        """Test formatting large minute values."""
        assert format_minutes(600) == "10:00"
        assert format_minutes(645) == "10:45"
        assert format_minutes(8385) == "139:45"

    def test_calculate_burn_rate_normal(self):
        """Test burn rate calculation with normal values."""
        result = calculate_burn_rate(
            current_minutes=3000,  # 50 hours
            window_days=30,
            limit_minutes=6000,  # 100 hours
        )

        assert result["daily_rate"] == pytest.approx(1.67, rel=0.1)  # ~1.67 hours/day
        assert result["remaining_minutes"] == 3000
        assert result["days_to_limit"] is not None
        assert result["projected_limit_date"] is not None

    def test_calculate_burn_rate_at_limit(self):
        """Test burn rate calculation when at limit."""
        result = calculate_burn_rate(
            current_minutes=6000,
            window_days=30,
            limit_minutes=6000,
        )

        assert result["remaining_minutes"] == 0
        assert result["days_to_limit"] == 0

    def test_calculate_burn_rate_zero_days(self):
        """Test burn rate with zero days."""
        result = calculate_burn_rate(
            current_minutes=1000,
            window_days=0,
            limit_minutes=6000,
        )

        assert result["daily_rate"] == 0
        assert result["days_to_limit"] is None


class TestAggregationCalculations:
    """Tests for aggregation calculations."""

    def test_calculate_route_intensity_normal(self):
        """Test route intensity calculation."""
        intensity = calculate_route_intensity(count=50, max_count=100)
        assert 0 < intensity < 1

    def test_calculate_route_intensity_max(self):
        """Test route intensity at maximum."""
        intensity = calculate_route_intensity(count=100, max_count=100)
        assert intensity == pytest.approx(1.0, rel=0.01)

    def test_calculate_route_intensity_min(self):
        """Test route intensity at minimum."""
        intensity = calculate_route_intensity(count=1, max_count=100)
        assert intensity > 0
        assert intensity < 0.5

    def test_calculate_route_intensity_zero(self):
        """Test route intensity with zero values."""
        assert calculate_route_intensity(count=0, max_count=100) == 0
        assert calculate_route_intensity(count=50, max_count=0) == 0

    def test_calculate_most_frequent_routes(self):
        """Test getting most frequent routes."""
        routes = [
            {"origin": "KHOU", "destination": "KDEN", "count": 100},
            {"origin": "KHOU", "destination": "KSAN", "count": 50},
            {"origin": "KHOU", "destination": "KLAX", "count": 200},
            {"origin": "KHOU", "destination": "KMSY", "count": 75},
        ]

        top_routes = calculate_most_frequent_routes(routes, top_n=2)

        assert len(top_routes) == 2
        assert top_routes[0]["destination"] == "KLAX"
        assert top_routes[1]["destination"] == "KDEN"

    def test_calculate_most_frequent_routes_empty(self):
        """Test with empty routes list."""
        assert calculate_most_frequent_routes([], top_n=10) == []

    def test_calculate_most_frequent_routes_less_than_n(self):
        """Test when fewer routes than requested."""
        routes = [
            {"origin": "KHOU", "destination": "KDEN", "count": 100},
        ]

        top_routes = calculate_most_frequent_routes(routes, top_n=10)
        assert len(top_routes) == 1
