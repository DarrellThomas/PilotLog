"""AI-assisted bid analyzer — parse bid packages, score lines, rank by preference.

Parses SWA CWA bid package files:
  HOUCPL.TXT — Line package (all bid lines with TFP, TAFB, block, days off, pairings)
  HOUCPP.TXT — Pairing details (every trip: legs, flights, times, layovers, credit)
  HOUCPS.TXT — Seniority bid list (bid order, planned absences, medical flags)
  HOUCPM.TXT — Monthly bid award list (who got what line)
  HOUCPC.TXT — Cover memo (SAQ airports, ELITT restrictions)

Two-tier system:
  Round 1 (Hardline): bid on published lines, awarded by seniority
  Round 2 (Blank line): if no hardline, get a rebuilt line from pulls

Timeline (CBA Section 9):
  4th: bids posted | 9th: close | 10th: awards | 17th: blank lines | 19th: blank awards
"""

import json
import logging
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from zipfile import ZipFile

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent / "data" / "bid_packages"

# Preferred overnight destinations (from user preferences)
PREFERRED_DESTINATIONS = {
    'SJO', 'SAN', 'LIR', 'RNO', 'SJC', 'SAC', 'LAX', 'LGB',
    'FLL', 'LAS', 'ELP', 'DEN', 'BOI',
}


# ============================================================
# Data classes
# ============================================================

@dataclass
class Pairing:
    """A single trip/pairing from the pairing file."""
    id: str                          # e.g. "HA2X"
    dow: list                        # day-of-week codes: ["MO", "TH", "FR"]
    report: str                      # report time: "10:15"
    credit: str                      # trip credit TFP: "13.58" or "19.50A" (A=ADG)
    credit_value: float = 0          # parsed numeric credit
    blk: str = ""                    # block hours: "11:30"
    blk_minutes: int = 0
    legs: int = 0
    tafb: str = ""                   # time away from base: "29:05"
    tafb_minutes: int = 0
    trip_days: int = 1               # multi-day count
    effective: str = ""              # effective dates
    routing: list = field(default_factory=list)   # station list
    overnights: list = field(default_factory=list) # overnight stations
    is_deadhead_only: bool = False
    legs_per_day: float = 0

    def __post_init__(self):
        # Parse credit value
        m = re.match(r'([\d.]+)', self.credit)
        if m:
            self.credit_value = float(m.group(1))
        # Parse block minutes
        if ':' in self.blk:
            parts = self.blk.split(':')
            self.blk_minutes = int(parts[0]) * 60 + int(parts[1])
        # Parse TAFB minutes
        if ':' in self.tafb:
            parts = self.tafb.split(':')
            self.tafb_minutes = int(parts[0]) * 60 + int(parts[1])
        # Legs per day
        self.legs_per_day = round(self.legs / max(self.trip_days, 1), 1)


@dataclass
class BidLine:
    """A single bid line from the line package."""
    number: int
    tfp: float
    tafb: str = ""
    tafb_minutes: int = 0
    off_days: int = 0
    blk: str = ""
    blk_minutes: int = 0
    num_dps: int = 0
    pairing_ids: list = field(default_factory=list)
    co_tfp: float = 0               # carryover TFP
    calendar: str = ""              # raw calendar line
    pairings: list = field(default_factory=list)  # resolved Pairing objects

    # Computed scores
    avg_legs_per_day: float = 0
    avg_report_hour: float = 0
    preferred_dest_count: int = 0
    overnight_stations: set = field(default_factory=set)
    score: float = 0
    rank: int = 0


@dataclass
class BidderInfo:
    """A pilot from the seniority bid list."""
    sq: int                          # sequence number (bid order)
    emp_id: str
    name: str
    is_paper: bool = False           # P = paper bid (medical, line returns to pool)
    planned_absences: list = field(default_factory=list)  # VA, MD, QT, etc.


@dataclass
class AwardEntry:
    """A line award from the award list."""
    sq: int
    sr: int                          # system seniority
    is_paper: bool
    emp_id: str
    name: str
    line: int


