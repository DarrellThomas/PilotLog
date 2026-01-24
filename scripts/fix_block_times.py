#!/usr/bin/env python3
"""Fix block_minutes values that were incorrectly parsed as raw minutes instead of HMM format."""

import sqlite3
from pathlib import Path

DB_PATH = Path.home() / ".pilotlog" / "logbook.db"


def fix_block_times(conn):
    """Recalculate all block_minutes from the incorrectly stored values."""
    cursor = conn.cursor()

    # Get all flights with their current block_minutes
    cursor.execute("""
        SELECT id, block_minutes
        FROM flights
        WHERE block_minutes > 0
    """)
    flights = cursor.fetchall()

    print(f"Found {len(flights)} flights to check")

    fixed_count = 0
    for flight_id, old_block in flights:
        # The old value was stored as raw integer (e.g., 414)
        # It should have been parsed as HMM (4:14 = 254 minutes)
        hours = old_block // 100
        mins = old_block % 100

        # Sanity check: minutes should be 0-59
        if mins >= 60:
            # This might be an edge case or already correct value
            print(f"  Warning: Flight {flight_id} has block={old_block}, mins={mins} >= 60, skipping")
            continue

        new_block = hours * 60 + mins

        if new_block != old_block:
            cursor.execute(
                "UPDATE flights SET block_minutes = ? WHERE id = ?",
                (new_block, flight_id)
            )
            fixed_count += 1

    conn.commit()
    return fixed_count


def verify_totals(conn):
    """Show the corrected totals."""
    cursor = conn.cursor()

    # 365-day rolling total
    cursor.execute("""
        SELECT COUNT(*), SUM(block_minutes)
        FROM flights
        WHERE flight_date > date('now', '-365 days')
        AND flight_date <= date('now')
        AND is_deadhead = 0
    """)
    row = cursor.fetchone()
    mins = row[1] or 0
    print(f"\n365-day rolling total: {row[0]} flights, {mins//60}:{mins%60:02d}")

    # Calendar year 2025
    cursor.execute("""
        SELECT COUNT(*), SUM(block_minutes)
        FROM flights
        WHERE flight_date >= '2025-01-01'
        AND flight_date <= '2025-12-31'
        AND is_deadhead = 0
    """)
    row = cursor.fetchone()
    mins = row[1] or 0
    print(f"2025 calendar year: {row[0]} flights, {mins//60}:{mins%60:02d}")

    # 2026 so far
    cursor.execute("""
        SELECT COUNT(*), SUM(block_minutes)
        FROM flights
        WHERE flight_date >= '2026-01-01'
        AND is_deadhead = 0
    """)
    row = cursor.fetchone()
    mins = row[1] or 0
    print(f"2026 YTD: {row[0]} flights, {mins//60}:{mins%60:02d}")


def main():
    if not DB_PATH.exists():
        print(f"Database not found at {DB_PATH}")
        return 1

    conn = sqlite3.connect(DB_PATH)

    try:
        print("Fixing block_minutes values...")
        fixed = fix_block_times(conn)
        print(f"Fixed {fixed} flights")

        verify_totals(conn)

    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    exit(main())
