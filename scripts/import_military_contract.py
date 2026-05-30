#!/usr/bin/env python3
"""Import military and contract flying records into PilotLog.

Sources:
  1. atoms_import_raw.ods "original" sheet  -> Avenge KA-300/350 (2011-2012)
  2. atoms_import_raw.ods "Liberty" sheet    -> Liberty MC-12W (2010-2011)
  3. SFA 2013 1H PDF                        -> Avenge KA-300/350 (Jan-May 2013)
  4. logbook ODS "prior" sheet (F-16 only)  -> USAF F-16 CJ at Misawa (2010-2011)
  5. logbook ODS "MC-12-worksheet"           -> MC-12W training at Meridian (2010)
  6. 781 audit XLS                           -> USAF F-16C flights (~2007)

De-duplication: (source, flight_date, origin, destination, tail_number, block_minutes)
Multiple flights on the same day ARE expected and valid.
"""

import asyncio
import datetime
import logging
import math
import re
import subprocess
import sys
import uuid
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pyexcel_ods3 import get_data
import openpyxl
import xlrd

from pilotlog.database.connection import get_session, init_db
from pilotlog.database.models import Flight, FlightAttribute, ImportBatch
from pilotlog.database.queries import sync_missing_airports

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# File paths
ATOMS_FILE = Path("/mnt/viperdrive/Storage_3/PERSONAL/documents/Flying/atoms_import_raw.ods")
LOGBOOK_FILE = Path("/mnt/viperdrive/Storage_3/PERSONAL/documents/Flying/Darrell_Thomas_logbook.ods")
SFA_2013_PDF = Path("/mnt/viperdrive/Storage_3/PERSONAL/documents/Flying/Avenge_hours/4.SFA_2013_1.pdf")
AUDIT_781_FILE = Path("/mnt/viperdrive/Storage_3/AVIATION/USAF/09.US_Air_Force/781 audit_August.xls")

# Aircraft type normalization
AIRCRAFT_NORM = {
    "KA 300": "KA-300",
    "KA300": "KA-300",
    "KA 350": "KA-350",
    "KA350": "KA-350",
    "MC-12W": "MC-12W",
    "F-16 CJ": "F-16CJ",
    "F-16C": "F-16C",
    "F016C": "F-16C",
}


def normalize_aircraft(raw: str) -> str:
    """Normalize aircraft type string."""
    if not raw:
        return raw
    raw = raw.strip()
    return AIRCRAFT_NORM.get(raw, raw)


def hours_to_minutes(hours_decimal) -> int:
    """Convert decimal hours to minutes, rounded to nearest minute."""
    if not hours_decimal or hours_decimal == "":
        return 0
    try:
        return round(float(hours_decimal) * 60)
    except (ValueError, TypeError):
        return 0


def make_dedup_key(source, flight_date, origin, destination, tail, block_minutes):
    """Create a dedup key for a flight."""
    return (source, str(flight_date), origin, destination, str(tail), block_minutes)


class ImportStats:
    def __init__(self, name):
        self.name = name
        self.processed = 0
        self.imported = 0
        self.duplicates = 0
        self.skipped = 0
        self.total_minutes = 0

    def report(self):
        hours = self.total_minutes // 60
        mins = self.total_minutes % 60
        logger.info(
            f"  {self.name}: {self.processed} processed, {self.imported} imported, "
            f"{self.duplicates} duplicates, {self.skipped} skipped, {hours}:{mins:02d} total"
        )


def add_flight_attributes(flight, attrs: dict):
    """Add FlightAttribute records for non-empty values."""
    for name, (value, unit) in attrs.items():
        if value and value != 0 and value != "" and value != 0.0:
            flight.attributes.append(
                FlightAttribute(
                    attribute_name=name,
                    attribute_value=str(value),
                    attribute_unit=unit,
                )
            )