# ============================================================
# Parsers
# ============================================================

def parse_pairings(text):
    """Parse HOUCPP.TXT pairing file into dict of Pairing objects."""
    headers = list(re.finditer(
        r'^(H\w{2,3})\s+((?:MO|TU|WE|TH|FR|SA|SU)[\s\w]*?)\s+PILOTS\s+REPORT AT\s+([\d:]+)\s+EFFECTIVE\s+(.+?)$',
        text, re.MULTILINE
    ))

    pairings = {}
    for i, m in enumerate(headers):
        pid = m.group(1)
        days = m.group(2).strip().split()
        report = m.group(3)
        effective = m.group(4).strip()

        start = m.start()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        block = text[start:end]

        credit_m = re.search(
            r'Trip Credit\s+([\d.]+\w?)\s+BLK HRS\s+([\d:]+)\s+No\.\s+Legs\s+(\d+)\s+TAFB\s+([\d:]+)',
            block
        )
        if not credit_m:
            continue

        # Count trip days from day-number lines
        day_nums = set(re.findall(r'^\s+(\d)\s+', block, re.MULTILINE))
        trip_days = max(len(day_nums), 1)

        # Extract routing (origin-dest pairs from leg lines)
        leg_matches = re.findall(
            r'^\s+\d\s+(?:DH\s+)?\s*\d+\s+\d{3}\s+(\w{3})\s+\d+\s+(\w{3})',
            block, re.MULTILINE
        )
        routing = []
        for orig, dest in leg_matches:
            if not routing or routing[-1] != orig:
                routing.append(orig)
            routing.append(dest)
        # Dedupe consecutive
        clean_route = []
        for r in routing:
            if not clean_route or clean_route[-1] != r:
                clean_route.append(r)

        # Overnight stations (non-base stations between days)
        overnights = []
        layover_matches = re.findall(r'LAYOVER\s+(.+?)$', block, re.MULTILINE)
        # Also infer from routing: stations that aren't HOU between days
        if trip_days > 1 and clean_route:
            for station in clean_route[1:-1]:
                if station != 'HOU' and station not in overnights:
                    overnights.append(station)

        pairings[pid] = Pairing(
            id=pid, dow=days, report=report,
            credit=credit_m.group(1), blk=credit_m.group(2),
            legs=int(credit_m.group(3)), tafb=credit_m.group(4),
            trip_days=trip_days, effective=effective,
            routing=clean_route, overnights=overnights,
        )

    return pairings


