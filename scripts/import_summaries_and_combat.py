#!/usr/bin/env python3
"""Add summary placeholder entries and combat sortie details.

1. Create one-line summary placeholder entries for flying time without
   individual sortie records (F-16, T-38, civilian, UPT, Avenge 2013 2H).
   Uses ARMS Flying History Report (12 Apr 2011) as authoritative source.

2. Parse Air Medal Sortie Tracker and add combat mission details
   (mission number, mission symbol, combat hours, NVG time) as
   FlightAttributes to matching Liberty MC-12W flights.
"""

import asyncio
import datetime
import logging
import sys
import uuid
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sqlalchemy import select, and_
from pilotlog.database.connection import get_session, init_db
from pilotlog.database.models import Flight, FlightAttribute, ImportBatch
from pilotlog.database.queries import sync_missing_airports

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

SORTIE_TRACKER = Path(
    "/mnt/viperdrive/Storage_3/AVIATION/USAF/09.US_Air_Force"
    "/Balad_Op_Sup_master/Air Medal Sortie Tracker(Thomas, Darrell).htm"
)

# Summary placeholders based on ARMS Flying History Report (12 Apr 2011),
# biography, and logbook "Current Times" sheet.
# Only create entries for time NOT already covered by individual flights.
# Already imported: F-16C 842.9h (11 sorties from prior sheet cover ~18.9h of Misawa 2010),
#   F-16C 4 Kunsan sorties (6.4h from 781 audit Aug 2007)
# ARMS Flying History Report (12 Apr 2011) is authoritative for USAF time.
# Already imported individually: 11 F-16CJ Misawa 2010 (18.9h), 4 F-16C Kunsan Aug 2007 (6.4h)
# F-16C(S) ARMS total: 842.9h / 535 sorties (15 Mar 96 - 25 Mar 08)
# F-16D(S) ARMS total: 212.6h / 153 sorties (14 Feb 96 - 14 Nov 07)
# SMF-16C(Q) sim: 114.8h / 76 sorties
# SF-16CR(Q) sim: 17.0h / 11 sorties
# AT-38B(S): 492.9h / 502 sorties (21 Nov 95 - 03 Mar 02)
# T-38C(S): 224.0h / 235 sorties (12 Feb 02 - 23 Dec 03)
# Student time: 189.9h
# Already imported: 25.3h F-16 individual flights
F16C_REMAINING = 842.9 - 18.9 - 6.4  # minus already imported individual flights

