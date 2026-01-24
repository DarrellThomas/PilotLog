-- PilotLog Database Schema (Reference)
-- This file is for documentation. The actual schema is managed by SQLAlchemy.

PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- Main flights table
CREATE TABLE IF NOT EXISTS flights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,  -- 'swa', 'usaf', 'civilian', 'manual'
    flight_date TEXT NOT NULL,  -- ISO 8601 date (YYYY-MM-DD)
    flight_number TEXT,
    origin TEXT NOT NULL,  -- ICAO code (4 chars)
    destination TEXT NOT NULL,  -- ICAO code (4 chars)
    departure_time INTEGER,  -- Minutes since midnight (local)
    arrival_time INTEGER,  -- Minutes since midnight (local)
    block_minutes INTEGER NOT NULL DEFAULT 0,
    tail_number TEXT,
    aircraft_type_raw TEXT,  -- Original aircraft type string
    aircraft_type TEXT,  -- Normalized aircraft type
    is_deadhead INTEGER NOT NULL DEFAULT 0,
    pic_takeoff INTEGER NOT NULL DEFAULT 0,
    pic_landing INTEGER NOT NULL DEFAULT 0,
    crew_position TEXT,  -- 'CA' or 'FO'
    crew_name TEXT,
    crew_id TEXT,
    remarks TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    import_batch_id TEXT REFERENCES import_batches(id)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS ix_flights_flight_date ON flights(flight_date);
CREATE INDEX IF NOT EXISTS ix_flights_origin ON flights(origin);
CREATE INDEX IF NOT EXISTS ix_flights_destination ON flights(destination);
CREATE INDEX IF NOT EXISTS ix_flights_crew_name ON flights(crew_name);
CREATE INDEX IF NOT EXISTS ix_flights_tail_number ON flights(tail_number);
CREATE INDEX IF NOT EXISTS ix_flights_aircraft_type ON flights(aircraft_type);
CREATE INDEX IF NOT EXISTS ix_flights_route ON flights(origin, destination);

-- Flexible attributes for sparse/source-specific data
CREATE TABLE IF NOT EXISTS flight_attributes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    flight_id INTEGER NOT NULL REFERENCES flights(id) ON DELETE CASCADE,
    attribute_name TEXT NOT NULL,
    attribute_value TEXT NOT NULL,
    attribute_unit TEXT
);

CREATE INDEX IF NOT EXISTS ix_flight_attributes_flight_id ON flight_attributes(flight_id);

-- Airport lookup table
CREATE TABLE IF NOT EXISTS airports (
    icao TEXT PRIMARY KEY,  -- ICAO code (4 chars)
    iata TEXT,  -- IATA code (3 chars)
    name TEXT,
    city TEXT,
    country TEXT,  -- ISO 2-letter country code
    latitude REAL,
    longitude REAL,
    timezone TEXT  -- IANA timezone
);

-- Import batch tracking
CREATE TABLE IF NOT EXISTS import_batches (
    id TEXT PRIMARY KEY,  -- UUID
    source TEXT NOT NULL,
    filename TEXT,
    imported_at TEXT NOT NULL,
    rows_processed INTEGER,
    rows_imported INTEGER,
    rows_skipped INTEGER,
    rows_duplicate INTEGER
);

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

-- Initial schema version
INSERT OR IGNORE INTO schema_version (version, applied_at) VALUES (1, CURRENT_TIMESTAMP);
