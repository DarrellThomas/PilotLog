"""Southwest Airlines CSV importer."""

import csv
import logging
import re
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from pilotlog.database.models import Flight, ImportBatch
from pilotlog.database.queries import check_duplicate_flight
from pilotlog.importers.base import BaseImporter, ImportResult, ParsedFlight

logger = logging.getLogger(__name__)

# Aircraft type normalization mapping
AIRCRAFT_TYPE_MAP = {
    # 737-700 variants
    "737-700": "B737-700",
    "737-73W": "B737-700",
    "737-73H": "B737-700",
    "737-73R": "B737-700",
    "737-7H4": "B737-700",
    "737-7BD": "B737-700",
    "737-7CT": "B737-700",
    "737-7Q8": "B737-700",
    "737-7L9": "B737-700",
    "737-7V8": "B737-700",
    "737-7A8": "B737-700",
    "737-7U8": "B737-700",
    "737-7X8": "B737-700",
    "737-7R8": "B737-700",
    # 737-800 variants
    "737-800": "B737-800",
    "737-8H4": "B737-800",
    "737-8BK": "B737-800",
    "737-8FH": "B737-800",
    "737-8KN": "B737-800",
    "737-8LY": "B737-800",
    "737-83N": "B737-800",
    "737-838": "B737-800",
    "737-8FE": "B737-800",
    "737-8GP": "B737-800",
    "737-8AS": "B737-800",
    "737-8CT": "B737-800",
    "737-8JP": "B737-800",
    "737-8DC": "B737-800",
    "737-8F2": "B737-800",
    "737-8HX": "B737-800",
    "737-8HG": "B737-800",
    "737-8SH": "B737-800",
    "737-8Q8": "B737-800",
    "737-8FT": "B737-800",
    "737-8AL": "B737-800",
    "737-8EH": "B737-800",
    "737-8CX": "B737-800",
    "737-8K5": "B737-800",
    "737-8EC": "B737-800",
    "737-8RD": "B737-800",
    "737-8D6": "B737-800",
    "737-8FN": "B737-800",
    "737-8SY": "B737-800",
    "737-8HK": "B737-800",
    "737-738": "B737-800",
    # 737 MAX 7 variants
    "737-7M8": "B737-MAX7",
    "737-7T8": "B737-MAX7",
    # 737 MAX 8 variants
    "737-8MX": "B737-MAX8",
    "737-8U8": "B737-MAX8",
    # Legacy models
    "737-300": "B737-300",
    "737-3H4": "B737-300",
    "737-3A4": "B737-300",
    "737-3G7": "B737-300",
    "737-3Q8": "B737-300",
    "737-3K2": "B737-300",
    "737-3T5": "B737-300",
    "737-3L9": "B737-300",
    "737-3Y0": "B737-300",
    "737-3B7": "B737-300",
    "737-317": "B737-300",
    "737-500": "B737-500",
    "737-5H4": "B737-500",
    "737-5Y0": "B737-500",
}

# Regex pattern for parsing crew field
# Examples: "FO  ZURCA JULIAN *JACKSON* [114706]", "CA  EVERS ROB *CKP* [58018]"
CREW_PATTERN = re.compile(
    r"^(FO|CA)\s+(.+?)\s*\[(\d+)\]$"
)


