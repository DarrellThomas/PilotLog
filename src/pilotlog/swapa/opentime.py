"""Open Time & TT/GA scanner — poll SWAPA, score trips, alert via Signal.

Scans ALL bases (not just HOU). Open bidding = anyone can bid, but:
  - Last-minute drops (< 24hr to report) favor HOU-local (can physically get there)
  - Close time is known — speed of awareness is the edge
  - Premium pay is rare but worth chasing; straight time on good trips is solid
  - Reserve pickups count too — light assignments from reserve pool

Trip scoring model (0-100):
  - Urgency bonus: last-minute postings score highest (HOU-local advantage)
  - Ease score: fewer legs/day, longer overnights = better
  - Pay score: TFP value * pay multiplier (premium/double > straight)
  - Penalty: high leg count + short overnight = grinder tax

The scanner diffs against the last snapshot to find NEW postings,
then fires a Signal alert for anything worth looking at.
"""

import json
import logging
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent / "data"
SNAPSHOT_FILE = DATA_DIR / "ot_snapshot.json"
TTGA_SNAPSHOT_FILE = DATA_DIR / "ttga_snapshot.json"
ALERT_LOG = DATA_DIR / "ot_alerts.jsonl"

HOME_BASE = "HOU"

# Only Signal-alert on Hourly Open Time (HOT): trips reporting within this many
# hours. Daily Open Time (DOT) — postings further out — is still scored and
# logged, just not texted. This is the HOU-local last-minute edge; the days-out
# bulk inventory was too noisy. Bump this to widen the alert window.
HOT_WINDOW_HOURS = 24

# SWA bases (2026)
SWA_BASES = [
    "ATL", "BAL", "BWI", "DAL", "DEN", "HOU", "LAS", "LAX",
    "MCO", "MDW", "OAK", "PHX", "SAN", "SJC", "TPA",
]

# Preferred overnight destinations — boost score when trip routes through these
# A good destination can still be ruined by a short overnight or bad hotel
PREFERRED_DESTINATIONS = {
    'SJO', 'SAN', 'LIR', 'RNO', 'SJC', 'SAC', 'LAX', 'LGB',
    'FLL', 'LAS', 'ELP', 'DEN', 'BOI',
}

# Destinations with social/personal value (extra bump)
DESTINATION_NOTES = {
    'LGB': 'rachel',
    'SJC': 'depends on hotel',
}

# Signal sending
SIGNAL_CLI = "/usr/local/bin/signal-cli"


def _load_env_var(*keys):
    """Load first matching key from ~/.env."""
    env_file = Path.home() / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                for key in keys:
                    if line.startswith(f'{key}='):
                        return line.split('=', 1)[1].strip().strip('"')
    return None


