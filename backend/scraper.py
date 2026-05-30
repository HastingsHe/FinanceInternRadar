"""
Lightweight scraper for monitoring company careers pages.
Uses httpx + BeautifulSoup. Runs periodically via APScheduler.
"""

import httpx
from bs4 import BeautifulSoup
import sqlite3
import os
import re
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "radar.db")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

KEYWORDS = [
    "summer intern", "summer analyst", "internship", "graduate program",
    "campus recruiting", "early careers", "students", "quantitative intern",
    "investment banking intern", "summer associate", "off-cycle intern",
    "spring intern", "placement year", "industrial placement",
]


def log_scrape(company_id, status, details=""):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO scrape_logs (company_id, status, details) VALUES (?, ?, ?)",
        (company_id, status, details[:500])
    )
    conn.commit()
    conn.close()


def scrape_company(company_id, name, careers_url):
    """Scrape a single company's careers page for internship openings."""
    try:
        with httpx.Client(timeout=15, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
            resp = client.get(careers_url)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            # Get all text, normalize
            text = soup.get_text(separator=" ", strip=True).lower()

            # Count keyword matches
            matches = []
            for kw in KEYWORDS:
                if kw in text:
                    matches.append(kw)

            # Also check for specific date patterns (e.g., "applications open July 2026")
            date_patterns = re.findall(
                r'(applications?\s*(?:open|close|open\s*(?:on|in))?\s*'
                r'(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|'
                r'jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s*\d{4})',
                text, re.IGNORECASE
            )

            status = "success" if matches else "no_change"
            details = f"Found {len(matches)} keyword matches: {', '.join(matches[:5])}"
            if date_patterns:
                details += f" | Date patterns: {', '.join(date_patterns[:3])}"

            log_scrape(company_id, status, details)
            return {"company": name, "status": status, "matches": len(matches), "details": details}

    except Exception as e:
        log_scrape(company_id, "failed", str(e))
        return {"company": name, "status": "failed", "error": str(e)}


def scrape_all():
    """Scrape all companies in the database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    companies = [dict(r) for r in conn.execute(
        "SELECT id, name, careers_url FROM companies WHERE careers_url IS NOT NULL"
    ).fetchall()]
    conn.close()

    results = []
    for c in companies:
        result = scrape_company(c["id"], c["name"], c["careers_url"])
        results.append(result)
        print(f"  [{result['status']}] {result['company']}: {result.get('details', result.get('error', ''))}")

    return results


if __name__ == "__main__":
    from database import init_db
    init_db()
    results = scrape_all()
    success = sum(1 for r in results if r["status"] == "success")
    print(f"\nScraped {len(results)} companies: {success} success, {len(results) - success} failed/no-change")