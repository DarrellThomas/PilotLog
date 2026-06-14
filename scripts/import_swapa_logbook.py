#!/usr/bin/env python3
"""Auto-import logbook from SWAPA — downloads CSV and feeds it to PilotLog's importer.

Usage:
    python3 import_swapa_logbook.py              # import current year
    python3 import_swapa_logbook.py 2025          # import specific year
    python3 import_swapa_logbook.py --all         # import all available years

Designed to run daily via cron. Duplicate flights are automatically skipped
by the existing SWACSVImporter.
"""

import argparse
import asyncio
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

LOG_DIR = Path(__file__).parent.parent / "logs"
DOWNLOAD_DIR = Path(__file__).parent.parent / "src" / "pilotlog" / "swapa" / "data" / "logbook_downloads"


def setup_logging():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(LOG_DIR / "logbook_import.log"),
            logging.StreamHandler(),
        ],
    )


def download_logbook_csv(year, headless=True):
    """Download logbook CSV from SWAPA for the given year.

    Returns path to downloaded CSV file, or None on failure.
    """
    from playwright.sync_api import sync_playwright
    from pilotlog.swapa.client import TOOLS, _load_cookies, ensure_logged_in

    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

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
            ensure_logged_in(page, TOOLS["logbook"])
            time.sleep(5)

            # Select year (UserName is readonly, pre-filled from login)
            page.select_option("#TimePeriod", str(year))
            time.sleep(0.3)

            # Click "Get Report"
            for btn in page.query_selector_all("button"):
                if "Get Report" in (btn.inner_text() or ""):
                    btn.click()
                    break
            time.sleep(10)

            # Click "CSV" download button
            csv_btn = page.get_by_text("CSV", exact=True).first
            if not csv_btn.is_visible():
                logging.error("CSV button not found or not visible")
                return None

            with page.expect_download(timeout=30000) as dl_info:
                csv_btn.click()

            download = dl_info.value
            save_path = DOWNLOAD_DIR / f"logbook_{year}.csv"
            download.save_as(str(save_path))
            logging.info(f"Downloaded {save_path} ({save_path.stat().st_size} bytes)")
            return save_path

        except Exception as e:
            logging.error(f"Download failed for {year}: {e}")
            return None
        finally:
            browser.close()


async def import_csv_to_db(csv_path):
    """Run the CSV through PilotLog's existing SWA importer."""
    from pilotlog.config import settings
    from pilotlog.database.connection import init_db, get_session
    from pilotlog.importers.swa_csv import SWACSVImporter

    settings.ensure_directories()
    await init_db()

    async with get_session() as session:
        importer = SWACSVImporter()
        result = await importer.import_file(csv_path, session)

    return result


def main():
    parser = argparse.ArgumentParser(description="Import logbook from SWAPA")
    parser.add_argument("year", nargs="?", default=str(datetime.now().year),
                        help="Year to import (default: current)")
    parser.add_argument("--all", action="store_true",
                        help="Import all available years (2011-current)")
    parser.add_argument("--visible", action="store_true",
                        help="Show browser window")
    args = parser.parse_args()

    setup_logging()
    logger = logging.getLogger(__name__)

    if args.all:
        years = list(range(2011, datetime.now().year + 1))
    else:
        years = [int(args.year)]

    for year in years:
        logger.info(f"Processing year {year}...")

        csv_path = download_logbook_csv(year, headless=not args.visible)
        if not csv_path:
            logger.error(f"Failed to download {year}")
            continue

        result = asyncio.run(import_csv_to_db(csv_path))

        logger.info(
            f"{year}: processed={result.rows_processed} "
            f"imported={result.rows_imported} "
            f"duplicates={result.rows_duplicate} "
            f"skipped={result.rows_skipped}"
        )

        if result.rows_imported > 0:
            logger.info(f"  New block time: {result.new_block_formatted}")
            if result.date_range_start and result.date_range_end:
                logger.info(f"  Date range: {result.date_range_start} to {result.date_range_end}")

    logger.info("Done!")


if __name__ == "__main__":
    main()