# ---------------------------------------------------------------------------
# 1. Avenge flights from atoms_import_raw.ods "original" sheet
# ---------------------------------------------------------------------------
def parse_avenge_flights():
    """Parse Avenge KA-300/350 flights from atoms_import_raw.ods original sheet.

    Columns: Date, Tail, Aircraft, PilotInCommand, Pilot2, From, To, Sorties,
             ???, TotalTime, TotalTime2, PIC, SIC, ???, IP, Night, SimWx, ActWx,
             DayLand, NightLand, Pre, NonPre, ???, DutyFlag
    """
    data = get_data(str(ATOMS_FILE))
    rows = data["original"]
    flights = []

    for i, row in enumerate(rows):
        if len(row) < 10:
            continue
        if not isinstance(row[0], datetime.date):
            continue

        flight_date = row[0]
        tail = str(row[1]).strip() if row[1] else None
        aircraft_raw = str(row[2]).strip() if row[2] else ""
        pic_name = str(row[3]).strip() if len(row) > 3 and row[3] else ""
        sic_name = str(row[4]).strip() if len(row) > 4 and row[4] else ""
        origin = str(row[5]).strip().upper() if len(row) > 5 and row[5] else "OAKN"
        destination = str(row[6]).strip().upper() if len(row) > 6 and row[6] else "OAKN"

        total_hours = float(row[9]) if len(row) > 9 and row[9] else 0
        block_minutes = hours_to_minutes(total_hours)

        pic_hours = float(row[11]) if len(row) > 11 and row[11] else 0
        sic_hours = float(row[12]) if len(row) > 12 and row[12] else 0
        ip_hours = float(row[14]) if len(row) > 14 and row[14] else 0
        night_hours = float(row[15]) if len(row) > 15 and row[15] else 0
        sim_wx = float(row[16]) if len(row) > 16 and row[16] else 0
        act_wx = float(row[17]) if len(row) > 17 and row[17] else 0
        day_landings = int(row[18]) if len(row) > 18 and row[18] else 0
        night_landings = int(row[19]) if len(row) > 19 and row[19] else 0
        prec_app = int(row[20]) if len(row) > 20 and row[20] else 0
        nonprec_app = int(row[21]) if len(row) > 21 and row[21] else 0

        # Determine crew position: if Thomas is PIC, crew_position = PIC
        is_pic = "thomas" in pic_name.lower()
        crew_name_other = sic_name if is_pic else pic_name

        # Determine duty position
        if ip_hours > 0:
            crew_position = "IP"
        elif pic_hours > 0:
            crew_position = "PC"
        elif sic_hours > 0:
            crew_position = "PI"
        else:
            crew_position = "PI"

        flights.append({
            "source": "avenge",
            "flight_date": flight_date.isoformat(),
            "origin": origin,
            "destination": destination,
            "block_minutes": block_minutes,
            "tail_number": tail,
            "aircraft_type_raw": aircraft_raw,
            "aircraft_type": normalize_aircraft(aircraft_raw),
            "crew_position": crew_position,
            "crew_name": crew_name_other.strip() if crew_name_other else None,
            "remarks": f"Avenge Inc - Afghanistan",
            "attrs": {
                "pic_hours": (pic_hours, "hours"),
                "sic_hours": (sic_hours, "hours"),
                "ip_hours": (ip_hours, "hours"),
                "night_hours": (night_hours, "hours"),
                "sim_instrument": (sim_wx, "hours"),
                "actual_instrument": (act_wx, "hours"),
                "day_landings": (day_landings, "count"),
                "night_landings": (night_landings, "count"),
                "precision_approaches": (prec_app, "count"),
                "nonprecision_approaches": (nonprec_app, "count"),
            },
        })

    return flights


