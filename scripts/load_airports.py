#!/usr/bin/env python3
"""Load airport data from OurAirports CSV into the database."""

import csv
import io
import sqlite3
import urllib.request
from pathlib import Path

AIRPORTS_URL = "https://davidmegginson.github.io/ourairports-data/airports.csv"
DB_PATH = Path.home() / ".pilotlog" / "logbook.db"


def download_airports_csv():
    """Download airports.csv from OurAirports."""
    print("Downloading airport data from OurAirports...")
    with urllib.request.urlopen(AIRPORTS_URL) as response:
        return response.read().decode('utf-8')


def get_needed_airports(conn):
    """Get list of airports used in flights."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT origin FROM flights
        UNION
        SELECT DISTINCT destination FROM flights
    """)
    return {row[0] for row in cursor.fetchall()}


def parse_and_insert_airports(conn, csv_data, needed_icao):
    """Parse CSV and insert matching airports."""
    reader = csv.DictReader(io.StringIO(csv_data))

    cursor = conn.cursor()
    inserted = 0

    for row in reader:
        icao = row.get('ident', '').upper()

        # Skip if not needed or not a valid ICAO code
        if icao not in needed_icao:
            continue

        # Skip closed airports
        if row.get('type') == 'closed':
            continue

        try:
            lat = float(row['latitude_deg']) if row.get('latitude_deg') else None
            lon = float(row['longitude_deg']) if row.get('longitude_deg') else None
        except (ValueError, TypeError):
            lat, lon = None, None

        if lat is None or lon is None:
            continue

        # Extract IATA code
        iata = row.get('iata_code', '') or None

        cursor.execute("""
            INSERT OR REPLACE INTO airports (icao, iata, name, city, country, latitude, longitude, timezone)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            icao,
            iata,
            row.get('name'),
            row.get('municipality'),
            row.get('iso_country'),
            lat,
            lon,
            row.get('local_region'),  # Not exactly timezone but close
        ))
        inserted += 1

    conn.commit()
    return inserted


def main():
    if not DB_PATH.exists():
        print(f"Database not found at {DB_PATH}")
        return 1

    conn = sqlite3.connect(DB_PATH)

    try:
        # Get airports we need
        needed = get_needed_airports(conn)
        print(f"Found {len(needed)} unique airports in flight data")

        # Download and parse
        csv_data = download_airports_csv()
        inserted = parse_and_insert_airports(conn, csv_data, needed)

        print(f"Inserted {inserted} airports with coordinates")

        # Show any missing
        cursor = conn.cursor()
        cursor.execute("SELECT icao FROM airports")
        loaded = {row[0] for row in cursor.fetchall()}
        missing = needed - loaded

        if missing:
            print(f"\nMissing airports ({len(missing)}): {sorted(missing)}")
        else:
            print("\nAll airports loaded successfully!")

    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    exit(main())