class SWACSVImporter(BaseImporter):
    """Importer for Southwest Airlines CSV flight records."""

    source_name = "swa"

    def __init__(self):
        super().__init__()
        self.header_lines = 7  # Skip first 7 lines (metadata + header row)

    def _parse_time(self, time_str: str) -> Optional[int]:
        """Parse HH:MM time string to minutes since midnight."""
        if not time_str or not time_str.strip():
            return None
        time_str = time_str.strip()
        try:
            # Handle times that cross midnight (e.g., 24:00, 25:30)
            parts = time_str.split(":")
            if len(parts) == 2:
                hours = int(parts[0])
                minutes = int(parts[1])
                return hours * 60 + minutes
        except (ValueError, IndexError):
            logger.warning(f"Could not parse time: {time_str}")
        return None

    def _parse_crew(self, crew_str: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
        """Parse crew field into (position, name, id)."""
        if not crew_str or not crew_str.strip():
            return None, None, None

        crew_str = crew_str.strip()

        # Handle special cases
        if crew_str in ("Deadheading", "NOT AVAILABLE"):
            return None, None, None

        match = CREW_PATTERN.match(crew_str)
        if match:
            position = match.group(1)  # FO or CA
            name = match.group(2).strip()
            # Clean up name - remove asterisk nicknames for storage
            name = re.sub(r"\s*\*[^*]+\*\s*", " ", name).strip()
            name = re.sub(r"\s+", " ", name)  # Normalize whitespace
            crew_id = match.group(3)
            return position, name, crew_id

        logger.warning(f"Could not parse crew field: {crew_str}")
        return None, crew_str, None

    def _normalize_aircraft_type(self, raw_type: str) -> Optional[str]:
        """Normalize aircraft type to standard format."""
        if not raw_type or not raw_type.strip():
            return None
        raw_type = raw_type.strip()
        return AIRCRAFT_TYPE_MAP.get(raw_type, raw_type)

    def _parse_boolean(self, value: str) -> bool:
        """Parse a boolean field (1 = True, else False)."""
        return value.strip() == "1" if value else False

    async def parse_file(self, file_path: Path) -> list[ParsedFlight]:
        """Parse a SWA CSV file and return parsed flights."""
        flights = []

        # Read file content, handling BOM
        content = file_path.read_text(encoding="utf-8-sig")
        lines = content.splitlines()

        # Skip header lines and parse data rows
        if len(lines) <= self.header_lines:
            logger.warning(f"File {file_path} has no data rows")
            return flights

        # Get the header row to understand column positions
        header_line = lines[self.header_lines - 1]
        reader = csv.DictReader(
            lines[self.header_lines:],
            fieldnames=[
                "DATE", "Flight", "dhd", "From", "Depart", "To", "Arrive",
                "Block", "Tail_Number", "A_C_Type", "TakeOff", "Landing", "CoPilot"
            ],
        )

        for row_num, row in enumerate(reader, start=self.header_lines + 1):
            try:
                # Skip empty rows
                if not row.get("DATE") or not row["DATE"].strip():
                    continue

                flight = self._parse_row(row)
                if flight:
                    flights.append(flight)
            except Exception as e:
                logger.error(f"Error parsing row {row_num}: {e}")

        return flights

    def _parse_row(self, row: dict) -> Optional[ParsedFlight]:
        """Parse a single CSV row into a ParsedFlight."""
        # Parse date
        date_str = row.get("DATE", "").strip()
        if not date_str:
            return None

        # Validate date format (YYYY-MM-DD expected)
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            logger.error(f"Invalid date format: {date_str}")
            return None

        # Parse required fields
        origin = row.get("From", "").strip().upper()
        destination = row.get("To", "").strip().upper()

        if not origin or not destination:
            logger.error(f"Missing origin or destination for flight on {date_str}")
            return None

        # Parse other fields
        flight_number = row.get("Flight", "").strip()
        is_deadhead = row.get("dhd", "").strip().upper() == "DH"

        # Block time - format is HMM or HHMM (e.g., "414" = 4:14 = 254 minutes)
        block_str = row.get("Block", "0").strip()
        try:
            if block_str:
                block_int = int(block_str)
                # Parse as HHMM format: last 2 digits are minutes, rest is hours
                block_hours = block_int // 100
                block_mins = block_int % 100
                block_minutes = block_hours * 60 + block_mins
            else:
                block_minutes = 0
        except ValueError:
            block_minutes = 0

        # Parse times
        departure_time = self._parse_time(row.get("Depart", ""))
        arrival_time = self._parse_time(row.get("Arrive", ""))

        # Parse aircraft info
        tail_number = row.get("Tail_Number", "").strip().upper() or None
        aircraft_type_raw = row.get("A_C_Type", "").strip() or None
        aircraft_type = self._normalize_aircraft_type(aircraft_type_raw) if aircraft_type_raw else None

        # Parse PIC takeoff/landing
        pic_takeoff = self._parse_boolean(row.get("TakeOff", ""))
        pic_landing = self._parse_boolean(row.get("Landing", ""))

        # Parse crew
        crew_position, crew_name, crew_id = self._parse_crew(row.get("CoPilot", ""))

        return ParsedFlight(
            source=self.source_name,
            flight_date=date_str,
            flight_number=flight_number,
            origin=origin,
            destination=destination,
            departure_time=departure_time,
            arrival_time=arrival_time,
            block_minutes=block_minutes,
            tail_number=tail_number,
            aircraft_type_raw=aircraft_type_raw,
            aircraft_type=aircraft_type,
            is_deadhead=is_deadhead,
            pic_takeoff=pic_takeoff,
            pic_landing=pic_landing,
            crew_position=crew_position,
            crew_name=crew_name,
            crew_id=crew_id,
        )

    def validate_flight(self, flight: ParsedFlight) -> tuple[bool, Optional[str]]:
        """Validate a parsed flight."""
        if not flight.flight_date:
            return False, "Missing flight date"
        if not flight.origin:
            return False, "Missing origin airport"
        if not flight.destination:
            return False, "Missing destination airport"
        if len(flight.origin) != 4:
            return False, f"Invalid origin ICAO code: {flight.origin}"
        if len(flight.destination) != 4:
            return False, f"Invalid destination ICAO code: {flight.destination}"

        return True, None

    async def import_file(
        self, file_path: Path, session: AsyncSession
    ) -> ImportResult:
        """Import a CSV file into the database."""
        result = ImportResult(
            batch_id=self.batch_id,
            filename=file_path.name,
            source=self.source_name,
        )

        # Parse the file
        parsed_flights = await self.parse_file(file_path)
        result.rows_processed = len(parsed_flights)

        if not parsed_flights:
            return result

        # Create import batch record FIRST (before flights that reference it)
        import_batch = ImportBatch(
            id=self.batch_id,
            source=self.source_name,
            filename=file_path.name,
            imported_at=self.imported_at,
            rows_processed=result.rows_processed,
            rows_imported=0,
            rows_skipped=0,
            rows_duplicate=0,
        )
        session.add(import_batch)
        await session.flush()  # Ensure batch exists before adding flights

        # Track date range
        dates = []

        # Process each flight
        for idx, parsed in enumerate(parsed_flights):
            # Validate
            is_valid, error_msg = self.validate_flight(parsed)
            if not is_valid:
                result.rows_skipped += 1
                result.errors.append({"row": idx + self.header_lines + 1, "message": error_msg})
                continue

            # Check for duplicates
            is_duplicate = await check_duplicate_flight(
                session,
                parsed.flight_date,
                parsed.flight_number,
                parsed.origin,
                parsed.destination,
            )
            if is_duplicate:
                result.rows_duplicate += 1
                continue

            # Create database record
            flight = Flight(
                source=parsed.source,
                flight_date=parsed.flight_date,
                flight_number=parsed.flight_number,
                origin=parsed.origin,
                destination=parsed.destination,
                departure_time=parsed.departure_time,
                arrival_time=parsed.arrival_time,
                block_minutes=parsed.block_minutes,
                tail_number=parsed.tail_number,
                aircraft_type_raw=parsed.aircraft_type_raw,
                aircraft_type=parsed.aircraft_type,
                is_deadhead=parsed.is_deadhead,
                pic_takeoff=parsed.pic_takeoff,
                pic_landing=parsed.pic_landing,
                crew_position=parsed.crew_position,
                crew_name=parsed.crew_name,
                crew_id=parsed.crew_id,
                import_batch_id=self.batch_id,
            )
            session.add(flight)
            result.rows_imported += 1
            result.new_block_minutes += parsed.block_minutes
            dates.append(parsed.flight_date)

        # Set date range
        if dates:
            result.date_range_start = min(dates)
            result.date_range_end = max(dates)

        # Update import batch with final counts
        import_batch.rows_imported = result.rows_imported
        import_batch.rows_skipped = result.rows_skipped
        import_batch.rows_duplicate = result.rows_duplicate

        await session.commit()

        logger.info(
            f"Imported {result.rows_imported} flights from {file_path.name} "
            f"({result.rows_skipped} skipped, {result.rows_duplicate} duplicates)"
        )

        return result