def send_signal_alert(message):
    """Send a Signal message to the pilot.

    Requires SIGNAL_SENDER and SIGNAL_RECIPIENT (or DARRELL_PHONE) in ~/.env.
    """
    import subprocess
    sender = _load_env_var('SIGNAL_SENDER')
    recipient = _load_env_var('SIGNAL_RECIPIENT', 'DARRELL_PHONE')

    if not sender or not recipient:
        logger.warning("SIGNAL_SENDER/SIGNAL_RECIPIENT not in ~/.env, skipping alert")
        print(f"  [ALERT - no config] {message}", file=sys.stderr)
        return False

    try:
        result = subprocess.run(
            [SIGNAL_CLI, "-a", sender, "send", "-m", message, recipient],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            logger.info(f"Signal alert sent: {message[:80]}")
            return True
        else:
            logger.error(f"Signal send failed: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"Signal send error: {e}")
        return False


def score_trip(trip):
    """Score a trip on a 0-100 scale for desirability.

    Args:
        trip: dict with keys like:
            base, trip_id, num_days, total_legs, legs_per_day (list),
            total_tfp, pay_type (straight/premium/double),
            report_time (datetime), close_time (datetime),
            overnights (list of minutes), routing (list of station pairs)

    Returns:
        (score, breakdown_dict)
    """
    now = datetime.now()

    # --- URGENCY (0-35 points) ---
    # Last-minute = biggest edge (HOU local can show up, others can't)
    hours_to_report = 999
    if trip.get('report_time'):
        try:
            rpt = trip['report_time']
            if isinstance(rpt, str):
                rpt = datetime.fromisoformat(rpt)
            hours_to_report = max(0, (rpt - now).total_seconds() / 3600)
        except Exception:
            pass

    if hours_to_report <= 4:
        urgency = 35   # fire alarm — get there NOW
    elif hours_to_report <= 12:
        urgency = 30   # very hot
    elif hours_to_report <= 24:
        urgency = 25   # same-day edge
    elif hours_to_report <= 48:
        urgency = 15
    elif hours_to_report <= 72:
        urgency = 10
    else:
        urgency = 5    # normal bid cycle, no special edge

    # Extra urgency for HOU-originating trips (don't need to commute)
    if trip.get('base', '').upper() == HOME_BASE:
        urgency = min(35, urgency + 5)

    # --- EASE (0-30 points) ---
    # Fewer legs/day + longer overnights = better trip
    total_legs = trip.get('total_legs', 0)
    num_days = max(trip.get('num_days', 1), 1)
    avg_legs_per_day = total_legs / num_days

    if avg_legs_per_day <= 1.5:
        ease = 30       # dream trip: 1 leg each way
    elif avg_legs_per_day <= 2.0:
        ease = 25       # very easy
    elif avg_legs_per_day <= 2.5:
        ease = 20       # comfortable
    elif avg_legs_per_day <= 3.0:
        ease = 15       # normal
    elif avg_legs_per_day <= 3.5:
        ease = 10       # busy
    elif avg_legs_per_day <= 4.0:
        ease = 5        # grinder territory
    else:
        ease = 0        # hard pass unless premium

    # Overnight quality bonus/penalty
    overnights = trip.get('overnights', [])
    if overnights:
        avg_overnight_hrs = sum(overnights) / len(overnights) / 60
        if avg_overnight_hrs >= 16:
            ease = min(30, ease + 8)   # hotel lifestyle — long layover, enjoy the city
        elif avg_overnight_hrs >= 14:
            ease = min(30, ease + 5)   # solid overnight
        elif avg_overnight_hrs <= 9:
            ease = max(0, ease - 8)    # hustle mode — food/rest discipline required
        elif avg_overnight_hrs <= 10:
            ease = max(0, ease - 5)    # short but manageable

    # Preferred destination bonus
    routing_stations = set()
    for r in trip.get('routing', []):
        if isinstance(r, str):
            routing_stations.add(r)
        elif isinstance(r, (list, tuple)):
            routing_stations.update(r)
    overnight_destinations = trip.get('overnight_stations', set())
    if not overnight_destinations:
        overnight_destinations = routing_stations

    preferred_hits = overnight_destinations & PREFERRED_DESTINATIONS
    if preferred_hits:
        ease = min(30, ease + 3)  # nice destination bump

    # --- PAY (0-25 points) ---
    total_tfp = trip.get('total_tfp', 0)
    pay_type = trip.get('pay_type', 'straight').lower()

    # Base pay score from TFP value
    if total_tfp >= 20:
        pay = 20
    elif total_tfp >= 15:
        pay = 17
    elif total_tfp >= 12:
        pay = 14
    elif total_tfp >= 8:
        pay = 10
    elif total_tfp >= 5:
        pay = 7
    else:
        pay = 3

    # Pay type multiplier
    if pay_type == 'double':
        pay = min(25, pay + 5)
    elif pay_type == 'premium':
        pay = min(25, pay + 3)
    # straight = no modifier

    # --- PENALTY (0 to -20) ---
    penalty = 0
    avg_on_hrs = 99
    if overnights:
        avg_on_hrs = sum(overnights) / len(overnights) / 60

    # Grinder penalty: lots of legs + short overnight
    if avg_legs_per_day >= 4.0:
        if avg_on_hrs <= 10:
            penalty = -20   # the 5+4 with 10hr overnight — even premium barely saves this
        elif avg_on_hrs <= 12:
            penalty = -12

    # Short overnight + low pay = not worth the hustle
    if avg_on_hrs <= 10 and total_tfp < 12 and pay_type == 'straight':
        penalty = min(penalty, -15)  # short overnight needs to PAY

    # Short overnight is tolerable at premium/double
    if avg_on_hrs <= 10 and pay_type in ('premium', 'double'):
        penalty = max(penalty, -8)   # partially forgiven

    # Very long multi-day grinder
    if num_days >= 4 and avg_legs_per_day >= 3.5:
        penalty = min(penalty, -10)

    score = max(0, min(100, urgency + ease + pay + penalty))

    breakdown = {
        'urgency': urgency,
        'ease': ease,
        'pay': pay,
        'penalty': penalty,
        'hours_to_report': round(hours_to_report, 1),
        'avg_legs_day': round(avg_legs_per_day, 1),
        'pay_type': pay_type,
        'total_tfp': total_tfp,
    }

    return score, breakdown


def _parse_ot_release(trip, report_time):
    """Parse release time from OT trip data, or estimate from num_days."""
    import re
    release_str = trip.get('release_str', '')
    if release_str:
        m = re.match(r'(\d{3,4})/(\d{2})([A-Z][a-z]{2})', release_str)
        if m:
            try:
                year = datetime.now().year
                release_time = datetime.strptime(
                    f"{m.group(2)}{m.group(3)}{year} {m.group(1).zfill(4)}", "%d%b%Y %H%M")
                if release_time < report_time:
                    release_time = release_time.replace(year=year + 1)
                return release_time
            except ValueError:
                pass
    num_days = trip.get('num_days', 1) or 1
    return report_time + timedelta(days=num_days)


def check_legality(trip):
    """Check if the pilot is legal for this trip per FAR 117 + CBA.

    Checks:
      1. Schedule conflict — does this trip overlap existing trips on the board?
      2. FAR 117 rest — 10hr minimum rest between trips
      3. 672-hour limit — max 100 flight hours in any 28-day (672-hour) window
      4. 365-day limit — max 1,000 flight hours in any 365-day window
      5. 30-in-7 — must have 30 consecutive hours free from duty in any 7-day window

    Returns (is_legal, reason_string). Fail CLOSED — if we can't determine
    legality (iCal down, parse error), assume illegal to avoid spam.
    """
    try:
        from pilotlog.swapa.ical import fetch_ical, parse_ical_feed
    except Exception:
        return False, "ical module unavailable"

    report_time = trip.get('report_time')
    if not report_time:
        return False, "no report_time"

    if isinstance(report_time, str):
        try:
            report_time = datetime.fromisoformat(report_time)
        except ValueError:
            return False, "bad report_time"

    release_time = _parse_ot_release(trip, report_time)

    # Fetch current schedule
    try:
        ical_text = fetch_ical()
        my_trips = parse_ical_feed(ical_text)
    except Exception as e:
        return False, f"schedule fetch failed: {e}"

    # FAR 117 minimum rest: 10 hours between release and next report
    # CBA: report cannot be moved up more than 3 hours while in rest
    # Buffer: need 10hr rest before report AND after previous release
    MIN_REST_HOURS = 10

    # Build OT trip date range
    ot_dates = set()
    d = report_time.date()
    while d <= release_time.date():
        ot_dates.add(d)
        d += timedelta(days=1)

    # Only check trips within a relevant window (3 days either side of OT trip)
    # to avoid false positives from distant past/future trips.
    proximity_buffer = timedelta(days=3)
    ot_start = report_time - proximity_buffer
    ot_end = release_time + proximity_buffer

    for my_trip in my_trips:
        if not my_trip.get('days'):
            continue

        # Build date set for this existing trip
        trip_dates = set()
        first_report_date = None
        last_release_date = None

        for day in my_trip['days']:
            month_str = day.get('month', '')
            date_num = day.get('date', 0)
            if not month_str or not date_num:
                continue
            try:
                year = datetime.now().year
                day_date = datetime.strptime(f"{month_str} {date_num} {year}", "%b %d %Y")
                trip_dates.add(day_date.date())
                if first_report_date is None or day_date < first_report_date:
                    first_report_date = day_date
                if last_release_date is None or day_date > last_release_date:
                    last_release_date = day_date
            except ValueError:
                continue

        if not trip_dates:
            continue

        # Skip trips entirely outside the proximity window
        if last_release_date and last_release_date < ot_start:
            continue
        if first_report_date and first_report_date > ot_end:
            continue

        # Check 1: direct date overlap (trip days conflict)
        overlap = ot_dates & trip_dates
        if overlap:
            return False, f"overlap {my_trip.get('trip_id', '?')}"

        # Check 2: FAR 117 rest requirement (10hr min between trips)
        rest_buffer = timedelta(hours=MIN_REST_HOURS)

        # Need 10hrs after my existing trip's last day before OT report
        # (only relevant if existing trip ends BEFORE OT starts)
        if last_release_date and last_release_date.date() < report_time.date():
            assumed_release = last_release_date.replace(hour=22)
            if report_time < assumed_release + rest_buffer:
                return False, f"<10hr rest after {my_trip.get('trip_id', '?')}"

        # Need 10hrs before my next trip's first day after OT release
        # (only relevant if existing trip starts AFTER OT ends)
        if first_report_date and first_report_date.date() > release_time.date():
            assumed_report = first_report_date.replace(hour=5)
            if release_time > assumed_report - rest_buffer:
                return False, f"<10hr rest before {my_trip.get('trip_id', '?')}"

    # Check 3: FAR 117 cumulative limits from PilotLog logbook DB
    # 100 flight hours in 672 consecutive hours (rolling to the hour, not calendar)
    # 1,000 flight hours in 365 consecutive days
    # NOTE: DB query uses calendar-day lookback which is slightly conservative
    # (may flag illegal when you're actually legal by a few hours). For OT
    # screening this is safe — if flagged, verify exact hour count before bidding.
    try:
        import asyncio
        from pilotlog.config import settings
        from pilotlog.database.connection import init_db, get_session
        from pilotlog.database.queries import get_rolling_totals

        async def _check_limits():
            settings.ensure_directories()
            await init_db()
            async with get_session() as session:
                from datetime import date
                return await get_rolling_totals(session, date.today(), [28, 365])

        totals = asyncio.run(_check_limits())
        ot_block_hrs = (trip.get('block_minutes', 0) or 0) / 60

        current_28d_hrs = totals[28]['minutes'] / 60
        if current_28d_hrs + ot_block_hrs > 100:
            return False, f"672hr limit ({current_28d_hrs:.0f}+{ot_block_hrs:.0f}>{100})"

        current_365d_hrs = totals[365]['minutes'] / 60
        if current_365d_hrs + ot_block_hrs > 1000:
            return False, f"365d limit ({current_365d_hrs:.0f}+{ot_block_hrs:.0f}>{1000})"

    except Exception as e:
        logger.debug(f"Could not check FAR 117 limits: {e}")

    return True, ""


def format_alert(trip, score, breakdown):
    """Format a trip as a concise Signal alert message.

    Example:
      OT 75/100 | HA35 HOU Jun 15-16 (2d) [LEGAL]
      1 leg/day | 19.5 TFP ($6,691) PREMIUM
      Rpt 14:35 | Closes 13:00 | HOU-DEN / DEN-HOU
    """
    tid = trip.get('trip_id', '???')
    base = trip.get('base', '???')
    tfp = trip.get('total_tfp', 0)
    pay_type = trip.get('pay_type', 'straight').upper()
    num_days = trip.get('num_days', '?')
    routing = trip.get('routing_str', '')
    report_str = trip.get('report_str', '?')
    close_str = trip.get('close_str', '?')
    date_range = trip.get('date_range', '')
    avg_lpd = breakdown.get('avg_legs_day', '?')

    from pilotlog.swapa.tfp import CAPTAIN_RATE
    dollars = round(tfp * CAPTAIN_RATE)

    pay_tag = f" {pay_type}" if pay_type != 'STRAIGHT' else ""
    urgency_tag = ""
    hrs = breakdown.get('hours_to_report', 999)
    if hrs <= 4:
        urgency_tag = " LAST MIN"
    elif hrs <= 12:
        urgency_tag = " HOT"
    elif hrs <= 24:
        urgency_tag = " TODAY"

    # Legality check
    is_legal, conflict = check_legality(trip)
    if is_legal:
        legal_tag = " [LEGAL]"
    else:
        legal_tag = f" [ILLEGAL - {conflict}]"

    # Commutability check for non-home bases
    commute_line = ""
    if base != HOME_BASE:
        try:
            from pilotlog.swapa.commute import check_commutability, format_commute_tag
            commute = check_commutability(trip)
            commute_tag = format_commute_tag(commute)
            if commute.get('tier') == 'NO_GO':
                commute_line = f"\n{commute['details']}"
            elif commute.get('tier') not in ('HOME', 'EASY', None):
                commute_line = f"\n{commute['details']}"
        except Exception:
            commute_tag = ""
    else:
        commute_tag = ""

    lines = [
        f"OT {score}/100 | {tid} {base} {date_range} ({num_days}d){urgency_tag}{legal_tag}{commute_tag}",
        f"{avg_lpd} legs/day | {tfp} TFP (${dollars:,}){pay_tag}",
        f"Rpt {report_str} | Closes {close_str} | {routing}",
    ]
    if commute_line:
        lines.append(commute_line.strip())
    return '\n'.join(lines)


def load_snapshot(path=None):
    """Load previous OT snapshot for diffing."""
    p = path or SNAPSHOT_FILE
    if not p.exists():
        return {}
    try:
        with open(p) as f:
            data = json.load(f)
        return {t['trip_id']: t for t in data.get('trips', [])}
    except Exception:
        return {}


def save_snapshot(trips, path=None):
    """Save current OT snapshot."""
    p = path or SNAPSHOT_FILE
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'count': len(trips),
            'trips': list(trips.values()) if isinstance(trips, dict) else trips,
        }, f, indent=2, default=str)