def parse_lines(text, pairings=None):
    """Parse HOUCPL.TXT line package into list of BidLine objects."""
    line_pattern = re.compile(
        r'^Line\s+(\d+)\s+TFP\s+([\d.]+)\s+(.+?)$',
        re.MULTILINE
    )

    lines = []
    matches = list(line_pattern.finditer(text))

    for i, m in enumerate(matches):
        line_num = int(m.group(1))
        tfp = float(m.group(2))

        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        chunk = text[start:end]

        tafb_m = re.search(r'TAFB\s+([\d:]+)', chunk)
        off_m = re.search(r'^OFF\s+(\d+)\s+BLK\s+([\d:]+)', chunk, re.MULTILINE)
        dp_m = re.search(r'No\.\s+DPs\s+(\d+)', chunk)
        co_m = re.search(r'C/O TFP\s+([\d.]+)', chunk)

        tafb_str = tafb_m.group(1) if tafb_m else "0:00"
        off_days = int(off_m.group(1)) if off_m else 0
        blk_str = off_m.group(2) if off_m else "0:00"
        num_dps = int(dp_m.group(1)) if dp_m else 0
        co_tfp = float(co_m.group(1)) if co_m else 0

        # Parse TAFB minutes
        tafb_min = 0
        if ':' in tafb_str:
            parts = tafb_str.split(':')
            tafb_min = int(parts[0]) * 60 + int(parts[1])

        # Parse block minutes
        blk_min = 0
        if ':' in blk_str:
            parts = blk_str.split(':')
            blk_min = int(parts[0]) * 60 + int(parts[1])

        # Extract pairing IDs from the C/O line
        pairing_ids = re.findall(r'([A-Z]\w{2,3})=\d{4}', chunk)
        # Add base prefix if needed
        pairing_ids = [f'H{pid}' if not pid.startswith('H') else pid for pid in pairing_ids]

        line = BidLine(
            number=line_num, tfp=tfp, tafb=tafb_str, tafb_minutes=tafb_min,
            off_days=off_days, blk=blk_str, blk_minutes=blk_min,
            num_dps=num_dps, pairing_ids=pairing_ids, co_tfp=co_tfp,
        )

        # Resolve pairings if available
        if pairings:
            for pid in pairing_ids:
                p = pairings.get(pid)
                if p:
                    line.pairings.append(p)

            # Compute line-level pairing stats
            if line.pairings:
                total_legs = sum(p.legs for p in line.pairings)
                total_trip_days = sum(p.trip_days for p in line.pairings)
                line.avg_legs_per_day = round(total_legs / max(total_trip_days, 1), 1)

                reports = []
                for p in line.pairings:
                    try:
                        parts = p.report.split(':')
                        reports.append(int(parts[0]) + int(parts[1]) / 60)
                    except (ValueError, IndexError):
                        pass
                if reports:
                    line.avg_report_hour = round(sum(reports) / len(reports), 1)

                # Overnight destinations
                for p in line.pairings:
                    for stn in p.overnights:
                        line.overnight_stations.add(stn)
                    # Also check routing for preferred destinations
                    for stn in p.routing:
                        if stn in PREFERRED_DESTINATIONS:
                            line.preferred_dest_count += 1

        lines.append(line)

    return lines


def parse_seniority(text):
    """Parse HOUCPS.TXT seniority bid list."""
    bidders = []
    current = None

    for line in text.split('\n'):
        # Match SQ# line: starts with number, has employee ID
        m = re.match(r'^\s*(\d+)\s+.*?(\d{5,6})\s+(.+?)$', line)
        if m:
            if current:
                bidders.append(current)
            sq = int(m.group(1))
            emp_id = m.group(2)
            name = m.group(3).strip()
            is_paper = bool(re.search(r'\bP\b', line[:35]))
            current = BidderInfo(sq=sq, emp_id=emp_id, name=name, is_paper=is_paper)
        elif current and line.strip():
            # Absence lines: VA, MD, QT with date ranges
            absence_m = re.search(r'(VA|MD|QT|TR|ML|UN)\s+(\d+\w+-\d+\w+)', line)
            if absence_m:
                current.planned_absences.append({
                    'type': absence_m.group(1),
                    'range': absence_m.group(2),
                })

    if current:
        bidders.append(current)
    return bidders


def parse_awards(text):
    """Parse HOUCPM.TXT award list."""
    awards = []
    # Format: SQ# SR# T EBG Name Id# Line LT
    pattern = re.compile(r'(\d+)\s+(\d+)\s*(P?)\s*\S*\s+(\S+.*?)\s+(\d{5,6})\s+(\d+)')
    for m in pattern.finditer(text):
        awards.append(AwardEntry(
            sq=int(m.group(1)), sr=int(m.group(2)),
            is_paper=m.group(3) == 'P',
            name=m.group(4).strip(), emp_id=m.group(5),
            line=int(m.group(6)),
        ))
    return awards


# ============================================================
# Scoring Engine
# ============================================================

DEFAULT_WEIGHTS = {
    'days_off': 30,
    'trip_quality': 25,
    'pay': 15,
    'overnight_quality': 15,
    'report_time': 10,
    'days_off_pattern': 5,
}


