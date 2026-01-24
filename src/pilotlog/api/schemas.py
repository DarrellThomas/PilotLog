"""Pydantic schemas for API request/response models."""

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


# Flight schemas
class FlightResponse(BaseModel):
    """Response model for a single flight."""

    id: int
    flight_date: str
    flight_number: Optional[str] = None
    origin: str
    destination: str
    block_minutes: int
    block_formatted: str
    tail_number: Optional[str] = None
    aircraft_type: Optional[str] = None
    crew_name: Optional[str] = None
    crew_position: Optional[str] = None
    is_deadhead: bool
    pic_takeoff: bool
    pic_landing: bool

    model_config = {"from_attributes": True}


class FlightsListResponse(BaseModel):
    """Response model for list of flights."""

    flights: list[FlightResponse]
    total: int
    limit: int
    offset: int


# Statistics schemas
class DateRange(BaseModel):
    """Date range for statistics."""

    first_flight: Optional[str] = None
    last_flight: Optional[str] = None


class AircraftTypeStats(BaseModel):
    """Statistics for a single aircraft type."""

    type: str
    flights: int
    minutes: int


class YearStats(BaseModel):
    """Statistics for a single year."""

    year: int
    flights: int
    minutes: int


class StatsResponse(BaseModel):
    """Response model for career statistics."""

    total_flights: int
    total_block_minutes: int
    total_block_formatted: str
    unique_airports: int
    unique_aircraft: int
    date_range: DateRange
    by_aircraft_type: list[AircraftTypeStats]
    by_year: list[YearStats]


# Rolling totals schemas
class RollingWindowStats(BaseModel):
    """Statistics for a single rolling window."""

    flights: int
    minutes: int
    formatted: str


class RollingResponse(BaseModel):
    """Response model for rolling totals."""

    as_of: str
    windows: dict[str, RollingWindowStats]


# Route map schemas
class RouteStats(BaseModel):
    """Statistics for a single route."""

    origin: str
    destination: str
    count: int
    total_minutes: int
    first_flown: Optional[str] = None
    last_flown: Optional[str] = None


class AirportStats(BaseModel):
    """Statistics for a single airport."""

    icao: str
    name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    departures: int
    arrivals: int


class RoutesResponse(BaseModel):
    """Response model for route data."""

    routes: list[RouteStats]
    airports: list[AirportStats]


# Import schemas
class ImportError(BaseModel):
    """An error from import processing."""

    row: int
    message: str


class ImportSummary(BaseModel):
    """Summary of imported data."""

    new_block_minutes: int
    new_block_formatted: str
    date_range: str


class ImportResponse(BaseModel):
    """Response model for import operation."""

    batch_id: str
    filename: str
    rows_processed: int
    rows_imported: int
    rows_skipped: int
    rows_duplicate: int
    errors: list[ImportError]
    summary: ImportSummary


# Airport schemas
class AirportResponse(BaseModel):
    """Response model for airport lookup."""

    icao: str
    iata: Optional[str] = None
    name: Optional[str] = None
    city: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    model_config = {"from_attributes": True}


class AirportsListResponse(BaseModel):
    """Response model for list of airports."""

    airports: list[AirportResponse]