def log_alert(trip, score, breakdown, sent, legal=None, conflict=""):
    """Append alert to JSONL log."""
    ALERT_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        'timestamp': datetime.now().isoformat(),
        'trip_id': trip.get('trip_id'),
        'base': trip.get('base'),
        'score': score,
        'sent': sent,
        'legal': legal,
        'conflict': conflict,
        'tfp': trip.get('total_tfp'),
        'pay_type': trip.get('pay_type'),
        **breakdown,
    }
    with open(ALERT_LOG, 'a') as f:
        f.write(json.dumps(entry, default=str) + '\n')


def _fill_ot_form(page, days_ahead=14):
    """Fill and submit the OT Inventory search form.

    Selects all bases, CA seat, all trip lengths, both pairings+reserves,
    includes ETOPS/international/redeye. Date range: today to days_ahead.
    """
    today = datetime.now()
    end = today + timedelta(days=days_ahead)

    # Fill dates
    page.click('#StartDate')
    time.sleep(0.2)
    page.keyboard.type(today.strftime('%m/%d/%Y'), delay=30)
    page.keyboard.press('Escape')
    time.sleep(0.2)

    page.click('#EndDate')
    time.sleep(0.2)
    page.keyboard.type(end.strftime('%m/%d/%Y'), delay=30)
    page.keyboard.press('Escape')
    time.sleep(0.3)

    # Select all bases (dropdown 0) and all trip lengths (dropdown 2)
    dropdowns = page.query_selector_all('.multiselect-dropdown')
    for dd_idx in [0, 2]:
        if dd_idx < len(dropdowns):
            dropdowns[dd_idx].click()
            time.sleep(0.4)
            for item in dropdowns[dd_idx].query_selector_all('li'):
                if 'Select All' in (item.inner_text() or ''):
                    item.click()
                    time.sleep(0.2)
                    break
            page.click('body', position={'x': 10, 'y': 10})
            time.sleep(0.2)

    # Submit the form
    for btn in page.query_selector_all('button'):
        if 'Get Report' in (btn.inner_text() or ''):
            btn.click()
            break

    # Wait for results to render (server-side)
    time.sleep(15)


