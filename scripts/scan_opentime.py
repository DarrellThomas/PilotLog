#!/usr/bin/env python3
"""Open Time scanner — cron-able script that polls SWAPA and sends Signal alerts.

Usage:
    python3 scan_opentime.py                    # normal scan, send alerts
    python3 scan_opentime.py --dry-run          # print what would alert, don't send
    python3 scan_opentime.py --threshold 30     # lower alert threshold (default 40)
    python3 scan_opentime.py --visible          # run browser visibly (debug)

Designed to run every 3-5 minutes via cron. Uses a lockfile to prevent overlapping runs.
The edge: we see new OT postings before SWAPA's own notification system delivers them.
"""

import argparse
import fcntl
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

# Add src to path for development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

LOCK_FILE = Path(__file__).parent.parent / "src" / "pilotlog" / "swapa" / "data" / ".ot_scan.lock"
LOG_DIR = Path(__file__).parent.parent / "logs"


def setup_logging():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    if root.handlers:
        return
    root.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    fh = logging.FileHandler(LOG_DIR / "ot_scanner.log")
    fh.setFormatter(fmt)
    root.addHandler(fh)
    # Only add console handler if running interactively (not cron)
    if sys.stdout.isatty():
        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        root.addHandler(sh)


def acquire_lock():
    """Prevent overlapping scanner runs."""
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    lock_fd = open(LOCK_FILE, 'w')
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_fd.write(str(datetime.now()))
        lock_fd.flush()
        return lock_fd
    except BlockingIOError:
        logging.warning("Another scan is already running, exiting")
        sys.exit(0)


def main():
    parser = argparse.ArgumentParser(description="Scan SWAPA Open Time inventory")
    parser.add_argument("--dry-run", action="store_true", help="Don't send Signal alerts")
    parser.add_argument("--threshold", type=int, default=40, help="Min score to alert (0-100)")
    parser.add_argument("--visible", action="store_true", help="Show browser window")
    args = parser.parse_args()

    setup_logging()
    logger = logging.getLogger(__name__)

    lock_fd = acquire_lock()

    try:
        logger.info("Starting OT scan...")
        start = time.time()

        from pilotlog.swapa.opentime import scan_open_time, scan_summary

        results = scan_open_time(
            headless=not args.visible,
            alert_threshold=args.threshold,
            dry_run=args.dry_run,
        )

        elapsed = time.time() - start
        logger.info(f"Scan complete in {elapsed:.1f}s")
        print(scan_summary(results))

        if results.get('errors'):
            for err in results['errors']:
                logger.error(f"Scan error: {err}")

    except Exception as e:
        logger.error(f"Scanner crashed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            lock_fd.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