def score_line(line, weights=None, preferences=None):
    """Score a bid line on a 0-100 scale based on weighted preferences.

    Args:
        line: BidLine object with resolved pairings
        weights: dict of category weights (must sum to 100)
        preferences: dict of specific preferences:
            min_days_off: int (minimum acceptable days off)
            max_legs_per_day: float (max tolerable)
            preferred_destinations: set of station codes
            min_report_hour: float (earliest acceptable, e.g. 6.0 = 0600)
            avoid_weekday_off: bool (prefer weekends off)

    Returns:
        score (0-100), breakdown dict
    """
    w = weights or DEFAULT_WEIGHTS
    prefs = preferences or {}

    # --- DAYS OFF (0-30) ---
    min_off = prefs.get('min_days_off', 17)
    if line.off_days >= 20:
        days_score = 30
    elif line.off_days >= 19:
        days_score = 27
    elif line.off_days >= 18:
        days_score = 23
    elif line.off_days >= 17:
        days_score = 18
    elif line.off_days >= 16:
        days_score = 12
    else:
        days_score = 5
    days_score = days_score * w['days_off'] / 30

    # --- TRIP QUALITY (0-25) ---
    # Lower legs per day = better
    lpd = line.avg_legs_per_day
    if lpd <= 2.0:
        quality_score = 25
    elif lpd <= 2.5:
        quality_score = 22
    elif lpd <= 3.0:
        quality_score = 18
    elif lpd <= 3.5:
        quality_score = 14
    elif lpd <= 4.0:
        quality_score = 10
    elif lpd <= 5.0:
        quality_score = 5
    else:
        quality_score = 1
    quality_score = quality_score * w['trip_quality'] / 25

    # --- PAY (0-15) ---
    # Normalize TFP: 89-113 range mapped to 0-15
    tfp_norm = max(0, min(1, (line.tfp - 89) / (113 - 89)))
    pay_score = tfp_norm * w['pay']

    # --- OVERNIGHT QUALITY (0-15) ---
    on_score = 0
    if line.pairings:
        # TAFB per pairing (longer = more overnight time)
        avg_tafb_hrs = line.tafb_minutes / max(line.num_dps, 1) / 60
        if avg_tafb_hrs >= 20:
            on_score = 12
        elif avg_tafb_hrs >= 16:
            on_score = 10
        elif avg_tafb_hrs >= 12:
            on_score = 7
        else:
            on_score = 3

        # Bonus for preferred destinations
        if line.preferred_dest_count >= 3:
            on_score = min(15, on_score + 3)
        elif line.preferred_dest_count >= 1:
            on_score = min(15, on_score + 1)
    on_score = on_score * w['overnight_quality'] / 15

    # --- REPORT TIME (0-10) ---
    rpt = line.avg_report_hour
    if rpt >= 10:
        rpt_score = 10
    elif rpt >= 8:
        rpt_score = 8
    elif rpt >= 6:
        rpt_score = 5
    elif rpt >= 5:
        rpt_score = 3
    else:
        rpt_score = 1
    rpt_score = rpt_score * w['report_time'] / 10

    # --- DAYS OFF PATTERN (0-5) ---
    # More DPs with fewer off days = scattered; fewer DPs = more consecutive blocks
    dp_ratio = line.num_dps / max(31 - line.off_days, 1)
    if dp_ratio <= 0.8:
        pattern_score = 5   # multi-day trips = big blocks of consecutive off
    elif dp_ratio <= 1.0:
        pattern_score = 3
    else:
        pattern_score = 1   # lots of single-day turns = scattered days off
    pattern_score = pattern_score * w['days_off_pattern'] / 5

    total = round(days_score + quality_score + pay_score + on_score + rpt_score + pattern_score, 1)
    total = max(0, min(100, total))

    breakdown = {
        'days_off': round(days_score, 1),
        'trip_quality': round(quality_score, 1),
        'pay': round(pay_score, 1),
        'overnight': round(on_score, 1),
        'report_time': round(rpt_score, 1),
        'pattern': round(pattern_score, 1),
    }

    return total, breakdown


