"""SWAPA.org browser automation — login, page scraping, tool access.

Uses Playwright (headless Chromium) to interact with swapa.org.
Credentials: SWAPA_ID and SWAPA_pass from ~/.env

WARNING: This module ONLY accesses swapa.org (the union website).
         It MUST NEVER access swacrew.com or any SWA corporate system.
"""

import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

DATA_DIR = Path(__file__).parent / "data"
COOKIES_FILE = DATA_DIR / "swapa_cookies.json"
ENV_FILE = Path.home() / ".env"

BLOCKED_DOMAINS = {"swacrew.com", "www.swacrew.com", "swalife.com", "www.swalife.com"}

# Known SWAPA tool URLs
TOOLS = {
    "open_time": "https://www.swapa.org/internal/resources/tools/open-time-inventory/",
    "ttga": "https://www.swapa.org/internal/resources/tools/ttga-inventory/",
    "ot_awards": "https://www.swapa.org/internal/resources/tools/open-time-awards/",
    "ot_forecast": "https://www.swapa.org/internal/resources/tools/ot-rsv-forecast/",
    "linetuner": "https://www.swapa.org/internal/resources/tools/linetuner/",
    "rco": "https://www.swapa.org/internal/resources/tools/rco/",
    "seniority_list": "https://www.swapa.org/internal/resources/tools/seniority-list/",
    "seniority_snapshot": "https://www.swapa.org/internal/resources/tools/seniority-snapshot/",
    "pay_audit": "https://www.swapa.org/internal/resources/tools/individual-pay-audit-c2020/",
    "vacancy": "https://www.swapa.org/internal/resources/tools/vacancy-award-projection/",
    "blank_line": "https://www.swapa.org/internal/resources/tools/blank-line-projection/",
    "line_award_pay": "https://www.swapa.org/internal/resources/tools/line-award-pay/",
    "who_seat": "https://www.swapa.org/internal/resources/tools/who-was-in-my-seat/",
    "logbook": "https://www.swapa.org/internal/resources/tools/logbook-export/",
    "sched_handbook": "https://www.swapa.org/internal/resources/tools/scheduling-handbook-html/",
}


def assert_safe_url(url):
    """Raise if URL targets a blocked domain."""
    host = urlparse(url).hostname or ""
    if host in BLOCKED_DOMAINS:
        raise RuntimeError(f"BLOCKED: refusing to access {host} -- corporate systems are off-limits")


def load_credentials():
    """Read SWAPA_ID and SWAPA_pass from ~/.env."""
    creds = {}
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line.startswith('#') or '=' not in line:
                continue
            key, val = line.split('=', 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key in ('SWAPA_ID', 'SWAPA_pass'):
                creds[key] = val
    if 'SWAPA_ID' not in creds or 'SWAPA_pass' not in creds:
        raise RuntimeError("SWAPA_ID and SWAPA_pass must be set in ~/.env")
    return creds


def _save_cookies(context):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    cookies = context.cookies()
    with open(COOKIES_FILE, 'w') as f:
        json.dump(cookies, f, indent=2)


def _load_cookies(context):
    if not COOKIES_FILE.exists():
        return False
    age_sec = time.time() - COOKIES_FILE.stat().st_mtime
    if age_sec > 4 * 3600:
        return False
    try:
        with open(COOKIES_FILE) as f:
            cookies = json.load(f)
        context.add_cookies(cookies)
        return True
    except Exception:
        return False


def create_browser(playwright, headless=True):
    """Launch Chromium and create a context with optional saved cookies."""
    browser = playwright.chromium.launch(headless=headless)
    context = browser.new_context(
        user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        viewport={"width": 1280, "height": 900},
        ignore_https_errors=True,
    )
    _load_cookies(context)
    return browser, context


def do_b2c_login(page):
    """Handle the Azure AD B2C login form at login.swapa.org."""
    creds = load_credentials()
    emp_id = creds['SWAPA_ID'].lstrip('eE')
    password = creds['SWAPA_pass']

    print("  [swapa] Filling B2C login...", file=sys.stderr)
    page.fill('#signInName', emp_id)
    time.sleep(0.3)
    page.click('#password')
    time.sleep(0.3)
    page.keyboard.type(password, delay=30)

    try:
        with page.expect_navigation(timeout=30000, wait_until="domcontentloaded"):
            page.click('button#next')
    except Exception:
        pass
    time.sleep(3)


def ensure_logged_in(page, target_url):
    """Navigate to target_url, handle B2C login if redirected."""
    assert_safe_url(target_url)
    page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
    time.sleep(3)

    if 'login.swapa.org' in page.url:
        do_b2c_login(page)

    current = page.url
    if 'swapa.org' in current and 'login.swapa.org' not in current:
        _save_cookies(page.context)
    else:
        err = page.query_selector('#errorMessage, .error, .alert-danger')
        if err and err.is_visible():
            raise RuntimeError(f"SWAPA login failed: {err.inner_text().strip()}")

    return page


def get_page_text(page, max_chars=50000):
    """Get body text from current page."""
    body = page.query_selector('body')
    if body:
        return body.inner_text()[:max_chars]
    return ""


def get_page_tables(page):
    """Extract all HTML tables from current page as list of list-of-dicts."""
    return page.evaluate("""() => {
        const tables = [];
        for (const table of document.querySelectorAll('table')) {
            const headers = [];
            const headerRow = table.querySelector('thead tr, tr:first-child');
            if (headerRow) {
                for (const th of headerRow.querySelectorAll('th, td')) {
                    headers.push(th.innerText.trim());
                }
            }
            const rows = [];
            const bodyRows = table.querySelectorAll('tbody tr, tr');
            for (let i = 0; i < bodyRows.length; i++) {
                const cells = bodyRows[i].querySelectorAll('td');
                if (cells.length === 0) continue;
                const row = {};
                for (let j = 0; j < cells.length; j++) {
                    const key = j < headers.length ? headers[j] : `col_${j}`;
                    row[key] = cells[j].innerText.trim();
                }
                rows.push(row);
            }
            if (rows.length > 0) {
                tables.push({headers, rows});
            }
        }
        return tables;
    }""")