# ---------------------------------------------------------------------------
# 2. Liberty MC-12W flights from atoms_import_raw.ods "Liberty" sheet
# ---------------------------------------------------------------------------
def parse_liberty_flights():
    """Parse Liberty MC-12W flights from atoms_import_raw.ods Liberty sheet.

    Columns: ???, Date, Aircraft, Tail, From, To, TotalTime, DayLand, NightLand,
             ???, Night, NightLandFlag, Wx, ???, Approaches, Sim, ???, ???,
             PIC, SIC, ???, IP, Remarks
    """
    data = get_data(str(ATOMS_FILE))
    rows = data["Liberty"]
    flights = []

    for i, row in enumerate(rows):
        if len(row) < 7:
            continue
        if not (len(row) > 1 and isinstance(row[1], datetime.date)):
            continue

        flight_date = row[1]
        aircraft_raw = str(row[2]).strip() if len(row) > 2 and row[2] else "MC-12W"
        tail = str(row[3]).strip() if len(row) > 3 and row[3] else None
        origin = str(row[4]).strip().upper() if len(row) > 4 and row[4] else "KMEI"
        destination = str(row[5]).strip().upper() if len(row) > 5 and row[5] else "KMEI"
        total_hours = float(row[6]) if len(row) > 6 and row[6] else 0
        block_minutes = hours_to_minutes(total_hours)

        day_landings = int(row[7]) if len(row) > 7 and row[7] and row[7] != "" else 0
        night_landings = int(row[8]) if len(row) > 8 and row[8] and row[8] != "" else 0
        night_hours = float(row[10]) if len(row) > 10 and row[10] and row[10] != "" else 0
        wx_hours = float(row[12]) if len(row) > 12 and row[12] and row[12] != "" else 0
        approaches = int(row[14]) if len(row) > 14 and row[14] and row[14] != "" else 0
        sim_hours = float(row[15]) if len(row) > 15 and row[15] and row[15] != "" else 0
        pic_hours = float(row[18]) if len(row) > 18 and row[18] and row[18] != "" else 0
        sic_hours = float(row[19]) if len(row) > 19 and row[19] and row[19] != "" else 0
        ip_hours = float(row[21]) if len(row) > 21 and row[21] and row[21] != "" else 0
        remarks_field = str(row[22]).strip() if len(row) > 22 and row[22] else ""

        # Determine crew position
        if ip_hours > 0:
            crew_position = "IP"
        elif pic_hours > 0:
            crew_position = "PC"
        elif sic_hours > 0:
            crew_position = "PI"
        else:
            crew_position = "PI"

        remarks = f"Project Liberty - {remarks_field}" if remarks_field else "Project Liberty"

        flights.append({
            "source": "liberty",
            "flight_date": flight_date.isoformat(),
            "origin": origin,
            "destination": destination,
            "block_minutes": block_minutes,
            "tail_number": tail,
            "aircraft_type_raw": aircraft_raw,
            "aircraft_type": normalize_aircraft(aircraft_raw),
            "crew_position": crew_position,
            "crew_name": remarks_field if remarks_field else None,
            "remarks": remarks,
            "attrs": {
                "pic_hours": (pic_hours, "hours"),
                "sic_hours": (sic_hours, "hours"),
                "ip_hours": (ip_hours, "hours"),
                "night_hours": (night_hours, "hours"),
                "actual_instrument": (wx_hours, "hours"),
                "sim_instrument": (sim_hours, "hours"),
                "day_landings": (day_landings, "count"),
                "night_landings": (night_landings, "count"),
                "approaches": (approaches, "count"),
            },
        })

    return flights


