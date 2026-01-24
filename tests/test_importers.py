"""Tests for flight record importers."""

from pathlib import Path
from tempfile import NamedTemporaryFile

import pytest

from pilotlog.importers.swa_csv import SWACSVImporter
from pilotlog.importers.base import ParsedFlight


class TestSWACSVImporter:
    """Tests for Southwest Airlines CSV importer."""

    @pytest.fixture
    def importer(self):
        """Create an importer instance."""
        return SWACSVImporter()

    def test_parse_time_valid(self, importer):
        """Test parsing valid time strings."""
        assert importer._parse_time("8:58") == 8 * 60 + 58
        assert importer._parse_time("12:10") == 12 * 60 + 10
        assert importer._parse_time("0:30") == 30
        assert importer._parse_time("23:59") == 23 * 60 + 59

    def test_parse_time_midnight_crossing(self, importer):
        """Test parsing times that cross midnight."""
        assert importer._parse_time("24:00") == 24 * 60
        assert importer._parse_time("25:30") == 25 * 60 + 30

    def test_parse_time_invalid(self, importer):
        """Test parsing invalid time strings."""
        assert importer._parse_time("") is None
        assert importer._parse_time("   ") is None
        assert importer._parse_time("invalid") is None

    def test_parse_crew_fo(self, importer):
        """Test parsing FO crew field."""
        position, name, crew_id = importer._parse_crew("FO  ZURCA JULIAN [114706]")
        assert position == "FO"
        assert name == "ZURCA JULIAN"
        assert crew_id == "114706"

    def test_parse_crew_ca(self, importer):
        """Test parsing CA crew field."""
        position, name, crew_id = importer._parse_crew("CA  EVERS ROB *CKP* [58018]")
        assert position == "CA"
        assert name == "EVERS ROB"  # Nickname removed
        assert crew_id == "58018"

    def test_parse_crew_with_nickname(self, importer):
        """Test parsing crew field with nickname."""
        position, name, crew_id = importer._parse_crew(
            "FO  MOBLEY EUGENE *GENE* [131282]"
        )
        assert position == "FO"
        assert name == "MOBLEY EUGENE"
        assert crew_id == "131282"

    def test_parse_crew_deadheading(self, importer):
        """Test parsing deadhead crew field."""
        position, name, crew_id = importer._parse_crew("Deadheading")
        assert position is None
        assert name is None
        assert crew_id is None

    def test_parse_crew_not_available(self, importer):
        """Test parsing NOT AVAILABLE crew field."""
        position, name, crew_id = importer._parse_crew("NOT AVAILABLE")
        assert position is None
        assert name is None
        assert crew_id is None

    def test_normalize_aircraft_type_737_700(self, importer):
        """Test normalizing 737-700 variants."""
        assert importer._normalize_aircraft_type("737-700") == "B737-700"
        assert importer._normalize_aircraft_type("737-73W") == "B737-700"
        assert importer._normalize_aircraft_type("737-73H") == "B737-700"
        assert importer._normalize_aircraft_type("737-7V8") == "B737-700"

    def test_normalize_aircraft_type_737_max(self, importer):
        """Test normalizing 737 MAX variants."""
        assert importer._normalize_aircraft_type("737-7M8") == "B737-MAX7"
        assert importer._normalize_aircraft_type("737-7T8") == "B737-MAX7"

    def test_normalize_aircraft_type_unknown(self, importer):
        """Test normalizing unknown aircraft types."""
        assert importer._normalize_aircraft_type("UNKNOWN") == "UNKNOWN"

    def test_parse_boolean(self, importer):
        """Test parsing boolean fields."""
        assert importer._parse_boolean("1") is True
        assert importer._parse_boolean(" 1 ") is True
        assert importer._parse_boolean("") is False
        assert importer._parse_boolean(" ") is False
        assert importer._parse_boolean("0") is False

    @pytest.mark.asyncio
    async def test_parse_file(self, importer, sample_csv_content):
        """Test parsing a complete CSV file."""
        with NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(sample_csv_content)
            f.flush()
            tmp_path = Path(f.name)

        try:
            flights = await importer.parse_file(tmp_path)

            assert len(flights) == 3

            # First flight
            flight1 = flights[0]
            assert flight1.flight_date == "2025-01-10"
            assert flight1.flight_number == "WN1052"
            assert flight1.origin == "KHOU"
            assert flight1.destination == "KSAN"
            assert flight1.block_minutes == 312
            assert flight1.tail_number == "N8867Q"
            assert flight1.aircraft_type == "B737-MAX7"
            assert flight1.is_deadhead is False
            assert flight1.pic_takeoff is True
            assert flight1.pic_landing is True
            assert flight1.crew_name == "ZURCA JULIAN"
            assert flight1.crew_id == "114706"

            # Deadhead flight
            flight3 = flights[2]
            assert flight3.is_deadhead is True
            assert flight3.block_minutes == 0
        finally:
            tmp_path.unlink()

    def test_validate_flight_valid(self, importer):
        """Test validating a valid flight."""
        flight = ParsedFlight(
            source="swa",
            flight_date="2025-01-10",
            origin="KHOU",
            destination="KSAN",
        )
        is_valid, error = importer.validate_flight(flight)
        assert is_valid is True
        assert error is None

    def test_validate_flight_missing_date(self, importer):
        """Test validating a flight with missing date."""
        flight = ParsedFlight(
            source="swa",
            flight_date="",
            origin="KHOU",
            destination="KSAN",
        )
        is_valid, error = importer.validate_flight(flight)
        assert is_valid is False
        assert "date" in error.lower()

    def test_validate_flight_invalid_icao(self, importer):
        """Test validating a flight with invalid ICAO code."""
        flight = ParsedFlight(
            source="swa",
            flight_date="2025-01-10",
            origin="HOU",  # Should be KHOU
            destination="KSAN",
        )
        is_valid, error = importer.validate_flight(flight)
        assert is_valid is False
        assert "ICAO" in error

    @pytest.mark.asyncio
    async def test_import_file(self, importer, db_session, sample_csv_content):
        """Test importing a CSV file into the database."""
        with NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(sample_csv_content)
            f.flush()
            tmp_path = Path(f.name)

        try:
            result = await importer.import_file(tmp_path, db_session)

            assert result.rows_processed == 3
            assert result.rows_imported == 3
            assert result.rows_skipped == 0
            assert result.rows_duplicate == 0
            assert result.new_block_minutes == 312 + 333 + 0
        finally:
            tmp_path.unlink()

    @pytest.mark.asyncio
    async def test_import_file_duplicate_detection(
        self, importer, db_session, sample_csv_content
    ):
        """Test that re-importing the same file detects duplicates."""
        with NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(sample_csv_content)
            f.flush()
            tmp_path = Path(f.name)

        try:
            # First import
            result1 = await importer.import_file(tmp_path, db_session)
            assert result1.rows_imported == 3

            # Second import - should detect duplicates
            importer2 = SWACSVImporter()
            result2 = await importer2.import_file(tmp_path, db_session)
            assert result2.rows_imported == 0
            assert result2.rows_duplicate == 3
        finally:
            tmp_path.unlink()
