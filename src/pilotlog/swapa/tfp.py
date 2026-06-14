"""TFP calculation engine — mileage, over-schedule, rigs, and overrides.

CBA Section 2.B-C (leg TFP), 2.H (rigs), 2.J (overrides).
All rates are 2026 Captain 12+ YOS values.
"""

import math
import json
from pathlib import Path

# CBA constants (2026 Captain 12+ YOS)
CAPTAIN_RATE = 343.14   # $/TFP
DHR_RATE = 0.74         # TFP per duty hour
DPM = 5.0               # duty period minimum TFP
ADG_RATE = 6.5           # TFP per domicile day
THR_DIVISOR = 3.0        # 1 TFP per 3 hours away
CONUS_PER_DIEM = 3.04    # $/hr
OCONUS_PER_DIEM = 3.63   # $/hr
CREW_MEAL = 20.0         # $ per flight >= 4hr block

# Non-domestic stations
NON_DOMESTIC = {
    'SJO', 'LIR', 'PVR', 'CUN', 'CZM', 'SJD', 'GDL',
    'MBJ', 'KIN', 'NAS', 'GGT', 'AUA', 'GCM', 'PUJ', 'SDQ',
    'BZE', 'TCA', 'PLS', 'HAV',
}
OCONUS_DOMESTIC = {'SJU', 'STX', 'STT', 'GUM'}

AIRPORTS_FILE = Path(__file__).parent / "data" / "airports.json"


def load_airports(path=None):
    """Load airport coordinate data."""
    p = path or AIRPORTS_FILE
    with open(p) as f:
        return json.load(f)


def haversine_sm(lat1, lon1, lat2, lon2):
    """Great circle distance in statute miles."""
    R_NM = 3440.065
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    nm = 2 * R_NM * math.asin(math.sqrt(a))
    return nm * 1.15078


def tfp_mileage(miles):
    """Mileage formula: 1.0 + 0.1 per 40-mile increment over 243, rounded standard."""
    if miles <= 243:
        return 1.0
    increments = round((miles - 243) / 40)
    return 1.0 + increments * 0.1


def tfp_overschedule(block_minutes):
    """Over-schedule formula: 1.0 + 0.1 per 5 min over 55, truncated."""
    if block_minutes <= 55:
        return 1.0
    increments = int((block_minutes - 55) / 5)
    return 1.0 + increments * 0.1


def compute_leg_tfp(origin, dest, block_minutes, airports=None):
    """Compute TFP for a leg: greater of mileage vs over-schedule.

    Returns (tfp, miles). Miles is None if airports not found.
    """
    if airports is None:
        airports = load_airports()

    os_tfp = tfp_overschedule(block_minutes)

    if origin in airports and dest in airports:
        o, d = airports[origin], airports[dest]
        miles = haversine_sm(o['lat'], o['lon'], d['lat'], d['lon'])
        mi_tfp = tfp_mileage(miles)
        return round(max(mi_tfp, os_tfp), 2), round(miles, 0)
    return round(os_tfp, 2), None


def compute_dhr(duty_minutes):
    """DHR rig: 0.74 TFP per duty hour (actual, not rounded up)."""
    if not duty_minutes:
        return 0
    return round((duty_minutes / 60) * DHR_RATE, 2)


def compute_dp_credit(leg_sum, duty_minutes):
    """Duty period credit: max(sum of leg TFP, DHR, DPM)."""
    dhr = compute_dhr(duty_minutes)
    return round(max(leg_sum, dhr, DPM), 2)


def compute_trip_credit(dp_credits, num_days):
    """Trip-level credit: max(sum of DP credits, ADG)."""
    dp_sum = round(sum(dp_credits), 2)
    adg = round(ADG_RATE * num_days, 2)
    return round(max(dp_sum, adg), 2), adg, dp_sum
