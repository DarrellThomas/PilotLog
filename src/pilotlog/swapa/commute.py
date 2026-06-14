"""Commutability checker — can the pilot get to a non-home base in time?

For OT trips at non-HOU bases, checks whether there's a realistic way
to commute from HOU to the base city before report time.

CBA Section 12.H Commuter Rules:
  To be eligible for commuter protections, a pilot must attempt a minimum of:
  (a) Two (2) scheduled SWA flights from commuter station that block in at
      the pairing's originating city PRIOR to scheduled report time; OR
  (b) One (1) SWA flight that blocks in at least ONE (1) HOUR prior to
      scheduled report time.
  The pilot may use online or offline airports (other carriers), as long as
  he can report at scheduled check-in.

  CBA 6.D.5: SWA pilots have PRIORITY on cockpit jumpseat (guaranteed seat)
  CBA 6.D.6: Pilots pre-board like operating crew for jumpseat
  12.H.11: Compliant commuter who fails to check in on time = NOT a no-show

Commute quality tiers:
  EASY    — nonstop SWA, arrives 3+ hrs before report, short flight
  DOABLE  — nonstop SWA, arrives 1-3 hrs before report
  TIGHT   — nonstop SWA, arrives just at the 1hr minimum, or needs early AM flight
  STRETCH — requires connecting flight or other carrier
  NO_GO   — no realistic way to get there in time
"""

import logging
import math
from datetime import datetime, timedelta
from pathlib import Path

from pilotlog.swapa.tfp import load_airports, haversine_sm

logger = logging.getLogger(__name__)

HOME_BASE = "HOU"

# CBA 12.H buffer requirements
# Option B (preferred): 1 SWA flight blocking in >= 1hr before report
# Option A (backup): 2 SWA flights blocking in before report (no 1hr req)
# Jumpseat guaranteed (CBA 6.D.5) — loads don't matter on own metal
OWN_METAL_BUFFER_MIN = 60    # 1 hour block-in before report (CBA 12.H.1.b)
OPTION_A_BUFFER_MIN = 0      # just block in before report (CBA 12.H.1.a, need 2 flights)

# Estimated block times from HOU to each SWA base (minutes)
# Derived from great circle distance and typical 737 speed
# These are conservative estimates (actual may be shorter)
_airports = None
def _get_airports():
    global _airports
    if _airports is None:
        _airports = load_airports()
    return _airports


def estimate_block_time(origin, dest):
    """Estimate block time in minutes between two airports.

    Uses great circle distance and average 737 ground speed of 450 mph,
    plus 30 min for taxi/climb/descent.
    """
    airports = _get_airports()
    if origin not in airports or dest not in airports:
        return None
    o, d = airports[origin], airports[dest]
    miles = haversine_sm(o['lat'], o['lon'], d['lat'], d['lon'])
    return int(miles / 450 * 60 + 30)


# SWA nonstop routes from HOU (confirmed from logbook data)
# All 13 SWA bases have direct HOU service
HOU_DIRECT_BASES = {
    'ATL', 'AUS', 'BNA', 'BWI', 'DAL', 'DEN',
    'LAS', 'LAX', 'MCO', 'MDW', 'OAK', 'PHX',
}

# Typical first/last SWA departure times from HOU (approximate, CST)
# These shift seasonally — used as rough planning guides
EARLIEST_HOU_DEPARTURE = 5 * 60 + 30   # 0530 CST
LATEST_HOU_DEPARTURE = 21 * 60 + 30    # 2130 CST

# Timezone offsets from CST for base cities (standard rough offsets)
BASE_TZ_OFFSET = {
    'ATL': 1,   # EST = CST+1
    'AUS': 0,
    'BNA': 0,   # CST
    'BWI': 1,   # EST
    'DAL': 0,
    'DEN': -1,  # MST = CST-1
    'HOU': 0,
    'LAS': -2,  # PST = CST-2 (actually -1 during DST but conservative)
    'LAX': -2,
    'MCO': 1,   # EST
    'MDW': 0,   # CST
    'OAK': -2,  # PST
    'PHX': -2,  # MST (no DST, but offset varies)
}