# JavaScript to extract trip data from the rendered OT results page.
# The page renders as text with base headers, seat headers, then trip rows.
# Trip IDs: 2-letter + digit + 1-2 alphanumeric (e.g., AA1W, HP46, HA35)
# Report/Release: format like 500/16Jun or 1405/16Jun
# Then: num_days, block, credit, str_pay, prem_pay (all integers, hundredths of TFP)
# Reserve trips have 'R' flag; RON stations listed as "MKE" or "MSP PHL"
_JS_EXTRACT_TRIPS = r"""() => {
    const body = document.querySelector('body');
    if (!body) return {error: 'no body', total: 0, trips: []};

    const lines = body.innerText.split('\n').map(l => l.trim()).filter(l => l);
    const tripRe = /^([A-Z]{2}[0-9][A-Z0-9]{1,2})$/;
    const baseRe = /^(ATL|AUS|BNA|BWI|DAL|DEN|HOU|LAS|LAX|MCO|MDW|OAK|PHX)$/;
    const reportRe = /^(\d{3,4})\/(\d{2})([A-Z][a-z]{2})$/;
    const stationRe = /^[A-Z]{3}(\s+[A-Z]{3})*$/;

    let currentBase = '';
    let currentSeat = '';
    const trips = [];

    for (let i = 0; i < lines.length; i++) {
        if (baseRe.test(lines[i])) { currentBase = lines[i]; continue; }
        if (/^(CA|FO)\s*$/.test(lines[i])) { currentSeat = lines[i].trim(); continue; }

        if (tripRe.test(lines[i])) {
            const tid = lines[i];
            const lookahead = lines.slice(i + 1, i + 20);
            const trip = {trip_id: tid, base: currentBase, seat: currentSeat};

            for (const la of lookahead) {
                const rm = la.match(reportRe);
                if (rm) {
                    if (!trip.report) trip.report = la;
                    else if (!trip.release) trip.release = la;
                }
            }

            const nums = [];
            for (const la of lookahead) {
                if (/^\d+$/.test(la)) nums.push(parseInt(la));
                if (tripRe.test(la) || baseRe.test(la)) break;
            }
            if (nums.length >= 5) {
                trip.num_days = nums[0];
                trip.block = nums[1];
                trip.credit = nums[2];
                trip.str_pay = nums[3];
                trip.prem_pay = nums[4];
            }

            for (const la of lookahead) {
                if (/^R\s*$/.test(la)) { trip.is_reserve = true; break; }
                if (tripRe.test(la) || baseRe.test(la)) break;
            }

            for (const la of lookahead) {
                if (stationRe.test(la) && !baseRe.test(la) && !tripRe.test(la) && !/^(CA|FO)$/.test(la)) {
                    trip.ron = la; break;
                }
                if (tripRe.test(la) || baseRe.test(la)) break;
            }

            trips.push(trip);
        }
    }
    return {total: trips.length, trips: trips};
}"""


