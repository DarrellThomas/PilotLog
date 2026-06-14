"""Seniority tracker — parse SWAPA seniority list, compute position at each base.

Downloads the full seniority list CSV from SWAPA, finds the pilot by employee ID,
and computes where they'd fall in the seniority order at every base.
"""

import csv
import logging
import sys
import time
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent / "data"
SENIORITY_CSV = DATA_DIR / "seniority_list.csv"
ENV_FILE = Path.home() / ".env"


def _get_employee_id():
    """Get pilot's employee ID from ~/.env."""
    with open(ENV_FILE) as f:
        for line in f:
            if line.startswith('SWAPA_ID='):
                return line.split('=', 1)[1].strip().strip('"').lstrip('eE')
    return None


def download_seniority_csv(headless=True):
    """Download fresh seniority list CSV from SWAPA."""
    from playwright.sync_api import sync_playwright
    from pilotlog.swapa.client import TOOLS, _load_cookies, ensure_logged_in

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
            viewport={"width": 1280, "height": 900},
            ignore_https_errors=True,
            accept_downloads=True,
        )
        _load_cookies(context)
        page = context.new_page()

        try:
            ensure_logged_in(page, TOOLS["seniority_list"])
            time.sleep(5)

            for btn in page.query_selector_all("button"):
                if "Get Report" in (btn.inner_text() or ""):
                    btn.click()
                    break
            time.sleep(20)

            csv_btn = page.get_by_text("CSV", exact=True).first
            with page.expect_download(timeout=30000) as dl_info:
                csv_btn.click()

            download = dl_info.value
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            download.save_as(str(SENIORITY_CSV))
            logger.info(f"Downloaded seniority list ({SENIORITY_CSV.stat().st_size} bytes)")
            return SENIORITY_CSV

        except Exception as e:
            logger.error(f"Seniority download failed: {e}")
            return None
        finally:
            browser.close()


def parse_seniority_csv(csv_path=None):
    """Parse seniority list CSV into list of pilot dicts.

    Returns list of dicts with keys:
        rank, system_seniority, emp_id, name, base, seat,
        hire_date, upgrade_date, retirement_date
    """
    path = csv_path or SENIORITY_CSV
    if not path.exists():
        raise FileNotFoundError(f"Seniority CSV not found: {path}")

    pilots = []
    content = path.read_text(encoding="utf-8-sig")
    reader = csv.DictReader(StringIO(content))

    for row in reader:
        pilots.append({
            "rank": int(row.get("CURRENT_Senioirty_Rank", 0) or 0),
            "system_seniority": int(row.get("System_Seniority_Number", 0) or 0),
            "emp_id": str(row.get("ID_Number", "")).strip(),
            "name": row.get("Name", "").strip(),
            "base": row.get("Base", "").strip(),
            "seat": row.get("Seat", "").strip(),
            "hire_date": row.get("Date_of_Hire1", "").strip(),
            "upgrade_date": row.get("Upgrade_Date", "").strip(),
            "retirement_date": row.get("Projected_Retirement_Date", "").strip(),
        })

    return pilots


def compute_base_positions(pilots, employee_id):
    """Compute the pilot's hypothetical seniority position at each base.

    Seniority is based on system seniority number (lower = more senior).
    At any base, your position = how many pilots at that base have a
    lower system seniority number than you, plus one.

    Returns dict with:
        pilot: the pilot's own record
        current_base: {base, position, total, percentile}
        all_bases: {base: {position, total, percentile}} for every base
        system_rank: overall system rank
        total_pilots: total on the list
    """
    # Find the pilot
    pilot = None
    for p in pilots:
        if p["emp_id"] == str(employee_id):
            pilot = p
            break

    if not pilot:
        raise ValueError(f"Employee {employee_id} not found in seniority list")

    my_seniority = pilot["system_seniority"]

    # Group by base (CA only for base position — you're a captain)
    bases = {}
    for p in pilots:
        b = p["base"]
        if b not in bases:
            bases[b] = []
        bases[b].append(p)

    # Compute position at each base
    all_bases = {}
    for base, base_pilots in sorted(bases.items()):
        # Sort by system seniority (ascending = most senior first)
        base_pilots_sorted = sorted(base_pilots, key=lambda p: p["system_seniority"])
        total = len(base_pilots_sorted)

        # Find where this pilot would fall
        position = 1
        for bp in base_pilots_sorted:
            if bp["system_seniority"] >= my_seniority:
                break
            position += 1

        percentile = round((1 - position / total) * 100, 1) if total > 0 else 0

        all_bases[base] = {
            "position": position,
            "total": total,
            "percentile": percentile,
        }

    current_base = pilot["base"]

    return {
        "pilot": pilot,
        "current_base": {
            "base": current_base,
            **all_bases.get(current_base, {}),
        },
        "all_bases": all_bases,
        "system_rank": pilot["rank"],
        "system_seniority": my_seniority,
        "total_pilots": len(pilots),
        "timestamp": datetime.now().isoformat(),
    }


