"""
FinanceInternRadar - Scraper Engine
Uses httpx + BeautifulSoup to scrape careers pages for new job positions.
"""

import sqlite3
import os
from datetime import datetime, timezone
import re

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "radar.db")

# Try to import optional dependencies
try:
    import httpx
except ImportError:
    httpx = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


class ScraperEngine:
    """Manages all scraping sources and scraped positions."""

    def __init__(self):
        self.conn = get_db()

    def close(self):
        self.conn.close()

    # ─── Source Management ───

    def get_active_sources(self, region=None, source_type=None):
        """Get all active scraping sources, optionally filtered."""
        query = """
            SELECT ss.*, c.name AS company_name, c.region AS company_region
            FROM scraping_sources ss
            JOIN companies c ON ss.company_id = c.id
            WHERE ss.is_active = 1
        """
        params = []
        if region:
            query += " AND ss.region = ?"
            params.append(region)
        if source_type:
            query += " AND ss.source_type = ?"
            params.append(source_type)
        query += " ORDER BY c.name ASC"
        return [dict(r) for r in self.conn.execute(query, params).fetchall()]

    def update_source_status(self, source_id, status, details=None):
        """Update last_scraped_at and last_status for a source."""
        now = datetime.now().isoformat()
        self.conn.execute(
            "UPDATE scraping_sources SET last_scraped_at = ?, last_status = ? WHERE id = ?",
            (now, f"{status}:{details}" if details else status, source_id)
        )
        self.conn.commit()

    # ─── Scraping ───

    def scrape_careers_page(self, url, timeout=15):
        """Scrape a careers page URL and return parsed job listings."""
        if httpx is None or BeautifulSoup is None:
            return None, "Dependencies not installed (httpx, beautifulsoup4)"

        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            }
            resp = httpx.get(url, headers=headers, timeout=timeout, follow_redirects=True)
            resp.raise_for_status()
        except Exception as e:
            return None, f"HTTP error: {e}"

        soup = BeautifulSoup(resp.text, "html.parser")
        listings = []

        # Pattern 1: Common job listing card patterns
        job_cards = soup.select(
            "div[class*='job'], div[class*='position'], li[class*='job'], li[class*='position'], "
            "div[class*='career'], div[class*='opening'], a[class*='job'], "
            "tr[class*='job'], tr[class*='position']"
        )

        if not job_cards:
            # Pattern 2: Look for job-related links
            job_cards = soup.select(
                "a[href*='job'], a[href*='career'], a[href*='position'], a[href*='apply']"
            )

        for card in job_cards[:50]:  # Limit to 50 per page
            text = card.get_text(" ", strip=True)
            if not text or len(text) < 5:
                continue

            # Try to find the link
            link = None
            if card.name == "a" and card.get("href"):
                link = card.get("href")
            else:
                a_tag = card.find("a")
                if a_tag and a_tag.get("href"):
                    link = a_tag.get("href")

            # Handle relative URLs
            if link and not link.startswith("http"):
                if link.startswith("/"):
                    # Parse base URL
                    from urllib.parse import urljoin
                    link = urljoin(url, link)

            listings.append({
                "title": text[:200],  # Use first 200 chars as title
                "snippet": text[:500],
                "url": link,
            })

        return listings, f"Found {len(listings)} potential listings"

    # ─── Position Deduplication & Storage ───

    def classify_job_type(self, title_text):
        """Classify a job title into job_type."""
        t = title_text.lower()
        if "intern" in t and ("graduate" in t or "trainee" in t):
            return "management_trainee"
        if "intern" in t:
            return "intern"
        if "graduate" in t or "campus" in t or "校招" in t:
            return "graduate"
        if "management trainee" in t or "管培" in t:
            return "management_trainee"
        if "full-time" in t or "full time" in t:
            return "full-time"
        # Default: assume intern if still ambiguous
        return "intern"

    def classify_region(self, text, default_region):
        """Heuristic region classification."""
        t = text.lower()
        if any(kw in t for kw in ["new york", "nyc", "san francisco", "chicago", "boston", "usa", "united states"]):
            return "US"
        if any(kw in t for kw in ["london", "uk", "united kingdom", "edinburgh"]):
            return "UK"
        if any(kw in t for kw in ["beijing", "shanghai", "shenzhen", "北京", "上海", "深圳", "china", "中国"]):
            return "CN"
        if any(kw in t for kw in ["hong kong", "hk", "香港"]):
            return "HK"
        if any(kw in t for kw in ["frankfurt", "paris", "zurich", "amsterdam", "berlin", "munich", "milan", "madrid"]):
            return "EU"
        if any(kw in t for kw in ["sydney", "melbourne", "australia", "悉尼", "墨尔本"]):
            return "AU"
        return default_region

    def save_positions(self, source_id, listings, default_region="US"):
        """Deduplicate and save scraped listings to scraped_positions table."""
        now = datetime.now().isoformat()
        new_count = 0

        for item in listings:
            title = item.get("title", "Unknown Position")
            job_type = item.get("job_type") or self.classify_job_type(title)
            location = item.get("location", "")
            region = self.classify_region(f"{title} {location}", default_region)
            posted_date = item.get("posted_date", datetime.now().strftime("%Y-%m-%d"))
            external_url = item.get("url", "")
            snippet = item.get("snippet", "")

            # Check for duplicates (source_id, title, posted_date)
            existing = self.conn.execute(
                "SELECT id FROM scraped_positions WHERE source_id = ? AND title = ? AND posted_date = ?",
                (source_id, title, posted_date)
            ).fetchone()

            if existing:
                continue

            try:
                self.conn.execute(
                    """INSERT INTO scraped_positions
                       (source_id, title, job_type, location, region, posted_date, external_url, description_snippet, is_new, scraped_at)
                       VALUES (?,?,?,?,?,?,?,?,1,?)""",
                    (source_id, title, job_type, location, region, posted_date, external_url, snippet[:500], now)
                )
                new_count += 1
            except sqlite3.IntegrityError:
                continue  # duplicate, skip

        self.conn.commit()
        return new_count

    # ─── Main Scrape All ───

    def scrape_all(self):
        """Scrape all active sources and return summary."""
        sources = self.get_active_sources()
        results = []

        for src in sources:
            src_id = src["id"]
            company_name = src["company_name"]
            source_url = src.get("source_url", "")

            if not source_url:
                self.update_source_status(src_id, "skipped", "No URL configured")
                results.append({
                    "company": company_name,
                    "source_id": src_id,
                    "status": "skipped",
                    "details": "No URL configured",
                    "new_positions": 0,
                })
                continue

            try:
                listings, msg = self.scrape_careers_page(source_url)
                if listings is None:
                    self.update_source_status(src_id, "failed", msg)
                    results.append({
                        "company": company_name,
                        "source_id": src_id,
                        "status": "failed",
                        "details": msg,
                        "new_positions": 0,
                    })
                    continue

                new_count = self.save_positions(src_id, listings, src.get("company_region", "US"))
                status_detail = f"Scraped {len(listings)} listings, {new_count} new"
                self.update_source_status(src_id, "success", status_detail)
                results.append({
                    "company": company_name,
                    "source_id": src_id,
                    "status": "success",
                    "details": status_detail,
                    "new_positions": new_count,
                })
            except Exception as e:
                self.update_source_status(src_id, "failed", str(e))
                results.append({
                    "company": company_name,
                    "source_id": src_id,
                    "status": "failed",
                    "details": str(e),
                    "new_positions": 0,
                })

        return results

    # ─── Query Methods ───

    def get_scraped_positions(self, region=None, job_type=None, verified=None, is_new=None, limit=100):
        """Get scraped positions with optional filters."""
        query = """
            SELECT sp.*, ss.source_url, ss.company_id, c.name AS company_name
            FROM scraped_positions sp
            LEFT JOIN scraping_sources ss ON sp.source_id = ss.id
            LEFT JOIN companies c ON ss.company_id = c.id
            WHERE 1=1
        """
        params = []
        if region:
            query += " AND sp.region = ?"
            params.append(region)
        if job_type:
            query += " AND sp.job_type = ?"
            params.append(job_type)
        if verified is not None:
            query += " AND sp.is_verified = ?"
            params.append(int(verified))
        if is_new is not None:
            query += " AND sp.is_new = ?"
            params.append(int(is_new))
        query += " ORDER BY sp.scraped_at DESC LIMIT ?"
        params.append(limit)

        return [dict(r) for r in self.conn.execute(query, params).fetchall()]

    def verify_position(self, position_id, verified=True):
        """Mark a scraped position as verified or not."""
        self.conn.execute(
            "UPDATE scraped_positions SET is_verified = ?, is_new = 0 WHERE id = ?",
            (int(verified), position_id)
        )
        self.conn.commit()

    def dismiss_position(self, position_id):
        """Dismiss a scraped position (mark as not new, not verified)."""
        self.conn.execute(
            "UPDATE scraped_positions SET is_new = 0, is_verified = 0 WHERE id = ?",
            (position_id,)
        )
        self.conn.commit()

    def get_scraping_status(self):
        """Get overall scraping status summary."""
        # Counts
        total_sources = self.conn.execute(
            "SELECT COUNT(*) FROM scraping_sources WHERE is_active = 1"
        ).fetchone()[0]
        total_positions = self.conn.execute(
            "SELECT COUNT(*) FROM scraped_positions"
        ).fetchone()[0]
        new_positions = self.conn.execute(
            "SELECT COUNT(*) FROM scraped_positions WHERE is_new = 1"
        ).fetchone()[0]
        verified_positions = self.conn.execute(
            "SELECT COUNT(*) FROM scraped_positions WHERE is_verified = 1"
        ).fetchone()[0]
        recent = self.conn.execute(
            "SELECT * FROM scraping_sources ORDER BY last_scraped_at DESC LIMIT 20"
        ).fetchall()

        return {
            "total_sources": total_sources,
            "total_positions": total_positions,
            "new_positions": new_positions,
            "verified_positions": verified_positions,
            "recent_sources": [dict(r) for r in recent],
        }


# Singleton
_engine = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = ScraperEngine()
    return _engine


if __name__ == "__main__":
    engine = ScraperEngine()
    print(f"Active sources: {len(engine.get_active_sources())}")
    status = engine.get_scraping_status()
    print(f"Total scraped positions: {status['total_positions']}, New: {status['new_positions']}")
    engine.close()