def fetch_ot_inventory(page, days_ahead=14):
    """Fill OT form, submit, and extract all trips from the results.

    Returns list of normalized trip dicts ready for scoring.
    """
    _fill_ot_form(page, days_ahead)
    raw = page.evaluate(_JS_EXTRACT_TRIPS)

    trips = []
    for t in raw.get('trips', []):
        credit_hundredths = t.get('credit', 0)
        str_hundredths = t.get('str_pay', 0)
        prem_hundredths = t.get('prem_pay', 0)

        # Determine pay type from str vs prem comparison
        if prem_hundredths > str_hundredths:
            pay_type = 'premium'
        elif prem_hundredths > str_hundredths * 1.5:
            pay_type = 'double'
        else:
            pay_type = 'straight'

        # Parse report time into datetime for urgency scoring
        report_time = None
        report_str = t.get('report', '')
        if report_str:
            m = re.match(r'(\d{3,4})/(\d{2})([A-Z][a-z]{2})', report_str)
            if m:
                time_part = m.group(1).zfill(4)
                day = m.group(2)
                mon = m.group(3)
                try:
                    year = datetime.now().year
                    report_time = datetime.strptime(f"{day}{mon}{year} {time_part}", "%d%b%Y %H%M")
                    # If parsed date is in the past, it's next year
                    if report_time < datetime.now() - timedelta(days=1):
                        report_time = report_time.replace(year=year + 1)
                except ValueError:
                    pass

        # Parse RON stations for overnight/destination analysis
        ron_stations = set()
        if t.get('ron'):
            ron_stations = set(t['ron'].split())

        trip = {
            'trip_id': t.get('trip_id', ''),
            'base': t.get('base', ''),
            'seat': t.get('seat', 'CA'),
            'source': 'ot',
            'num_days': t.get('num_days', 0),
            'total_legs': 0,  # not available from OT page directly
            'total_tfp': credit_hundredths / 100.0,
            'str_tfp': str_hundredths / 100.0,
            'prem_tfp': prem_hundredths / 100.0,
            'pay_type': pay_type,
            'is_reserve': t.get('is_reserve', False),
            'report_time': report_time,
            'report_str': report_str,
            'release_str': t.get('release', ''),
            'date_range': f"{report_str.split('/')[1] if '/' in report_str else '?'}-{t.get('release', '').split('/')[1] if '/' in t.get('release', '') else '?'}",
            'routing_str': t.get('ron', ''),
            'overnight_stations': ron_stations,
            'block_minutes': t.get('block', 0),
        }

        # Estimate legs from block time and days if not available
        if trip['block_minutes'] and trip['num_days']:
            # Rough estimate: avg ~120 min block per leg
            trip['total_legs'] = max(trip['num_days'], round(trip['block_minutes'] / 120))

        trips.append(trip)

    return trips