# ---------------------------------------------------------------------------
# 3. Avenge 2013 1H flights from SFA PDF
# ---------------------------------------------------------------------------
def parse_sfa_2013_pdf():
    """Parse 2013 1H Avenge flights from SFA PDF using pdftotext."""
    result = subprocess.run(
        ["pdftotext", "-layout", str(SFA_2013_PDF), "-"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        logger.error(f"pdftotext failed: {result.stderr}")
        return []

    text = result.stdout
    flights = []

    # Parse using two patterns - one with airports, one without
    # Pattern 1: With From/To airports
    pat_full = re.compile(
        r"(\d{2}-[A-Za-z]{3}-\d{4})\s+"   # Date
        r"(KA\s*\d+)\s+"                   # Equipment
        r"(\S+)\s+"                         # Registration (tail)
        r"(\S{3,4})\s+"                     # From (3-4 char)
        r"(\S{3,4})\s+"                     # To (3-4 char)
        r"(\S+)\s+"                         # Pilot in Command
        r"(\S+(?:\s*,\s*\S+)?)\s+"          # Pilot (may have comma for "Jr.")
        r"(\d+\.\d+)\s+"                    # Flight Time
        r"(\d+\.?\d*)\s+"                   # Night Time
        r"(\d+\.?\d*)\s+"                   # Weather Sim
        r"(\d+\.?\d*)\s+"                   # Weather Actual
        r"(\d+)\s+"                         # Landings Day
        r"(\d+)\s+"                         # Landings Night
        r"(\d+)\s+"                         # Approaches Precision
        r"(\d+)"                            # Approaches Non-Precision
    )
    # Pattern 2: Without From/To airports (both blank)
    pat_no_apt = re.compile(
        r"(\d{2}-[A-Za-z]{3}-\d{4})\s+"   # Date
        r"(KA\s*\d+)\s+"                   # Equipment
        r"(\S+)\s+"                         # Registration (tail)
        r"(\S+)\s+"                         # Pilot in Command (no airports before)
        r"(\S+(?:\s*,\s*\S+)?)\s+"          # Pilot
        r"(\d+\.\d+)\s+"                    # Flight Time
        r"(\d+\.?\d*)\s+"                   # Night Time
        r"(\d+\.?\d*)\s+"                   # Weather Sim
        r"(\d+\.?\d*)\s+"                   # Weather Actual
        r"(\d+)\s+"                         # Landings Day
        r"(\d+)\s+"                         # Landings Night
        r"(\d+)\s+"                         # Approaches Precision
        r"(\d+)"                            # Approaches Non-Precision
    )
    # Pattern 3: From present, To blank (e.g., 11-Mar-2013 line)
    pat_from_only = re.compile(
        r"(\d{2}-[A-Za-z]{3}-\d{4})\s+"   # Date
        r"(KA\s*\d+)\s+"                   # Equipment
        r"(\S+)\s+"                         # Registration (tail)
        r"(\S{3,4})\s{5,}"                  # From + wide gap (To is blank)
        r"(\S+)\s+"                         # Pilot in Command
        r"(\S+(?:\s*,\s*\S+)?)\s+"          # Pilot
        r"(\d+\.\d+)\s+"                    # Flight Time
        r"(\d+\.?\d*)\s+"                   # Night Time
        r"(\d+\.?\d*)\s+"                   # Weather Sim
        r"(\d+\.?\d*)\s+"                   # Weather Actual
        r"(\d+)\s+"                         # Landings Day
        r"(\d+)\s+"                         # Landings Night
        r"(\d+)\s+"                         # Approaches Precision
        r"(\d+)"                            # Approaches Non-Precision
    )

    for line in text.split("\n"):
        line = line.strip()

        match = pat_full.search(line)
        if match:
            try:
                date_str = match.group(1)
                flight_date = datetime.datetime.strptime(date_str, "%d-%b-%Y").date()
            except ValueError:
                continue
            equipment = match.group(2).strip()
            tail = match.group(3).strip()
            origin = match.group(4).strip().upper()
            dest = match.group(5).strip().upper()
            pic_name = match.group(6).strip()
            pilot_name = match.group(7).strip()
            total_hours = float(match.group(8))
            night_hours = float(match.group(9))
            sim_wx = float(match.group(10))
            act_wx = float(match.group(11))
            day_landings = int(match.group(12))
            night_landings = int(match.group(13))
            prec_app = int(match.group(14))
            nonprec_app = int(match.group(15))
        else:
            match = pat_from_only.search(line)
            if match:
                try:
                    date_str = match.group(1)
                    flight_date = datetime.datetime.strptime(date_str, "%d-%b-%Y").date()
                except ValueError:
                    continue
                equipment = match.group(2).strip()
                tail = match.group(3).strip()
                origin = match.group(4).strip().upper()
                dest = origin  # To is blank, assume same as From
                pic_name = match.group(5).strip()
                pilot_name = match.group(6).strip()
                total_hours = float(match.group(7))
                night_hours = float(match.group(8))
                sim_wx = float(match.group(9))
                act_wx = float(match.group(10))
                day_landings = int(match.group(11))
                night_landings = int(match.group(12))
                prec_app = int(match.group(13))
                nonprec_app = int(match.group(14))
            else:
                match = pat_no_apt.search(line)
                if not match:
                    continue
                try:
                    date_str = match.group(1)
                    flight_date = datetime.datetime.strptime(date_str, "%d-%b-%Y").date()
                except ValueError:
                    continue
                equipment = match.group(2).strip()
                tail = match.group(3).strip()
                origin = "OAKN"  # Default to Kandahar
                dest = "OAKN"
                pic_name = match.group(4).strip()
                pilot_name = match.group(5).strip()
                total_hours = float(match.group(6))
                night_hours = float(match.group(7))
                sim_wx = float(match.group(8))
                act_wx = float(match.group(9))
                day_landings = int(match.group(10))
                night_landings = int(match.group(11))
                prec_app = int(match.group(12))
                nonprec_app = int(match.group(13))

        block_minutes = hours_to_minutes(total_hours)

        # Determine if Thomas is PIC
        is_pic = pic_name.lower() == "thomas"
        crew_name_other = pilot_name if is_pic else pic_name

        # Determine duty position based on who is PIC
        if is_pic:
            crew_position = "PC"  # PIC
        else:
            crew_position = "PI"  # Co-pilot

        flights.append({
            "source": "avenge",
            "flight_date": flight_date.isoformat(),
            "origin": origin,
            "destination": dest,
            "block_minutes": block_minutes,
            "tail_number": tail,
            "aircraft_type_raw": equipment,
            "aircraft_type": normalize_aircraft(equipment),
            "crew_position": crew_position,
            "crew_name": crew_name_other,
            "remarks": "Avenge Inc - Afghanistan (2013 1H SFA)",
            "attrs": {
                "night_hours": (night_hours, "hours"),
                "sim_instrument": (sim_wx, "hours"),
                "actual_instrument": (act_wx, "hours"),
                "day_landings": (day_landings, "count"),
                "night_landings": (night_landings, "count"),
                "precision_approaches": (prec_app, "count"),
                "nonprecision_approaches": (nonprec_app, "count"),
            },
        })

    return flights


# ---------------------------------------------------------------------------
# 4. F-16 flights from logbook ODS "prior" sheet
# ---------------------------------------------------------------------------
def parse_prior_sheet_flights():
    """Parse F-16 and KA350 flights from Darrell_Thomas_logbook.ods prior sheet.

    Extract F-16 flights AND KA350 flights (Flight Safety sims + initial training).
    Skip MC-12W entries (those are covered by Liberty/atoms data).

    Columns (offset by 1 blank): Date, Make/Model, Ident, From, TO,
        Total Duration, SEL, SES, MEL, Turboprop, Heli, Glider, Complex, Jet,
        Day Landings, Night Landings, ???, NIGHT, Actual Instr, Sim Instr,
        Approaches, ???, XC, SOLO, PIC, SIC, Dual, CFI
    """
    data = get_data(str(LOGBOOK_FILE))
    rows = data["prior"]
    flights = []

    for i, row in enumerate(rows):
        if len(row) < 7:
            continue
        if not (len(row) > 1 and isinstance(row[1], datetime.date)):
            continue

        aircraft_raw = str(row[2]).strip() if len(row) > 2 and row[2] else ""

        # Only F-16 and KA350 flights - skip MC-12W (those are in Liberty/atoms data)
        is_f16 = "F-16" in aircraft_raw or "f-16" in aircraft_raw.lower()
        is_ka350 = "KA" in aircraft_raw.upper()
        if not is_f16 and not is_ka350:
            continue

        flight_date = row[1]
        tail = str(row[3]).strip() if len(row) > 3 and row[3] else None
        origin = str(row[4]).strip().upper() if len(row) > 4 and row[4] else ""
        destination = str(row[5]).strip().upper() if len(row) > 5 and row[5] else ""
        total_hours = float(row[6]) if len(row) > 6 and row[6] else 0
        block_minutes = hours_to_minutes(total_hours)

        jet_hours = float(row[14]) if len(row) > 14 and row[14] and row[14] != "" else 0
        day_landings = int(row[15]) if len(row) > 15 and row[15] and row[15] != "" else 0
        night_landings = int(row[16]) if len(row) > 16 and row[16] and row[16] != "" else 0
        night_hours = float(row[18]) if len(row) > 18 and row[18] and row[18] != "" else 0
        act_instr = float(row[19]) if len(row) > 19 and row[19] and row[19] != "" else 0
        sim_instr = float(row[20]) if len(row) > 20 and row[20] and row[20] != "" else 0
        approaches = int(row[21]) if len(row) > 21 and row[21] and row[21] != "" else 0
        xc_hours = float(row[23]) if len(row) > 23 and row[23] and row[23] != "" else 0
        solo_hours = float(row[24]) if len(row) > 24 and row[24] and row[24] != "" else 0
        pic_hours = float(row[25]) if len(row) > 25 and row[25] and row[25] != "" else 0
        sic_hours = float(row[26]) if len(row) > 26 and row[26] and row[26] != "" else 0
        dual_hours = float(row[27]) if len(row) > 27 and row[27] and row[27] != "" else 0
        cfi_hours = float(row[28]) if len(row) > 28 and row[28] and row[28] != "" else 0

        # Determine position
        if cfi_hours > 0:
            crew_position = "IP"
        elif pic_hours > 0:
            crew_position = "PC"
        elif sic_hours > 0:
            crew_position = "PI"
        elif dual_hours > 0:
            crew_position = "ST"  # Student
        else:
            crew_position = "PC"

        # Set source and remarks based on aircraft type
        if is_f16:
            source = "usaf_f16"
            remarks = "USAF F-16 - Misawa AB (RJSM)"
        else:
            # KA350: Flight Safety sims or initial training
            is_sim = tail and "sim" in str(tail).lower()
            if is_sim:
                source = "flight_safety"
                remarks = "Flight Safety KA350 simulator - Atlanta"
            else:
                source = "avenge"
                remarks = "KA350 initial training - Meridian"

        flights.append({
            "source": source,
            "flight_date": flight_date.isoformat(),
            "origin": origin,
            "destination": destination,
            "block_minutes": block_minutes,
            "tail_number": tail,
            "aircraft_type_raw": aircraft_raw,
            "aircraft_type": normalize_aircraft(aircraft_raw),
            "crew_position": crew_position,
            "remarks": remarks,
            "attrs": {
                "pic_hours": (pic_hours, "hours"),
                "sic_hours": (sic_hours, "hours"),
                "dual_received": (dual_hours, "hours"),
                "cfi_hours": (cfi_hours, "hours"),
                "night_hours": (night_hours, "hours"),
                "actual_instrument": (act_instr, "hours"),
                "sim_instrument": (sim_instr, "hours"),
                "cross_country": (xc_hours, "hours"),
                "solo": (solo_hours, "hours"),
                "day_landings": (day_landings, "count"),
                "night_landings": (night_landings, "count"),
                "approaches": (approaches, "count"),
            },
        })

    return flights


# ---------------------------------------------------------------------------
# 5. MC-12W training flights - SKIPPED (covered by Liberty sheet in atoms)
# ---------------------------------------------------------------------------
def _parse_mc12_training_flights_UNUSED():
    """Parse MC-12W training flights from Darrell_Thomas_logbook.ods MC-12-worksheet.

    These are the initial MC-12W training flights at Meridian and sims in Atlanta,
    BEFORE the Liberty deployment. Need to de-dup against Liberty sheet.
    """
    data = get_data(str(LOGBOOK_FILE))
    rows = data["MC-12-worksheet"]
    flights = []

    # Find column structure - look for header row
    # Columns (offset by 2): Date, Make/Model, Ident, From, TO,
    #   Total Duration, MEL, Turboprop, Heli, Glider, Jet,
    #   Day Landings, Night Landings, ???, NIGHT, Actual Instr, Sim Instr,
    #   Approaches, ???, XC, SOLO, PIC, SIC, Dual, CFI, Remarks

    for i, row in enumerate(rows):
        if len(row) < 8:
            continue

        # Date is in column 2 (index 2) for this sheet
        date_val = row[2] if len(row) > 2 else None
        if not isinstance(date_val, datetime.date):
            continue

        flight_date = date_val
        aircraft_raw = str(row[3]).strip() if len(row) > 3 and row[3] else "MC-12W"
        tail = str(row[4]).strip() if len(row) > 4 and row[4] else None
        origin = str(row[5]).strip().upper() if len(row) > 5 and row[5] else "KMEI"
        destination = str(row[6]).strip().upper() if len(row) > 6 and row[6] else "KMEI"
        total_hours = float(row[7]) if len(row) > 7 and row[7] and row[7] != "" else 0
        block_minutes = hours_to_minutes(total_hours)

        if block_minutes == 0:
            continue

        night_hours = float(row[16]) if len(row) > 16 and row[16] and row[16] != "" else 0
        act_instr = float(row[17]) if len(row) > 17 and row[17] and row[17] != "" else 0
        sim_instr = float(row[18]) if len(row) > 18 and row[18] and row[18] != "" else 0
        approaches = int(row[19]) if len(row) > 19 and row[19] and row[19] != "" else 0
        xc_hours = float(row[21]) if len(row) > 21 and row[21] and row[21] != "" else 0
        pic_hours = float(row[23]) if len(row) > 23 and row[23] and row[23] != "" else 0
        sic_hours = float(row[24]) if len(row) > 24 and row[24] and row[24] != "" else 0
        dual_hours = float(row[25]) if len(row) > 25 and row[25] and row[25] != "" else 0
        cfi_hours = float(row[26]) if len(row) > 26 and row[26] and row[26] != "" else 0
        remarks_field = str(row[27]).strip() if len(row) > 27 and row[27] else ""

        if cfi_hours > 0:
            crew_position = "IP"
        elif pic_hours > 0:
            crew_position = "PC"
        elif sic_hours > 0:
            crew_position = "PI"
        elif dual_hours > 0:
            crew_position = "ST"
        else:
            crew_position = "PI"

        flights.append({
            "source": "usaf_mc12",
            "flight_date": flight_date.isoformat(),
            "origin": origin,
            "destination": destination,
            "block_minutes": block_minutes,
            "tail_number": tail,
            "aircraft_type_raw": aircraft_raw,
            "aircraft_type": normalize_aircraft(aircraft_raw),
            "crew_position": crew_position,
            "crew_name": remarks_field if remarks_field else None,
            "remarks": f"USAF MC-12W training - {remarks_field}" if remarks_field else "USAF MC-12W training",
            "attrs": {
                "pic_hours": (pic_hours, "hours"),
                "sic_hours": (sic_hours, "hours"),
                "dual_received": (dual_hours, "hours"),
                "cfi_hours": (cfi_hours, "hours"),
                "night_hours": (night_hours, "hours"),
                "actual_instrument": (act_instr, "hours"),
                "sim_instrument": (sim_instr, "hours"),
                "cross_country": (xc_hours, "hours"),
                "approaches": (approaches, "count"),
            },
        })

    return flights


# ---------------------------------------------------------------------------
# 6. F-16C flights from 781 audit
# ---------------------------------------------------------------------------
def parse_781_audit():
    """Parse F-16C flights from 781 audit spreadsheet.

    Excel serial dates need conversion. Only extract Thomas's flights.
    """
    wb = xlrd.open_workbook(str(AUDIT_781_FILE))
    ws = wb.sheet_by_index(0)
    flights = []

    # Header at row 4: Flight Dt, Name, Crew Pos., Tail Number, MDS, Mission #, Mission Sym., Sorties, Hours
    current_name = None
    for i in range(5, ws.nrows):
        row = [ws.cell_value(i, j) for j in range(ws.ncols)]

        # Get date
        date_val = row[0]
        if not date_val:
            continue

        # Track name - it only appears on first row for each pilot
        if row[1]:
            current_name = str(row[1]).strip()

        # Only Thomas's flights
        if not current_name or "thomas" not in current_name.lower():
            continue

        # Convert Excel serial date
        try:
            if isinstance(date_val, float):
                flight_date = datetime.datetime(1899, 12, 30) + datetime.timedelta(days=int(date_val))
                flight_date = flight_date.date()
            else:
                continue
        except (ValueError, OverflowError):
            continue

        crew_pos = str(row[2]).strip() if row[2] else ""
        tail = str(row[3]).strip() if row[3] else None
        mds = str(row[4]).strip() if row[4] else "F-16C"
        mission_num = str(row[5]).strip() if row[5] else None
        mission_sym = str(row[6]).strip() if row[6] else ""
        sorties = int(row[7]) if row[7] else 1
        hours = float(row[8]) if row[8] else 0
        block_minutes = hours_to_minutes(hours)

        if block_minutes == 0:
            continue

        # Map USAF crew positions
        pos_map = {"MPCE": "PC", "MPIL": "PI", "IP": "IP", "SPIL": "PI", "SCP": "PC"}
        crew_position = pos_map.get(crew_pos, crew_pos[:2] if crew_pos else "PC")

        flights.append({
            "source": "usaf_f16",
            "flight_date": flight_date.isoformat(),
            "origin": "RKJK",  # Kunsan AB
            "destination": "RKJK",
            "block_minutes": block_minutes,
            "tail_number": tail,
            "aircraft_type_raw": mds,
            "aircraft_type": normalize_aircraft(mds),
            "crew_position": crew_position,
            "remarks": f"USAF F-16C Kunsan AB - Msn {mission_num} ({mission_sym})" if mission_num else "USAF F-16C Kunsan AB",
            "attrs": {
                "mission_number": (mission_num, None),
                "mission_symbol": (mission_sym, None),
                "sorties": (sorties, "count"),
            },
        })

    return flights


# ---------------------------------------------------------------------------
# Main import logic
# ---------------------------------------------------------------------------
async def import_flights(flight_list, source_name, stats, session, seen_keys):
    """Import a list of flight dicts into the database."""
    batch_id = str(uuid.uuid4())
    batch = ImportBatch(
        id=batch_id,
        source=source_name,
        filename=f"import_military_contract_{source_name}",
        imported_at=datetime.datetime.utcnow(),
        rows_processed=0,
        rows_imported=0,
        rows_skipped=0,
        rows_duplicate=0,
    )
    session.add(batch)
    await session.flush()

    for f in flight_list:
        stats.processed += 1

        # Build dedup key
        key = make_dedup_key(
            f["source"],
            f["flight_date"],
            f["origin"],
            f["destination"],
            f.get("tail_number", ""),
            f["block_minutes"],
        )

        if key in seen_keys:
            stats.duplicates += 1
            continue
        seen_keys.add(key)

        # Also check database for existing flights
        from sqlalchemy import select
        existing = await session.execute(
            select(Flight).where(
                Flight.source == f["source"],
                Flight.flight_date == f["flight_date"],
                Flight.origin == f["origin"],
                Flight.destination == f["destination"],
                Flight.block_minutes == f["block_minutes"],
            )
        )
        if existing.scalar_one_or_none():
            stats.duplicates += 1
            continue

        attrs = f.pop("attrs", {})

        flight = Flight(
            source=f["source"],
            flight_date=f["flight_date"],
            origin=f["origin"],
            destination=f["destination"],
            block_minutes=f["block_minutes"],
            tail_number=f.get("tail_number"),
            aircraft_type_raw=f.get("aircraft_type_raw"),
            aircraft_type=f.get("aircraft_type"),
            crew_position=f.get("crew_position"),
            crew_name=f.get("crew_name"),
            remarks=f.get("remarks"),
            is_deadhead=False,
            pic_takeoff=False,
            pic_landing=False,
            import_batch_id=batch_id,
        )

        add_flight_attributes(flight, attrs)
        session.add(flight)

        stats.imported += 1
        stats.total_minutes += f["block_minutes"]

    batch.rows_processed = stats.processed
    batch.rows_imported = stats.imported
    batch.rows_skipped = stats.skipped
    batch.rows_duplicate = stats.duplicates


async def main():
    """Run the full import."""
    await init_db()

    logger.info("=" * 60)
    logger.info("Military & Contract Flight Import")
    logger.info("=" * 60)

    # Parse all sources
    logger.info("\nParsing data sources...")

    avenge_flights = parse_avenge_flights()
    logger.info(f"  Avenge (2011-2012): {len(avenge_flights)} flights")

    liberty_flights = parse_liberty_flights()
    logger.info(f"  Liberty (2010-2011): {len(liberty_flights)} flights")

    sfa_2013_flights = parse_sfa_2013_pdf()
    logger.info(f"  Avenge 2013 1H (PDF): {len(sfa_2013_flights)} flights")

    prior_flights = parse_prior_sheet_flights()
    logger.info(f"  Prior sheet (F-16 + KA350): {len(prior_flights)} flights")

    audit_flights = parse_781_audit()
    logger.info(f"  781 audit (Kunsan): {len(audit_flights)} flights")

    # Import into database
    logger.info("\nImporting to database...")
    seen_keys = set()

    async with get_session() as session:
        # Import in order - atoms data first (most reliable/cross-checked)
        stats_avenge = ImportStats("Avenge (2011-2012)")
        await import_flights(avenge_flights, "avenge", stats_avenge, session, seen_keys)
        stats_avenge.report()

        stats_liberty = ImportStats("Liberty MC-12W")
        await import_flights(liberty_flights, "liberty", stats_liberty, session, seen_keys)
        stats_liberty.report()

        stats_sfa = ImportStats("Avenge 2013 1H")
        await import_flights(sfa_2013_flights, "avenge", stats_sfa, session, seen_keys)
        stats_sfa.report()

        stats_prior = ImportStats("Prior sheet (F-16 + KA350)")
        await import_flights(prior_flights, "mixed", stats_prior, session, seen_keys)
        stats_prior.report()

        stats_781 = ImportStats("781 audit (Kunsan)")
        await import_flights(audit_flights, "usaf_f16", stats_781, session, seen_keys)
        stats_781.report()

        await session.commit()

        # Sync airport data for new airports
        logger.info("\nSyncing airport data...")
        new_airports = await sync_missing_airports(session)
        if new_airports:
            logger.info(f"  Added airports: {', '.join(sorted(new_airports))}")

    # Summary
    all_stats = [stats_avenge, stats_liberty, stats_sfa, stats_prior, stats_781]
    total_imported = sum(s.imported for s in all_stats)
    total_minutes = sum(s.total_minutes for s in all_stats)
    total_duplicates = sum(s.duplicates for s in all_stats)

    hours = total_minutes // 60
    mins = total_minutes % 60

    logger.info("\n" + "=" * 60)
    logger.info(f"TOTAL: {total_imported} flights imported, {total_duplicates} duplicates skipped")
    logger.info(f"TOTAL TIME: {hours}:{mins:02d}")
    logger.info("=" * 60)

    # Note gaps
    logger.info("\nDATA GAPS (summary-only, no individual flights):")
    logger.info("  - Avenge 2013 2H (Jun-Oct 2013, Bagram): ~168.1 hrs")
    logger.info("  - T-38/AT-38 time: ~738.8 hrs")
    logger.info("  - F-16 time at Luke/Kunsan (pre-2007): see F-16 worksheet")
    logger.info("  - Civilian time: ~254.2 hrs")
    logger.info("  - Student/UPT time: ~189.9 hrs")
    logger.info("  - Flight Safety BE350 sims: ~26.9 hrs")


if __name__ == "__main__":
    asyncio.run(main())
