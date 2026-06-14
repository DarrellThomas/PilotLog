#!/usr/bin/env python3
"""Seniority tracker — download list from SWAPA, compute base positions, store snapshot.

Usage:
    python3 scan_seniority.py            # download fresh list, compute, print
    python3 scan_seniority.py --cached   # use existing CSV (skip download)
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

LOG_DIR = Path(__file__).parent.parent / "logs"


def setup_logging():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(LOG_DIR / "seniority.log"),
            logging.StreamHandler(),
        ],
    )


def main():
    parser = argparse.ArgumentParser(description="SWAPA seniority tracker")
    parser.add_argument("--cached", action="store_true",
                        help="Use existing CSV instead of downloading fresh")
    args = parser.parse_args()

    setup_logging()
    logger = logging.getLogger(__name__)

    from pilotlog.swapa.seniority import (
        download_seniority_csv, parse_seniority_csv,
        compute_base_positions, format_seniority_report, _get_employee_id,
    )

    emp_id = _get_employee_id()
    if not emp_id:
        logger.error("No SWAPA_ID in ~/.env")
        sys.exit(1)

    if not args.cached:
        logger.info("Downloading fresh seniority list...")
        csv_path = download_seniority_csv()
        if not csv_path:
            logger.error("Download failed")
            sys.exit(1)
    else:
        logger.info("Using cached seniority CSV")

    pilots = parse_seniority_csv()
    logger.info(f"Parsed {len(pilots)} pilots")

    result = compute_base_positions(pilots, emp_id)
    report = format_seniority_report(result)
    print(report)

    # Save snapshot
    import json
    snapshot_dir = Path(__file__).parent.parent / "src" / "pilotlog" / "swapa" / "data"
    snapshot_file = snapshot_dir / "seniority_snapshot.json"
    with open(snapshot_file, 'w') as f:
        json.dump(result, f, indent=2, default=str)
    logger.info(f"Snapshot saved: {snapshot_file}")


if __name__ == "__main__":
    main()