SUMMARY_ENTRIES = [
    # F-16C single-seat time (all assignments, minus individually imported flights)
    {
        "source": "usaf_f16",
        "flight_date": "2008-03-25",  # ARMS last flown date
        "origin": "RJSM",
        "destination": "RJSM",
        "aircraft_type_raw": "F-16C",
        "aircraft_type": "F-16C",
        "remarks": (
            "SUMMARY: F-16C single-seat time (ARMS: 842.9h/535 sorties, 15 Mar 96 - 25 Mar 08). "
            "Assignments: Luke RTU 61FS (1996-97), Misawa 13FS (1997-2000), "
            "Luke refresher 302FS (Jan-May 2004), Kunsan 8FW (2004-05), Misawa 14FS (2005-08). "
            f"{F16C_REMAINING:.1f}h remaining after 15 individually imported flights. "
            "Individual sorties pending scan of green book."
        ),
        "block_minutes": round(F16C_REMAINING * 60),
        "crew_position": "PC",
    },
    # F-16D dual-seat time
    {
        "source": "usaf_f16",
        "flight_date": "2007-11-14",
        "origin": "RJSM",
        "destination": "RJSM",
        "aircraft_type_raw": "F-16D",
        "aircraft_type": "F-16D",
        "remarks": "SUMMARY: F-16D dual-seat time (ARMS: 212.6h/153 sorties, 14 Feb 96 - 14 Nov 07). Individual sorties pending scan of green book.",
        "block_minutes": round(212.6 * 60),
        "crew_position": "PC",
    },
    # F-16 simulator time
    {
        "source": "usaf_f16",
        "flight_date": "2008-01-16",
        "origin": "RJSM",
        "destination": "RJSM",
        "aircraft_type_raw": "F-16 Sim",
        "aircraft_type": "F-16-SIM",
        "remarks": "SUMMARY: F-16 simulator time (ARMS: SMF-16C 114.8h/76 sorties + SF-16CR 17.0h/11 sorties).",
        "block_minutes": round((114.8 + 17.0) * 60),
        "crew_position": "PC",
    },
    # AT-38B — IFF + IP at Randolph/Moody
    {
        "source": "usaf_t38",
        "flight_date": "2002-03-03",
        "origin": "KRND",
        "destination": "KRND",
        "aircraft_type_raw": "AT-38B",
        "aircraft_type": "AT-38B",
        "remarks": "SUMMARY: AT-38B (ARMS: 492.9h/502 sorties, 21 Nov 95 - 03 Mar 02). IFF student 560 FTS Randolph (Nov 95-Jan 96), then IP/Chief W&T 435 FS Randolph & Moody (Feb 2000-Mar 2002). Individual sorties pending scan of green book.",
        "block_minutes": round(492.9 * 60),
        "crew_position": "IP",
    },
    # T-38C — IP at Moody
    {
        "source": "usaf_t38",
        "flight_date": "2003-12-23",
        "origin": "KVAD",
        "destination": "KVAD",
        "aircraft_type_raw": "T-38C",
        "aircraft_type": "T-38C",
        "remarks": "SUMMARY: T-38C IP (ARMS: 224.0h/235 sorties, 12 Feb 02 - 23 Dec 03). 435 FS/479 FTG, Moody AFB. Individual sorties pending scan of green book.",
        "block_minutes": round(224.0 * 60),
        "crew_position": "IP",
    },
    # UPT student time — Vance AFB
    {
        "source": "usaf_upt",
        "flight_date": "1995-10-24",
        "origin": "KVNC",
        "destination": "KVNC",
        "aircraft_type_raw": "T-37/T-38",
        "aircraft_type": "T-37/T-38",
        "remarks": "SUMMARY: UPT student, Vance AFB (Sep 1994-Oct 1995). ARMS: 189.9h student time. Individual sorties pending scan of green book.",
        "block_minutes": round(189.9 * 60),
        "crew_position": "ST",
    },
    # Civilian time
    {
        "source": "civilian",
        "flight_date": "2013-10-01",
        "origin": "KLAS",
        "destination": "KLAS",
        "aircraft_type_raw": "Various SEL",
        "aircraft_type": "GA-SEL",
        "remarks": "SUMMARY: Civilian flying time. 254.2h per logbook Current Times sheet.",
        "block_minutes": round(254.2 * 60),
        "crew_position": "PC",
    },
    # Avenge 2013 2H (Bagram)
    {
        "source": "avenge",
        "flight_date": "2013-09-25",
        "origin": "OAIX",
        "destination": "OAIX",
        "aircraft_type_raw": "KA 300",
        "aircraft_type": "KA-300",
        "remarks": "SUMMARY: Avenge 2013 2H, Bagram (OAIX), through 25 Sep 2013. 168.1h per logbook Current Times. SFA data was on ATOMS portal, never exported.",
        "block_minutes": round(168.1 * 60),
        "crew_position": "IP",
    },
]


def parse_air_medal_tracker():
    """Parse Air Medal Sortie Tracker HTML for combat mission details."""

    class TableParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.in_td = False
            self.cells = []
            self.current_row = []
            self.data = ""

        def handle_starttag(self, tag, attrs):
            if tag == "td":
                self.in_td = True
                self.data = ""
            if tag == "tr":
                self.current_row = []

        def handle_endtag(self, tag):
            if tag == "td":
                self.in_td = False
                self.current_row.append(self.data.strip())
            if tag == "tr" and self.current_row:
                self.cells.append(self.current_row)

        def handle_data(self, data):
            if self.in_td:
                self.data += data

    with open(SORTIE_TRACKER) as f:
        html = f.read()

    p = TableParser()
    p.feed(html)

    flights = []
    for row in p.cells[1:]:
        if not row or len(row) < 10:
            continue

        if len(row) >= 13:
            date_str, msn, sym = row[1], row[2], row[3]
            prim, sec, instr, other, nvg = row[4], row[5], row[6], row[7], row[8]
            total, sorties, cmb_hrs, cmb_sort = row[9], row[10], row[11], row[12]
        elif len(row) >= 12:
            date_str, msn, sym = row[0], row[1], row[2]
            prim, sec, instr, other, nvg = row[3], row[4], row[5], row[6], row[7]
            total, sorties, cmb_hrs, cmb_sort = row[8], row[9], row[10], row[11]
        else:
            continue

        if not date_str or "Sum" in str(cmb_hrs) or "Count" in str(cmb_sort):
            continue

        try:
            d = datetime.datetime.strptime(date_str, "%d-%b-%y").date()
        except ValueError:
            continue

        try:
            total_hrs = float(total)
            combat_hrs = float(cmb_hrs) if cmb_hrs else 0
            nvg_hrs = float(nvg) if nvg else 0
        except (ValueError, TypeError):
            continue

        flights.append({
            "date": d.isoformat(),
            "total_hrs": total_hrs,
            "mission_number": msn,
            "mission_symbol": sym,
            "combat_hours": combat_hrs,
            "nvg_hours": nvg_hrs,
        })

    return flights


