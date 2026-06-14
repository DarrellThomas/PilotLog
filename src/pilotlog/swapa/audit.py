"""Trip pay audit engine — baseline capture, comparison, override computation.

Migrated from ~/.claude/skills/trip-audit/trip_tools.py
"""

import json
import math
from datetime import datetime
from pathlib import Path

from pilotlog.swapa.tfp import (
    CAPTAIN_RATE, NON_DOMESTIC, OCONUS_DOMESTIC,
    compute_leg_tfp, compute_dhr, compute_dp_credit, compute_trip_credit,
    load_airports, DPM, DHR_RATE, ADG_RATE,
)
from pilotlog.swapa.ical import fetch_ical, parse_ical_feed

DATA_DIR = Path(__file__).parent / "data"
BASELINES_DIR = DATA_DIR / "baselines"


def enrich_trip(trip, airports=None):
    """Add TFP computations to a parsed trip."""
    if airports is None:
        airports = load_airports()

    for day in trip['days']:
        for leg in day['legs']:
            if leg.get('type') in ('HTL', 'DUTY') or leg['block_minutes'] == 0:
                leg['tfp'] = 0
                leg['miles'] = 0
                continue
            tfp, miles = compute_leg_tfp(leg['origin'], leg['dest'], leg['block_minutes'], airports)
            leg['tfp'] = tfp
            leg['miles'] = miles or 0
            leg['non_domestic'] = leg['origin'] in NON_DOMESTIC or leg['dest'] in NON_DOMESTIC
            leg['oconus'] = (leg['non_domestic'] or
                             leg['origin'] in OCONUS_DOMESTIC or leg['dest'] in OCONUS_DOMESTIC)

        # Duty period rigs
        leg_sum = sum(l['tfp'] for l in day['legs'])
        duty_min = day.get('duty_minutes') or 0
        dhr = compute_dhr(duty_min)

        day['leg_sum'] = round(leg_sum, 2)
        day['dhr'] = dhr
        day['dpm'] = DPM
        day['dp_credit'] = compute_dp_credit(leg_sum, duty_min)

    # Trip-level rigs
    num_days = len(trip['days'])
    dp_credits = [d['dp_credit'] for d in trip['days']]
    trip_credit, adg, dp_sum = compute_trip_credit(dp_credits, num_days)

    trip['trip_credit'] = trip_credit
    trip['adg'] = adg
    trip['dp_sum'] = dp_sum
    trip['adg_applies'] = adg > dp_sum

    return trip


def save_baseline(trip, trip_id=None):
    """Save trip as a baseline for later audit comparison."""
    BASELINES_DIR.mkdir(parents=True, exist_ok=True)
    tid = trip_id or trip['trip_id']
    date_str = datetime.now().strftime('%Y%m%d')
    filepath = BASELINES_DIR / f"{tid}_{date_str}.json"
    with open(filepath, 'w') as f:
        json.dump(trip, f, indent=2, default=str)
    return filepath


def load_baseline(trip_id):
    """Load the most recent baseline for a trip ID."""
    BASELINES_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(BASELINES_DIR.glob(f"{trip_id}*.json"), reverse=True)
    if not files:
        files = sorted(BASELINES_DIR.glob(f"*{trip_id}*.json"), reverse=True)
    if not files:
        return None
    with open(files[0]) as f:
        return json.load(f)


def list_baselines():
    """List all stored baselines."""
    BASELINES_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    for f in sorted(BASELINES_DIR.glob("*.json")):
        with open(f) as fh:
            data = json.load(fh)
        results.append({
            'file': f.name,
            'trip_id': data.get('trip_id', f.stem),
            'days': len(data.get('days', [])),
        })
    return results


def identify_original_legs(baseline_day, current_day):
    """Tag legs in current_day as original or not based on baseline."""
    original_flights = set()
    for leg in baseline_day.get('legs', []):
        if leg.get('type') in ('HTL', 'DUTY'):
            continue
        original_flights.add((leg['flight'], leg['origin'], leg['dest']))

    for leg in current_day.get('legs', []):
        if leg.get('type') in ('HTL', 'DUTY'):
            leg['is_original'] = True
            continue
        leg['is_original'] = (leg['flight'], leg['origin'], leg['dest']) in original_flights