def check_commutability(trip):
    """Check if the pilot can commute from HOU to the trip's base in time.

    Args:
        trip: dict with 'base', 'report_time' (datetime or str), 'report_str'

    Returns:
        dict with:
            commutable: bool
            tier: EASY | DOABLE | TIGHT | STRETCH | NO_GO
            details: human-readable explanation
            must_depart_by: latest HOU departure time (CST)
            flight_time_min: estimated block time
            buffer_min: how much buffer before report
    """
    base = trip.get('base', '').upper()

    # Home base — no commute needed
    if base == HOME_BASE or not base:
        return {
            'commutable': True,
            'tier': 'HOME',
            'details': 'Home base — no commute needed',
        }

    # Check if pilot might already be at this base (ending a trip with DH release)
    # This is a possibility flag — pilot may already be positioned there
    already_there = False
    try:
        from pilotlog.swapa.ical import fetch_ical, parse_ical_feed
        ical_text = fetch_ical()
        my_trips = parse_ical_feed(ical_text)
        for my_trip in my_trips:
            if not my_trip.get('days'):
                continue
            last_day = my_trip['days'][-1]
            last_legs = [l for l in last_day.get('legs', []) if l.get('dest')]
            if last_legs:
                last_dest = last_legs[-1]['dest']
                # If last trip ends at this base's city, pilot might already be there
                if last_dest == base:
                    # Check if the release is close to this OT trip's report
                    already_there = True
    except Exception:
        pass

    # Parse report time
    report_time = trip.get('report_time')
    if not report_time:
        return {
            'commutable': True,
            'tier': 'UNKNOWN',
            'details': 'No report time — cannot assess commute',
        }
    if isinstance(report_time, str):
        try:
            report_time = datetime.fromisoformat(report_time)
        except ValueError:
            return {'commutable': True, 'tier': 'UNKNOWN', 'details': 'Cannot parse report time'}

    # Estimate flight time
    block_min = estimate_block_time(HOME_BASE, base)
    if block_min is None:
        block_min = 180  # default 3hr estimate for unknown routes

    # Must arrive 1hr before report (own metal)
    # Flight time + taxi/deplane (~20 min) + get to ops (~20 min) + buffer
    ground_time = 40  # deplane + transit to ops
    must_arrive_by = report_time - timedelta(minutes=OWN_METAL_BUFFER_MIN)
    must_land_by = must_arrive_by - timedelta(minutes=ground_time)
    must_depart_by = must_land_by - timedelta(minutes=block_min)

    # Convert must_depart_by to CST for comparison with HOU schedule
    # report_time is in base local time, so adjust for timezone
    tz_offset_hrs = BASE_TZ_OFFSET.get(base, 0)
    must_depart_cst = must_depart_by - timedelta(hours=tz_offset_hrs)

    depart_hour_cst = must_depart_cst.hour + must_depart_cst.minute / 60
    buffer_before_report = (report_time - must_depart_by).total_seconds() / 60 - block_min - ground_time

    # Determine tier
    now = datetime.now()
    hours_until_depart = (must_depart_cst - now).total_seconds() / 3600

    if already_there:
        return {
            'commutable': True,
            'tier': 'EASY',
            'details': f'May already be at {base} (prior trip ends there)',
            'base': base,
            'flight_time_min': 0,
            'must_depart_by_cst': 'N/A',
            'hours_until_depart': hours_until_depart,
        }

    if base not in HOU_DIRECT_BASES:
        tier = 'STRETCH'
        details = f'No direct HOU-{base} — need connecting flight or other carrier'
        commutable = hours_until_depart > 4  # need time to figure it out
    elif hours_until_depart < 0:
        tier = 'NO_GO'
        details = f'Too late — needed to depart HOU by {must_depart_cst.strftime("%H:%M")} CST'
        commutable = False
    elif depart_hour_cst < 5.5:
        # Need a flight before earliest HOU departure
        # Check if previous evening flight works (red-eye commute)
        prev_evening_depart = must_depart_cst - timedelta(hours=12)
        if prev_evening_depart.hour >= 17:
            tier = 'TIGHT'
            details = (f'Need evening-before commute — depart HOU ~{prev_evening_depart.strftime("%H:%M")} CST, '
                       f'overnight at {base}, {block_min}min flight')
            commutable = True
        else:
            tier = 'STRETCH'
            details = f'Very early report — may need prev-day positioning to {base}'
            commutable = True
    elif hours_until_depart >= 6 and block_min <= 180:
        tier = 'EASY'
        details = (f'Nonstop HOU-{base} ({block_min}min), '
                   f'depart by {must_depart_cst.strftime("%H:%M")} CST, '
                   f'plenty of time')
        commutable = True
    elif hours_until_depart >= 3:
        tier = 'DOABLE'
        details = (f'Nonstop HOU-{base} ({block_min}min), '
                   f'depart by {must_depart_cst.strftime("%H:%M")} CST')
        commutable = True
    else:
        tier = 'TIGHT'
        details = (f'Nonstop HOU-{base} ({block_min}min), '
                   f'must depart by {must_depart_cst.strftime("%H:%M")} CST — cutting it close')
        commutable = True

    return {
        'commutable': commutable,
        'tier': tier,
        'details': details,
        'base': base,
        'flight_time_min': block_min,
        'must_depart_by_cst': must_depart_cst.strftime('%H:%M') if must_depart_cst else None,
        'hours_until_depart': round(hours_until_depart, 1),
    }


def format_commute_tag(result):
    """Format commutability result as a short tag for Signal alerts."""
    tier = result.get('tier', 'UNKNOWN')
    if tier == 'HOME':
        return ''  # no tag needed for home base
    if tier == 'EASY':
        return f' [COMMUTE OK]'
    if tier == 'DOABLE':
        return f' [COMMUTE: depart HOU by {result.get("must_depart_by_cst", "?")}]'
    if tier == 'TIGHT':
        return f' [COMMUTE TIGHT: {result.get("details", "")}]'
    if tier == 'STRETCH':
        return f' [COMMUTE HARD: {result.get("details", "")}]'
    if tier == 'NO_GO':
        return f' [CANT GET THERE]'
    return ''
