"""SQLAlchemy models for PilotLog database."""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


class Flight(Base):
    """A single flight record."""

    __tablename__ = "flights"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    flight_date: Mapped[str] = mapped_column(String(10), nullable=False)  # ISO 8601
    flight_number: Mapped[Optional[str]] = mapped_column(String(20))
    origin: Mapped[str] = mapped_column(String(4), nullable=False)
    destination: Mapped[str] = mapped_column(String(4), nullable=False)
    departure_time: Mapped[Optional[int]] = mapped_column(Integer)  # Minutes since midnight
    arrival_time: Mapped[Optional[int]] = mapped_column(Integer)  # Minutes since midnight
    block_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tail_number: Mapped[Optional[str]] = mapped_column(String(10))
    aircraft_type_raw: Mapped[Optional[str]] = mapped_column(String(20))
    aircraft_type: Mapped[Optional[str]] = mapped_column(String(20))
    is_deadhead: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    pic_takeoff: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    pic_landing: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    crew_position: Mapped[Optional[str]] = mapped_column(String(5))
    crew_name: Mapped[Optional[str]] = mapped_column(String(100))
    crew_id: Mapped[Optional[str]] = mapped_column(String(20))
    remarks: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )
    import_batch_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("import_batches.id")
    )

    # Relationships
    attributes: Mapped[list["FlightAttribute"]] = relationship(
        back_populates="flight", cascade="all, delete-orphan"
    )
    import_batch: Mapped[Optional["ImportBatch"]] = relationship(back_populates="flights")

    __table_args__ = (
        Index("ix_flights_flight_date", "flight_date"),
        Index("ix_flights_origin", "origin"),
        Index("ix_flights_destination", "destination"),
        Index("ix_flights_crew_name", "crew_name"),
        Index("ix_flights_tail_number", "tail_number"),
        Index("ix_flights_aircraft_type", "aircraft_type"),
        Index("ix_flights_route", "origin", "destination"),
    )


class FlightAttribute(Base):
    """Flexible key-value attributes for sparse/source-specific flight data."""

    __tablename__ = "flight_attributes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    flight_id: Mapped[int] = mapped_column(Integer, ForeignKey("flights.id"), nullable=False)
    attribute_name: Mapped[str] = mapped_column(String(50), nullable=False)
    attribute_value: Mapped[str] = mapped_column(Text, nullable=False)
    attribute_unit: Mapped[Optional[str]] = mapped_column(String(20))

    # Relationships
    flight: Mapped["Flight"] = relationship(back_populates="attributes")

    __table_args__ = (Index("ix_flight_attributes_flight_id", "flight_id"),)


class Airport(Base):
    """Airport lookup data with coordinates."""

    __tablename__ = "airports"

    icao: Mapped[str] = mapped_column(String(4), primary_key=True)
    iata: Mapped[Optional[str]] = mapped_column(String(3))
    name: Mapped[Optional[str]] = mapped_column(String(100))
    city: Mapped[Optional[str]] = mapped_column(String(100))
    country: Mapped[Optional[str]] = mapped_column(String(2))
    latitude: Mapped[Optional[float]] = mapped_column(Float)
    longitude: Mapped[Optional[float]] = mapped_column(Float)
    timezone: Mapped[Optional[str]] = mapped_column(String(50))


class ImportBatch(Base):
    """Track import operations for audit and rollback."""

    __tablename__ = "import_batches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # UUID
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    filename: Mapped[Optional[str]] = mapped_column(String(255))
    imported_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    rows_processed: Mapped[Optional[int]] = mapped_column(Integer)
    rows_imported: Mapped[Optional[int]] = mapped_column(Integer)
    rows_skipped: Mapped[Optional[int]] = mapped_column(Integer)
    rows_duplicate: Mapped[Optional[int]] = mapped_column(Integer)

    # Relationships
    flights: Mapped[list["Flight"]] = relationship(back_populates="import_batch")


class SchemaVersion(Base):
    """Track database schema version for migrations."""

    __tablename__ = "schema_version"

    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    applied_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