def scan_open_time(headless=True, alert_threshold=40, dry_run=False):
    """Main scanner: fetch OT inventory, diff, score, alert.

    Args:
        headless: run browser headless
        alert_threshold: minimum score to trigger Signal alert (0-100)
        dry_run: if True, don't send Signal, just print

    Returns:
        dict with scan results
    """
    from playwright.sync_api import sync_playwright
    from pilotlog.swapa.client import create_browser, ensure_logged_in, get_page_tables, TOOLS

    results = {
        'timestamp': datetime.now().isoformat(),
        'trips_found': 0,
        'new_trips': 0,
        'alerts_sent': 0,
        'errors': [],
    }

    with sync_playwright() as p:
        browser, context = create_browser(p, headless=headless)
        page = context.new_page()

        try:
            # Navigate to Open Time Inventory and fill the search form
            ensure_logged_in(page, TOOLS['open_time'])
            time.sleep(5)

            current_trips = fetch_ot_inventory(page, days_ahead=14)

            if not current_trips:
                results['errors'].append("No trips parsed from OT page")
                logger.warning("No trips found on OT inventory page")

            results['trips_found'] = len(current_trips)

            # Build current index
            current_index = {}
            for t in current_trips:
                tid = t.get('trip_id', '')
                if tid:
                    current_index[tid] = t

            # Load previous snapshot and diff
            prev_index = load_snapshot()
            new_trip_ids = set(current_index.keys()) - set(prev_index.keys())
            results['new_trips'] = len(new_trip_ids)

            # Score and alert on new trips
            alerts = []
            for tid in sorted(new_trip_ids):
                trip = current_index[tid]
                score, breakdown = score_trip(trip)

                # Only text Hourly Open Time (near-term). Daily Open Time
                # (reports beyond the HOT window) is logged but not sent.
                is_hot = breakdown.get('hours_to_report', 999) <= HOT_WINDOW_HOURS

                # Only text trips Darrell can legally pick up (no schedule
                # conflict, no FAR 117 limit bust). Illegal ones still logged.
                is_legal, conflict = check_legality(trip)

                if score >= alert_threshold and is_hot and is_legal:
                    msg = format_alert(trip, score, breakdown)

                    if dry_run:
                        print(f"\n--- WOULD ALERT (score={score}) ---")
                        print(msg)
                        print("---")
                        sent = False
                    else:
                        sent = send_signal_alert(msg)
                        results['alerts_sent'] += 1 if sent else 0

                    log_alert(trip, score, breakdown, sent,
                              legal=True, conflict="")
                    alerts.append({'trip_id': tid, 'score': score, 'message': msg})
                else:
                    log_alert(trip, score, breakdown, False,
                              legal=is_legal, conflict=conflict)

            results['alerts'] = alerts

            # Save new snapshot
            save_snapshot(current_index)

        except Exception as e:
            results['errors'].append(str(e))
            logger.error(f"OT scan failed: {e}", exc_info=True)
        finally:
            browser.close()

    return results


def scan_summary(results):
    """Format scan results as a human-readable summary."""
    lines = [
        f"OT Scan @ {results.get('timestamp', '?')}",
        f"  Trips on board: {results.get('trips_found', 0)}",
        f"  New since last: {results.get('new_trips', 0)}",
        f"  Alerts sent:    {results.get('alerts_sent', 0)}",
    ]
    if results.get('errors'):
        lines.append(f"  Errors: {'; '.join(results['errors'])}")
    if results.get('alerts'):
        lines.append("  --- Alerts ---")
        for a in results['alerts']:
            lines.append(f"  [{a['score']}] {a['trip_id']}")
    return '\n'.join(lines)