def compute_lco_rate(day_index, total_days, day_data, baseline_day):
    """Determine LCO rate: 50% or 100%."""
    is_first = (day_index == 0)
    is_last = (day_index == total_days - 1)

    orig_legs = [l for l in baseline_day.get('legs', []) if l.get('type') not in ('HTL', 'DUTY')]
    curr_legs = [l for l in day_data.get('legs', []) if l.get('type') not in ('HTL', 'DUTY')]

    if not orig_legs or not curr_legs:
        return 0.50

    if is_first:
        orig_first_depart = orig_legs[0].get('depart', '9999')
        for leg in curr_legs:
            if not leg.get('is_original') and leg.get('depart', '9999') < orig_first_depart:
                return 1.00

    if is_last:
        orig_last_arrive = orig_legs[-1].get('arrive', '0000')
        curr_last_arrive = curr_legs[-1].get('arrive', '0000') if curr_legs else '0000'
        if curr_last_arrive > orig_last_arrive:
            return 1.00

    return 0.50


def run_audit(baseline, current):
    """Compare baseline trip against current, compute all overrides."""
    results = {
        'baseline_id': baseline['trip_id'],
        'current_id': current['trip_id'],
        'days': [],
        'total_baseline_credit': 0,
        'total_online_sched': 0,
        'total_lco': 0,
        'total_gto': 0,
        'total_other_overrides': 0,
    }

    num_days = max(len(baseline['days']), len(current['days']))

    for i in range(num_days):
        b_day = baseline['days'][i] if i < len(baseline['days']) else None
        c_day = current['days'][i] if i < len(current['days']) else None

        if b_day and c_day:
            identify_original_legs(b_day, c_day)

        b_credit = b_day['dp_credit'] if b_day else 0
        c_credit = c_day['dp_credit'] if c_day else 0
        online_credit = max(b_credit, c_credit)

        # LCO
        lco_total = 0
        lco_details = []
        if c_day and b_day:
            lco_rate = compute_lco_rate(i, num_days, c_day, b_day)
            for leg in c_day.get('legs', []):
                if leg.get('type') in ('HTL', 'DUTY'):
                    continue
                if not leg.get('is_original', True):
                    lco_amt = round(leg.get('tfp', 0) * lco_rate, 2)
                    lco_total += lco_amt
                    lco_details.append({
                        'flight': leg['flight'],
                        'route': f"{leg['origin']}-{leg['dest']}",
                        'dh': leg.get('deadhead', False),
                        'tfp': leg.get('tfp', 0),
                        'lco_rate': lco_rate,
                        'lco_amt': lco_amt,
                    })

        # LDO
        duty_min = c_day.get('duty_minutes', 0) if c_day else 0
        ldo = 1.0 if duty_min and duty_min > 720 else 0

        day_result = {
            'day': i + 1,
            'date': c_day.get('date') if c_day else (b_day.get('date') if b_day else None),
            'baseline_credit': b_credit,
            'actual_credit': c_credit,
            'online_sched_credit': online_credit,
            'lco_total': round(lco_total, 2),
            'lco_details': lco_details,
            'ldo': ldo,
            'day_total': round(online_credit + lco_total + ldo, 2),
        }

        results['days'].append(day_result)
        results['total_baseline_credit'] += b_credit
        results['total_online_sched'] += online_credit
        results['total_lco'] += lco_total
        results['total_other_overrides'] += ldo

    for key in ('total_baseline_credit', 'total_online_sched', 'total_lco', 'total_other_overrides'):
        results[key] = round(results[key], 2)

    results['grand_total'] = round(
        results['total_online_sched'] + results['total_lco'] +
        results['total_other_overrides'] + results['total_gto'], 2
    )
    results['dollar_baseline'] = round(results['total_baseline_credit'] * CAPTAIN_RATE, 2)
    results['dollar_total'] = round(results['grand_total'] * CAPTAIN_RATE, 2)
    results['dollar_delta'] = round(results['dollar_total'] - results['dollar_baseline'], 2)

    return results
