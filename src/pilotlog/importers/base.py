"""Base importer class for flight record imports."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional
import uuid


@dataclass
class ImportResult:
    """Result of an import operation."""

    batch_id: str
    filename: str
    source: str
    rows_processed: int = 0
    rows_imported: int = 0
    rows_skipped: int = 0
    rows_duplicate: int = 0
    errors: list[dict] = field(default_factory=list)
    new_block_minutes: int = 0
    date_range_start: Optional[str] = None
    date_range_end: Optional[str] = None

    @property
    def new_block_formatted(self) -> str:
        """Format block time as HH:MM."""
        hours = self.new_block_minutes // 60
        minutes = self.new_block_minutes % 60
        return f"{hours}:{minutes:02d}"


@dataclass
class ParsedFlight:
    """A parsed flight record ready for database insertion."""

    source: str
    flight_date: str  # ISO 8601
    flight_number: Optional[str] = None
    origin: str = ""
    destination: str = ""
    departure_time: Optional[int] = None  # Minutes since midnight
    arrival_time: Optional[int] = None  # Minutes since midnight
    block_minutes: int = 0
    tail_number: Optional[str] = None
    aircraft_type_raw: Optional[str] = None
    aircraft_type: Optional[str] = None
    is_deadhead: bool = False
    pic_takeoff: bool = False
    pic_landing: bool = False
    crew_position: Optional[str] = None
    crew_name: Optional[str] = None
    crew_id: Optional[str] = None
    remarks: Optional[str] = None


class BaseImporter(ABC):
    """Base class for flight record importers."""

    source_name: str = "unknown"

    def __init__(self):
        self.batch_id = str(uuid.uuid4())
        self.imported_at = datetime.utcnow()

    @abstractmethod
    async def parse_file(self, file_path: Path) -> list[ParsedFlight]:
        """Parse a file and return a list of parsed flights."""
        pass

    @abstractmethod
    def validate_flight(self, flight: ParsedFlight) -> tuple[bool, Optional[str]]:
        """Validate a parsed flight. Returns (is_valid, error_message)."""
        pass