def format_seniority_report(result):
    """Format seniority analysis as readable text."""
    pilot = result["pilot"]
    lines = [
        f"Seniority Report — {pilot['name']} (#{pilot['emp_id']})",
        f"System Rank: {result['system_rank']} of {result['total_pilots']}",
        f"System Seniority #: {result['system_seniority']}",
        f"Hire Date: {pilot['hire_date']}  |  Upgrade: {pilot['upgrade_date']}",
        f"Projected Retirement: {pilot['retirement_date']}",
        "",
        f"Current Base: {result['current_base']['base']} — "
        f"#{result['current_base']['position']} of {result['current_base']['total']} "
        f"(top {100 - result['current_base']['percentile']:.0f}%)",
        "",
        "Position at Each Base:",
        f"  {'Base':>5s}  {'Position':>8s}  {'Total':>6s}  {'Percentile':>10s}",
        f"  {'—'*5}  {'—'*8}  {'—'*6}  {'—'*10}",
    ]

    for base, info in sorted(result["all_bases"].items(),
                              key=lambda x: x[1]["position"]):
        marker = " <<<" if base == pilot["base"] else ""
        lines.append(
            f"  {base:>5s}  {info['position']:>8d}  {info['total']:>6d}  "
            f"  top {100 - info['percentile']:>4.0f}%{marker}"
        )

    # Retirement projections if available
    if result.get("retirement_projections"):
        lines.append("")
        lines.append("Retirement Projections (position improvement as senior pilots retire):")
        lines.append(f"  {'Base':>5s}  {'Now':>5s}  {'6 mo':>5s}  {'1 yr':>5s}  {'2 yr':>5s}  {'Retirements 1yr':>15s}")
        lines.append(f"  {'—'*5}  {'—'*5}  {'—'*5}  {'—'*5}  {'—'*5}  {'—'*15}")
        for base, proj in sorted(result["retirement_projections"].items(),
                                  key=lambda x: x[1]["position_now"]):
            marker = " <<<" if base == pilot["base"] else ""
            lines.append(
                f"  {base:>5s}  {proj['position_now']:>5d}  "
                f"{proj['position_6mo']:>5d}  "
                f"{proj['position_1yr']:>5d}  "
                f"{proj['position_2yr']:>5d}  "
                f"{proj['retirements_1yr']:>15d}{marker}"
            )

    return "\n".join(lines)


def _parse_date(date_str):
    """Parse M/D/YYYY date string to datetime."""
    if not date_str:
        return None
    for fmt in ("%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def compute_retirement_projections(pilots, employee_id):
    """Project seniority position improvement as senior pilots retire.

    For each base, count how many pilots senior to you retire in
    6 months, 1 year, and 2 years. Subtract those from your current
    position to get projected future position.

    Returns dict: {base: {position_now, position_6mo, position_1yr,
                           position_2yr, retirements_6mo, retirements_1yr,
                           retirements_2yr}}
    """
    pilot = None
    for p in pilots:
        if p["emp_id"] == str(employee_id):
            pilot = p
            break
    if not pilot:
        return {}

    my_seniority = pilot["system_seniority"]
    now = datetime.now()
    horizons = {
        "6mo": now + timedelta(days=182),
        "1yr": now + timedelta(days=365),
        "2yr": now + timedelta(days=730),
    }

    # Group by base
    bases = {}
    for p in pilots:
        b = p["base"]
        if b not in bases:
            bases[b] = []
        bases[b].append(p)

    projections = {}
    for base, base_pilots in bases.items():
        # Pilots senior to me at this base
        senior_pilots = [p for p in base_pilots
                         if p["system_seniority"] < my_seniority]
        position_now = len(senior_pilots) + 1

        retirements = {"6mo": 0, "1yr": 0, "2yr": 0}
        for sp in senior_pilots:
            ret_date = _parse_date(sp["retirement_date"])
            if not ret_date:
                continue
            for key, horizon in horizons.items():
                if ret_date <= horizon:
                    retirements[key] += 1

        projections[base] = {
            "position_now": position_now,
            "position_6mo": position_now - retirements["6mo"],
            "position_1yr": position_now - retirements["1yr"],
            "position_2yr": position_now - retirements["2yr"],
            "retirements_6mo": retirements["6mo"],
            "retirements_1yr": retirements["1yr"],
            "retirements_2yr": retirements["2yr"],
            "total": len(base_pilots),
        }

    return projections


def save_snapshot_to_db(result):
    """Store seniority snapshot in the PilotLog database."""
    import asyncio
    from pilotlog.config import settings
    from pilotlog.database.connection import init_db, get_session
    from pilotlog.database.models import SenioritySnapshot

    async def _save():
        settings.ensure_directories()
        await init_db()
        async with get_session() as session:
            now = datetime.now()
            emp_id = result["pilot"]["emp_id"]

            # Store a row per base
            for base, info in result["all_bases"].items():
                snapshot = SenioritySnapshot(
                    captured_at=now,
                    employee_id=emp_id,
                    system_seniority=result["system_seniority"],
                    base=base,
                    base_position=info["position"],
                    base_total=info["total"],
                )
                session.add(snapshot)
            await session.commit()
            logger.info(f"Saved {len(result['all_bases'])} seniority snapshots to DB")

    asyncio.run(_save())


def get_seniority_history(employee_id=None, base=None, limit=52):
    """Query seniority history from the DB.

    Returns list of snapshots, newest first. Useful for trend charts.
    """
    import asyncio
    from sqlalchemy import select
    from pilotlog.config import settings
    from pilotlog.database.connection import init_db, get_session
    from pilotlog.database.models import SenioritySnapshot

    async def _query():
        settings.ensure_directories()
        await init_db()
        async with get_session() as session:
            query = select(SenioritySnapshot)
            if employee_id:
                query = query.where(SenioritySnapshot.employee_id == str(employee_id))
            if base:
                query = query.where(SenioritySnapshot.base == base)
            query = query.order_by(SenioritySnapshot.captured_at.desc()).limit(limit)
            result = await session.execute(query)
            rows = result.scalars().all()
            return [{
                "captured_at": r.captured_at.isoformat(),
                "base": r.base,
                "position": r.base_position,
                "total": r.base_total,
                "system_seniority": r.system_seniority,
            } for r in rows]

    return asyncio.run(_query())