def score_all_lines(lines, weights=None, preferences=None):
    """Score and rank all lines. Returns sorted list (best first)."""
    for line in lines:
        line.score, _ = score_line(line, weights, preferences)

    ranked = sorted(lines, key=lambda l: -l.score)
    for i, line in enumerate(ranked):
        line.rank = i + 1

    return ranked


# ============================================================
# Bid Package Loader
# ============================================================

def load_bid_package(zip_path=None, txt_dir=None, base="HOU", seat="CA"):
    """Load and parse a complete bid package.

    Args:
        zip_path: path to ZIP file (e.g., HOUCPA.ZIP)
        txt_dir: path to directory with extracted TXT files
        base: base code (default HOU)
        seat: seat code (default CA)

    Returns:
        dict with 'lines', 'pairings', 'bidders', 'cover', 'metadata'
    """
    # File naming: HOUCPL.TXT = HOU + CP (Captain) + L (Lines)
    # Prefix is BASE + "CP" for Captain, "FP" for FO
    seat_code = "CP" if seat == "CA" else "FP"
    prefix = f"{base}{seat_code}"  # e.g., "HOUCP"

    if zip_path:
        zip_path = Path(zip_path)
        txt_dir = Path(f"/tmp/bid_package_{base}_{seat}")
        txt_dir.mkdir(parents=True, exist_ok=True)
        with ZipFile(zip_path) as zf:
            zf.extractall(txt_dir)

    txt_dir = Path(txt_dir)
    files = {f.stem.upper(): f for f in txt_dir.glob("*.TXT")}

    result = {'metadata': {'base': base, 'seat': seat, 'loaded_at': datetime.now().isoformat()}}

    # Parse pairings first (needed for line resolution)
    pp_key = f"{prefix}P"
    if pp_key in files:
        with open(files[pp_key], encoding='utf-8', errors='replace') as f:
            result['pairings'] = parse_pairings(f.read())
        result['metadata']['pairing_count'] = len(result['pairings'])
    else:
        result['pairings'] = {}

    # Parse lines
    pl_key = f"{prefix}L"
    if pl_key in files:
        with open(files[pl_key], encoding='utf-8', errors='replace') as f:
            result['lines'] = parse_lines(f.read(), result['pairings'])
        result['metadata']['line_count'] = len(result['lines'])

    # Parse seniority
    ps_key = f"{prefix}S"
    if ps_key in files:
        with open(files[ps_key], encoding='utf-8', errors='replace') as f:
            result['bidders'] = parse_seniority(f.read())
        result['metadata']['bidder_count'] = len(result['bidders'])
        result['metadata']['paper_count'] = sum(1 for b in result['bidders'] if b.is_paper)

    # Parse cover memo
    pc_key = f"{prefix}C"
    if pc_key in files:
        with open(files[pc_key], encoding='utf-8', errors='replace') as f:
            result['cover'] = f.read()

    return result


def load_awards(zip_path=None, txt_path=None, base="HOU", seat="CA"):
    """Load and parse award list."""
    seat_code = "CP" if seat == "CA" else "FP"
    prefix = f"{base}{seat_code}"

    if zip_path:
        zip_path = Path(zip_path)
        txt_dir = Path(f"/tmp/bid_awards_{base}_{seat}")
        txt_dir.mkdir(parents=True, exist_ok=True)
        with ZipFile(zip_path) as zf:
            zf.extractall(txt_dir)
        txt_path = txt_dir / f"{prefix}M.TXT"

    if txt_path:
        with open(txt_path, encoding='utf-8', errors='replace') as f:
            return parse_awards(f.read())
    return []


def compute_effective_seniority(bidders, employee_id):
    """Compute effective seniority after removing paper-bid pilots."""
    my_sq = None
    paper_above = 0
    total_paper = 0

    for b in bidders:
        if b.emp_id == str(employee_id):
            my_sq = b.sq
        if b.is_paper:
            total_paper += 1
            if my_sq is None:  # haven't found us yet, so this is above us
                paper_above += 1

    if my_sq is None:
        return None

    return {
        'sq': my_sq,
        'effective_sq': my_sq - paper_above,
        'paper_above': paper_above,
        'total_paper': total_paper,
        'total_bidders': len(bidders),
        'active_bidders': len(bidders) - total_paper,
    }


