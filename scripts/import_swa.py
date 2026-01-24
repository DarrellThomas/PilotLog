#!/usr/bin/env python3
"""CLI tool to import SWA CSV files."""

import asyncio
import sys
from pathlib import Path

# Add src to path for development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pilotlog.config import settings
from pilotlog.database.connection import init_db, get_session
from pilotlog.importers.swa_csv import SWACSVImporter


async def main():
    if len(sys.argv) < 2:
        print("Usage: import_swa.py <csv_file> [csv_file2] ...")
        print("\nImports Southwest Airlines CSV flight records into PilotLog.")
        sys.exit(1)

    # Initialize database
    settings.ensure_directories()
    await init_db()

    for csv_path in sys.argv[1:]:
        path = Path(csv_path)
        if not path.exists():
            print(f"Error: File not found: {path}")
            continue

        if not path.suffix.lower() == ".csv":
            print(f"Warning: Skipping non-CSV file: {path}")
            continue

        print(f"\nImporting {path.name}...")

        async with get_session() as session:
            importer = SWACSVImporter()
            result = await importer.import_file(path, session)

        print(f"  Rows processed: {result.rows_processed}")
        print(f"  Flights imported: {result.rows_imported}")
        print(f"  Duplicates skipped: {result.rows_duplicate}")
        print(f"  Rows skipped: {result.rows_skipped}")

        if result.rows_imported > 0:
            print(f"  New block time: {result.new_block_formatted}")
            if result.date_range_start and result.date_range_end:
                print(f"  Date range: {result.date_range_start} to {result.date_range_end}")

        if result.errors:
            print(f"  Errors:")
            for err in result.errors[:5]:
                print(f"    Row {err['row']}: {err['message']}")
            if len(result.errors) > 5:
                print(f"    ...and {len(result.errors) - 5} more errors")

    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