async def main():
    await init_db()

    logger.info("=" * 60)
    logger.info("Summary Placeholders & Combat Sortie Details")
    logger.info("=" * 60)

    async with get_session() as session:
        # ----------------------------------------------------------
        # 1. Add summary placeholder entries
        # ----------------------------------------------------------
        logger.info("\n--- Summary Placeholders ---")
        batch_id = str(uuid.uuid4())
        batch = ImportBatch(
            id=batch_id,
            source="summary",
            filename="import_summaries_and_combat.py",
            imported_at=datetime.datetime.utcnow(),
            rows_processed=len(SUMMARY_ENTRIES),
        )
        session.add(batch)
        await session.flush()

        imported = 0
        for entry in SUMMARY_ENTRIES:
            # Check for existing summary entry
            existing = await session.execute(
                select(Flight).where(
                    Flight.source == entry["source"],
                    Flight.flight_date == entry["flight_date"],
                    Flight.remarks.like("SUMMARY:%"),
                    Flight.aircraft_type == entry["aircraft_type"],
                )
            )
            if existing.scalar_one_or_none():
                logger.info(f"  SKIP (exists): {entry['aircraft_type']} {entry['flight_date']}")
                continue

            flight = Flight(
                source=entry["source"],
                flight_date=entry["flight_date"],
                origin=entry["origin"],
                destination=entry["destination"],
                block_minutes=entry["block_minutes"],
                aircraft_type_raw=entry.get("aircraft_type_raw"),
                aircraft_type=entry["aircraft_type"],
                crew_position=entry.get("crew_position"),
                is_deadhead=False,
                pic_takeoff=False,
                pic_landing=False,
                remarks=entry["remarks"],
                import_batch_id=batch_id,
            )
            session.add(flight)
            imported += 1
            hrs = entry["block_minutes"] // 60
            mins = entry["block_minutes"] % 60
            logger.info(f"  ADD: {entry['aircraft_type']:10s} {entry['flight_date']} {hrs:4d}:{mins:02d} {entry['origin']}")

        batch.rows_imported = imported
        logger.info(f"\n  {imported} summary entries added")

        # ----------------------------------------------------------
        # 2. Add Air Medal combat sortie details to Liberty flights
        # ----------------------------------------------------------
        logger.info("\n--- Air Medal Combat Sortie Details ---")
        combat_sorties = parse_air_medal_tracker()
        logger.info(f"  Parsed {len(combat_sorties)} combat sorties from tracker")

        matched = 0
        unmatched = 0
        already_tagged = 0

        for sortie in combat_sorties:
            # Find matching Liberty flight by date and approximate block time
            block_minutes_target = round(sortie["total_hrs"] * 60)
            result = await session.execute(
                select(Flight).where(
                    Flight.source == "liberty",
                    Flight.flight_date == sortie["date"],
                    Flight.block_minutes.between(
                        block_minutes_target - 6,  # ±6 min tolerance
                        block_minutes_target + 6,
                    ),
                )
            )
            flights = list(result.scalars().all())

            if not flights:
                # Try broader match — just date
                result = await session.execute(
                    select(Flight).where(
                        Flight.source == "liberty",
                        Flight.flight_date == sortie["date"],
                    )
                )
                flights = list(result.scalars().all())

            if not flights:
                unmatched += 1
                continue

            flight = flights[0]  # Best match

            # Check if already tagged
            existing_attr = await session.execute(
                select(FlightAttribute).where(
                    FlightAttribute.flight_id == flight.id,
                    FlightAttribute.attribute_name == "mission_number",
                )
            )
            if existing_attr.scalar_one_or_none():
                already_tagged += 1
                continue

            # Add combat attributes
            attrs = [
                FlightAttribute(flight_id=flight.id, attribute_name="mission_number",
                                attribute_value=sortie["mission_number"]),
                FlightAttribute(flight_id=flight.id, attribute_name="mission_symbol",
                                attribute_value=sortie["mission_symbol"]),
                FlightAttribute(flight_id=flight.id, attribute_name="combat_hours",
                                attribute_value=str(sortie["combat_hours"]), attribute_unit="hours"),
                FlightAttribute(flight_id=flight.id, attribute_name="combat_sortie",
                                attribute_value="true"),
            ]
            if sortie["nvg_hours"] > 0:
                attrs.append(
                    FlightAttribute(flight_id=flight.id, attribute_name="nvg_hours",
                                    attribute_value=str(sortie["nvg_hours"]), attribute_unit="hours")
                )

            for attr in attrs:
                session.add(attr)
            matched += 1

        logger.info(f"  {matched} flights tagged with combat details")
        logger.info(f"  {already_tagged} already tagged (skipped)")
        logger.info(f"  {unmatched} combat sorties with no matching Liberty flight")

        await session.commit()

        # Sync airports
        logger.info("\nSyncing airports...")
        new_airports = await sync_missing_airports(session)
        if new_airports:
            logger.info(f"  Added: {', '.join(sorted(new_airports))}")

    logger.info("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