def available_lines(lines, awards, my_sq):
    """Determine which lines are available at a given seniority position."""
    # Lines taken by non-paper pilots senior to me
    taken = set()
    for a in awards:
        if a.sq < my_sq and not a.is_paper:
            taken.add(a.line)

    return [l for l in lines if l.number not in taken]


# ============================================================
# Report Formatting
# ============================================================

def format_bid_report(ranked_lines, top_n=25, effective_sen=None):
    """Format ranked lines as a readable bid recommendation."""
    lines = [
        "BID RECOMMENDATION — Ranked by Quality Score",
        f"{'='*75}",
    ]

    if effective_sen:
        lines.append(
            f"Effective seniority: #{effective_sen['effective_sq']} "
            f"(#{effective_sen['sq']} system, {effective_sen['paper_above']} paper bids above)"
        )
        lines.append(
            f"Active bidders: {effective_sen['active_bidders']} "
            f"(of {effective_sen['total_bidders']} total)"
        )
        lines.append("")

    lines.append(
        f"{'Rank':>4s} {'Line':>4s} {'Score':>5s} | "
        f"{'TFP':>6s} {'Off':>3s} {'DPs':>3s} {'Lg/d':>4s} "
        f"{'Rpt':>5s} | {'Days':>4s} {'Qual':>4s} {'Pay':>4s} "
        f"{'Ovnt':>4s} {'Rpt':>4s} {'Pat':>3s}"
    )
    lines.append(f"{'—'*4} {'—'*4} {'—'*5} | {'—'*6} {'—'*3} {'—'*3} {'—'*4} {'—'*5} | "
                 f"{'—'*4} {'—'*4} {'—'*4} {'—'*4} {'—'*4} {'—'*3}")

    for line in ranked_lines[:top_n]:
        _, bd = score_line(line)
        rpt_str = f"{line.avg_report_hour:.0f}:00" if line.avg_report_hour else "?"
        dest_tag = ""
        if line.overnight_stations & PREFERRED_DESTINATIONS:
            hits = line.overnight_stations & PREFERRED_DESTINATIONS
            dest_tag = f" [{','.join(sorted(hits))}]"

        lines.append(
            f"{line.rank:>4d} {line.number:>4d} {line.score:>5.1f} | "
            f"{line.tfp:>6.1f} {line.off_days:>3d} {line.num_dps:>3d} {line.avg_legs_per_day:>4.1f} "
            f"{rpt_str:>5s} | {bd['days_off']:>4.1f} {bd['trip_quality']:>4.1f} {bd['pay']:>4.1f} "
            f"{bd['overnight']:>4.1f} {bd['report_time']:>4.1f} {bd['pattern']:>3.1f}"
            f"{dest_tag}"
        )

    return "\n".join(lines)


def save_bid_package(package, period, base="HOU"):
    """Archive a parsed bid package for historical tracking."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    outfile = DATA_DIR / f"{base}_{period}.json"

    # Convert to serializable format
    data = {
        'metadata': package['metadata'],
        'period': period,
        'line_count': len(package.get('lines', [])),
        'pairing_count': len(package.get('pairings', {})),
        'lines_summary': [
            {
                'number': l.number, 'tfp': l.tfp, 'off': l.off_days,
                'dps': l.num_dps, 'blk': l.blk, 'tafb': l.tafb,
                'avg_lpd': l.avg_legs_per_day, 'avg_rpt': l.avg_report_hour,
                'score': l.score,
            }
            for l in package.get('lines', [])
        ],
    }

    with open(outfile, 'w') as f:
        json.dump(data, f, indent=2, default=str)
    logger.info(f"Saved bid package to {outfile}")
    return outfile
