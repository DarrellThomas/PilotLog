"""iCal feed parser for SWA CrewHub schedule."""

import os
import re
import subprocess
from pathlib import Path


TZ_OFFSETS = {
    'EDT': -4, 'CDT': -5, 'MDT': -6, 'PDT': -7, 'MST': -7,
    'EST': -5, 'CST': -6, 'PST': -8, 'AST': -4, 'HST': -10,
}

ENV_FILE = Path.home() / ".env"


def fetch_ical():
    """Fetch iCal feed from SWA_SCHEDULE URL in ~/.env."""
    url = None
    with open(ENV_FILE) as f:
        for line in f:
            if line.startswith('SWA_SCHEDULE='):
                url = line.split('=', 1)[1].strip().strip('"')
                break
    if not url:
        raise RuntimeError("SWA_SCHEDULE not found in ~/.env")
    result = subprocess.run(['curl', '-s', url], capture_output=True, text=True)
    return result.stdout


def parse_ical_description(desc):
    """Parse a CrewHub iCal DESCRIPTION into structured trip data."""
    desc = desc.replace('\\n', '\n').replace('\n ', '')

    days = []
    current_day = None
    lines = desc.split('\n')

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Day header: "Thu Jun 11"
        day_match = re.match(r'^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+(\w+)\s+(\d+)', line)
        if day_match:
            if current_day:
                days.append(current_day)
            current_day = {
                'dow': day_match.group(1),
                'month': day_match.group(2),
                'date': int(day_match.group(3)),
                'legs': [],
                'report': None, 'release': None,
                'duty_minutes': None, 'block_minutes': None,
                'credit': None, 'hotel': None, 'flags': '',
            }
            continue

        if not current_day:
            continue

        # Report time
        rpt_match = re.match(r'^(?:Report|Rpt)\s+(\d{2}:?\d{2})\s*(\w+)?', line)
        if rpt_match:
            current_day['report'] = rpt_match.group(1).replace(':', '')
            current_day['report_tz'] = rpt_match.group(2) or 'CDT'
            continue

        # Release time
        rls_match = re.match(r'^Rls\s+(\d{2}:?\d{2})', line)
        if rls_match:
            current_day['release'] = rls_match.group(1).replace(':', '')
            continue

        # Duty/Block/Credit
        dbc_match = re.match(r'^Duty\s+([\d:]+)\s+Block\s+([\d:]+)\s+Credit\s+([\d.]+)\s*(.*)', line)
        if dbc_match:
            current_day['credit'] = float(dbc_match.group(3))
            current_day['flags'] = dbc_match.group(4).strip()
            for key, val_str in [('duty_minutes', dbc_match.group(1)), ('block_minutes', dbc_match.group(2))]:
                if ':' in val_str:
                    parts = val_str.split(':')
                    try:
                        current_day[key] = int(parts[0] or 0) * 60 + int(parts[1] or 0)
                    except ValueError:
                        current_day[key] = 0
            continue

        # Flight leg
        leg_match = re.match(
            r'^(DM\s+)?(\d+)\s+(\w{3})\s+(\d{2}:?\d{2})\s+(\w+)\s+(\w{3})\s+(\d{2}:?\d{2})\s+(\w+)',
            line
        )
        if leg_match:
            depart_time = leg_match.group(4).replace(':', '')
            arrive_time = leg_match.group(7).replace(':', '')
            dh, dm = int(depart_time[:2]), int(depart_time[2:])
            ah, am = int(arrive_time[:2]), int(arrive_time[2:])
            dep_tz, arr_tz = leg_match.group(5), leg_match.group(8)

            dep_utc = (dh * 60 + dm) - TZ_OFFSETS.get(dep_tz, -5) * 60
            arr_utc = (ah * 60 + am) - TZ_OFFSETS.get(arr_tz, -5) * 60
            if arr_utc < dep_utc:
                arr_utc += 24 * 60

            current_day['legs'].append({
                'flight': int(leg_match.group(2)),
                'origin': leg_match.group(3),
                'depart': depart_time, 'depart_tz': dep_tz,
                'dest': leg_match.group(6),
                'arrive': arrive_time, 'arrive_tz': arr_tz,
                'deadhead': bool(leg_match.group(1)),
                'block_minutes': arr_utc - dep_utc,
            })
            continue

        # Hotel
        hotel_keywords = ('Hotel:', 'Hilton', 'Marriott', 'Sheraton', 'Doubletree',
                          'Embassy', 'Westin', 'Canopy', 'Hyatt', 'Peppermill', 'Grove')
        if any(kw in line for kw in hotel_keywords):
            if current_day:
                current_day['hotel'] = line
            continue

        # HTL/DUTY
        htl_match = re.match(r'^(HTL|DUTY)\s+(\w{3})', line)
        if htl_match:
            current_day['legs'].append({
                'flight': 0, 'origin': htl_match.group(2),
                'dest': htl_match.group(2), 'type': htl_match.group(1),
                'deadhead': False, 'block_minutes': 0,
            })

    if current_day:
        days.append(current_day)
    return days


def parse_ical_feed(ical_text, trip_id=None):
    """Parse iCal feed text, optionally filtering by trip ID."""
    trips = []
    events = re.split(r'BEGIN:VEVENT', ical_text)

    for event in events[1:]:
        loc_match = re.search(r'LOCATION:Trip:\s*(\S+)', event)
        if not loc_match:
            continue

        tid = loc_match.group(1)
        if trip_id and tid != trip_id:
            continue

        desc_match = re.search(r'DESCRIPTION:(.*?)(?=\n[A-Z]+[:;])', event, re.DOTALL)
        if not desc_match:
            continue

        desc = desc_match.group(1)
        desc = re.sub(r'\n\s', '', desc)

        summary_match = re.search(r'SUMMARY:(.*)', event)
        modified_match = re.search(r'LAST-MODIFIED:(\S+)', event)
        created_match = re.search(r'CREATED:(\S+)', event)

        days = parse_ical_description(desc)
        trips.append({
            'trip_id': tid,
            'summary': summary_match.group(1).strip() if summary_match else '',
            'last_modified': modified_match.group(1) if modified_match else '',
            'created': created_match.group(1) if created_match else '',
            'days': days,
        })

    return trips
