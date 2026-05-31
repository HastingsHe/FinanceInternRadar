"""
FinanceInternRadar - Scraper Engine
Uses httpx + BeautifulSoup to scrape careers pages for new job positions.
Enhanced with FinTech startup sources and job board aggregation.
"""

import sqlite3
import os
import json
from datetime import datetime, timezone, timedelta
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

# ─── FinTech Startup Sources ───
# Career pages of notable FinTech startups

FINTECH_STARTUPS = [
    # US FinTech
    ("Stripe", "US", "https://stripe.com/jobs/search?q=intern", "FinTech",
     "Online payment processing platform, valued at $65B+"),
    ("Plaid", "US", "https://plaid.com/careers/", "FinTech",
     "Financial data connectivity platform connecting apps to bank accounts"),
    ("Chime", "US", "https://www.chime.com/careers/", "FinTech",
     "Neobank with 20M+ users, no-fee mobile banking"),
    ("Robinhood", "US", "https://careers.robinhood.com/", "FinTech",
     "Commission-free trading platform, democratizing finance"),
    ("Coinbase", "US", "https://www.coinbase.com/careers/positions", "FinTech",
     "Largest US cryptocurrency exchange, publicly traded"),
    ("Ripple", "US", "https://ripple.com/careers/", "FinTech",
     "Enterprise blockchain and crypto solutions for cross-border payments"),
    ("Brex", "US", "https://www.brex.com/careers/", "FinTech",
     "Corporate credit card and spend management for startups"),
    ("Affirm", "US", "https://www.affirm.com/careers", "FinTech",
     "Buy-now-pay-later fintech, publicly traded"),
    ("SoFi", "US", "https://www.sofi.com/careers/", "FinTech",
     "All-in-one personal finance platform (banking, investing, lending)"),

    # UK/Europe FinTech
    ("Revolut", "UK", "https://www.revolut.com/careers/", "FinTech",
     "Global neobank and financial super-app with 45M+ customers"),
    ("Monzo", "UK", "https://monzo.com/careers/", "FinTech",
     "UK digital challenger bank with distinctive coral cards"),
    ("Klarna", "EU", "https://www.klarna.com/careers/", "FinTech",
     "Swedish BNPL giant, one of Europe's most valuable fintechs"),
    ("Wise", "UK", "https://www.wise.jobs/", "FinTech",
     "International money transfer at real exchange rate, publicly traded"),
    ("Checkout.com", "UK", "https://www.checkout.com/careers", "FinTech",
     "Global payment processing platform, valued at $40B"),
    ("Adyen", "EU", "https://www.adyen.com/careers", "FinTech",
     "Dutch payment company powering payments for Netflix, Spotify, Uber"),

    # Asia-Pacific FinTech
    ("Airwallex", "AU", "https://www.airwallex.com/careers", "FinTech",
     "Cross-border payments and financial infrastructure for businesses"),
    ("Afterpay", "AU", "https://www.afterpay.com/careers", "FinTech",
     "Australian BNPL pioneer, acquired by Block (Square)"),
]

# FinTech job boards and aggregators
FINTECH_JOB_BOARDS = [
    {
        "name": "Otta (FinTech filter)",
        "url": "https://otta.com/jobs/fintech",
        "region": "US",
        "type": "aggregator",
    },
    {
        "name": "Built In NYC FinTech",
        "url": "https://www.builtinnyc.com/jobs/fintech",
        "region": "US",
        "type": "aggregator",
    },
    {
        "name": "TrueUp FinTech Jobs",
        "url": "https://www.trueup.io/jobs?q=fintech+intern",
        "region": "US",
        "type": "aggregator",
    },
]

# Lever / Greenhouse API patterns used by many FinTech startups
LEVER_API_PATTERN = "{base}/.json"
GREENHOUSE_API_PATTERN = "{base}/jobs.json"


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

    # ─── FinTech Startup Methods ───

    def ensure_fintech_companies(self):
        """Ensure all FinTech startup companies exist in the companies table."""
        now = datetime.now().isoformat()
        added = 0

        for name, region, url, category, desc in FINTECH_STARTUPS:
            existing = self.conn.execute(
                "SELECT id FROM companies WHERE name = ?", (name,)
            ).fetchone()
            if existing:
                continue

            cursor = self.conn.cursor()
            cursor.execute(
                """INSERT INTO companies (name, region, category, description, website, careers_url, is_featured)
                   VALUES (?, ?, ?, ?, ?, ?, 1)""",
                (name, region, category, desc, url, url)
            )
            company_id = cursor.lastrowid

            # Also add as scraping source
            cursor.execute(
                "INSERT INTO scraping_sources (company_id, source_url, source_type, region, is_active) VALUES (?, ?, 'careers_page', ?, 1)",
                (company_id, url, region)
            )

            added += 1

        if added:
            self.conn.commit()
        return added

    def scrape_fintech_careers(self):
        """Scrape FinTech startup career pages. Many use Lever/Greenhouse ATS."""
        if httpx is None or BeautifulSoup is None:
            return [], "Dependencies not installed"

        all_listings = []
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json,text/html,application/xhtml+xml",
        }

        for name, region, url, category, desc in FINTECH_STARTUPS:
            listings = []

            # Try Lever API first (many FinTechs use Lever)
            if "lever.co" in url or "/jobs" in url:
                try:
                    # Try common API patterns
                    for api_url in [
                        url.rstrip("/") + "/.json" if "lever.co" in url else None,
                        url.rstrip("/") + "/jobs.json" if "greenhouse.io" in url else None,
                    ]:
                        if api_url is None:
                            continue
                        try:
                            resp = httpx.get(api_url, headers=headers, timeout=10, follow_redirects=True)
                            if resp.status_code == 200 and "application/json" in resp.headers.get("content-type", ""):
                                data = resp.json()
                                for job in (data if isinstance(data, list) else data.get("postings", data.get("jobs", []))):
                                    title = job.get("text", job.get("title", ""))
                                    if not title:
                                        continue
                                    if any(kw in title.lower() for kw in ["intern", "graduate", "campus", "new grad", "entry"]):
                                        job_url = job.get("hostedUrl", job.get("applyUrl", job.get("url", "")))
                                        listings.append({
                                            "title": title,
                                            "snippet": f"{name} - {title}",
                                            "url": job_url,
                                            "job_type": self.classify_job_type(title),
                                            "location": job.get("categories", {}).get("location", "") if isinstance(job.get("categories"), dict) else "",
                                            "posted_date": datetime.now().strftime("%Y-%m-%d"),
                                        })
                        except Exception:
                            continue
                except Exception:
                    pass

            # Fall back to HTML scraping
            if not listings:
                try:
                    html_listings, _ = self.scrape_careers_page(url, timeout=10)
                    if html_listings:
                        for item in html_listings:
                            title = item.get("title", "")
                            # Filter for intern/new grad
                            if any(kw in title.lower() for kw in ["intern", "graduate", "campus", "new grad", "entry"]):
                                item["job_type"] = self.classify_job_type(title)
                                item["posted_date"] = datetime.now().strftime("%Y-%m-%d")
                                listings.append(item)
                except Exception:
                    pass

            if listings:
                all_listings.append({
                    "company_name": name,
                    "region": region,
                    "listings": listings,
                })

        return all_listings

    def scrape_job_boards(self):
        """Scrape FinTech-focused job board aggregators for intern positions."""
        if httpx is None or BeautifulSoup is None:
            return [], "Dependencies not installed"

        all_listings = []
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml",
        }

        for board in FINTECH_JOB_BOARDS:
            try:
                resp = httpx.get(board["url"], headers=headers, timeout=15, follow_redirects=True)
                resp.raise_for_status()
            except Exception:
                continue

            soup = BeautifulSoup(resp.text, "html.parser")

            # Look for job cards/listings
            job_elements = soup.select(
                "div[class*='job-card'], div[class*='JobCard'], "
                "li[class*='job'], a[class*='job'], "
                "div[class*='opportunity'], "
                "div[class*='position'], div[class*='listing']"
            )

            for elem in job_elements[:30]:
                text = elem.get_text(" ", strip=True)
                if not text or len(text) < 10:
                    continue

                link = None
                if elem.name == "a" and elem.get("href"):
                    link = elem.get("href")
                else:
                    a_tag = elem.find("a")
                    if a_tag and a_tag.get("href"):
                        link = a_tag.get("href")

                if link and not link.startswith("http"):
                    from urllib.parse import urljoin
                    link = urljoin(board["url"], link)

                title = text[:200]
                if any(kw in title.lower() for kw in ["intern", "graduate", "campus", "new grad", "entry"]):
                    all_listings.append({
                        "title": title,
                        "snippet": text[:500],
                        "url": link,
                        "region": board["region"],
                        "source_name": board["name"],
                        "job_type": self.classify_job_type(title),
                        "posted_date": datetime.now().strftime("%Y-%m-%d"),
                    })

        return all_listings

    def _save_fintech_listings(self, fintech_results):
        """Save FinTech-scraped listings into the database."""
        now = datetime.now().isoformat()
        total_new = 0

        for result in fintech_results:
            company_name = result["company_name"]
            region = result["region"]
            listings = result["listings"]

            # Find or create the company's scraping source
            company = self.conn.execute(
                "SELECT id FROM companies WHERE name = ?", (company_name,)
            ).fetchone()
            if not company:
                continue

            # Get or create scraping source
            source = self.conn.execute(
                "SELECT id FROM scraping_sources WHERE company_id = ? AND source_type = 'careers_page'",
                (company["id"],)
            ).fetchone()

            if not source:
                cursor = self.conn.cursor()
                cursor.execute(
                    "INSERT INTO scraping_sources (company_id, source_url, source_type, region, is_active) VALUES (?, '', 'careers_page', ?, 1)",
                    (company["id"], region)
                )
                source_id = cursor.lastrowid
                self.conn.commit()
            else:
                source_id = source["id"]

            for item in listings:
                title = item.get("title", "Unknown Position")
                job_type = item.get("job_type", "intern")
                posted_date = item.get("posted_date", datetime.now().strftime("%Y-%m-%d"))
                external_url = item.get("url", "")

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
                        (source_id, title, job_type, "", region, posted_date, external_url, title[:500], now)
                    )
                    total_new += 1
                except sqlite3.IntegrityError:
                    continue

        if total_new > 0:
            self.conn.commit()
        return total_new

    # ─── Main Scrape All ───

    def scrape_all(self):
        """Scrape all active sources and return summary.
        Now includes FinTech startup career pages and job board aggregators.
        """
        results = []
        total_new_positions = 0

        # Phase 1: Ensure FinTech companies exist in DB
        fintech_added = self.ensure_fintech_companies()

        # Phase 2: Scrape existing sources (traditional finance companies)
        sources = self.get_active_sources()
        for src in sources:
            src_id = src["id"]
            company_name = src["company_name"]
            source_url = src.get("source_url", "")

            # Skip FinTech companies here — they get scraped via dedicated method
            if src.get("company_region") and src.get("company_name") in [s[0] for s in FINTECH_STARTUPS]:
                continue

            if not source_url:
                self.update_source_status(src_id, "skipped", "No URL configured")
                results.append({
                    "company": company_name,
                    "source_id": src_id,
                    "status": "skipped",
                    "details": "No URL configured",
                    "new_positions": 0,
                    "source_type": "traditional",
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
                        "source_type": "traditional",
                    })
                    continue

                new_count = self.save_positions(src_id, listings, src.get("company_region", "US"))
                total_new_positions += new_count
                status_detail = f"Scraped {len(listings)} listings, {new_count} new"
                self.update_source_status(src_id, "success", status_detail)
                results.append({
                    "company": company_name,
                    "source_id": src_id,
                    "status": "success",
                    "details": status_detail,
                    "new_positions": new_count,
                    "source_type": "traditional",
                })
            except Exception as e:
                self.update_source_status(src_id, "failed", str(e))
                results.append({
                    "company": company_name,
                    "source_id": src_id,
                    "status": "failed",
                    "details": str(e),
                    "new_positions": 0,
                    "source_type": "traditional",
                })

        # Phase 3: Scrape FinTech startup career pages
        try:
            fintech_results = self.scrape_fintech_careers()
            fintech_new = self._save_fintech_listings(fintech_results)
            total_new_positions += fintech_new
            results.append({
                "company": "FinTech Startups (aggregate)",
                "source_id": None,
                "status": "success",
                "details": f"Scraped {len(fintech_results)} FinTech companies, {fintech_new} new positions",
                "new_positions": fintech_new,
                "source_type": "fintech_startup",
            })
        except Exception as e:
            results.append({
                "company": "FinTech Startups (aggregate)",
                "source_id": None,
                "status": "failed",
                "details": str(e),
                "new_positions": 0,
                "source_type": "fintech_startup",
            })

        # Phase 4: Scrape job board aggregators
        try:
            board_listings = self.scrape_job_boards()
            board_count = len(board_listings)
            if board_listings and board_count > 0:
                # Save job board listings under a virtual "FinTech Job Boards" source
                # First ensure a virtual source exists
                virtual_source = self.conn.execute(
                    "SELECT id FROM scraping_sources WHERE source_type = 'careers_page' AND source_url LIKE '%aggregator%' LIMIT 1"
                ).fetchone()
                if not virtual_source:
                    # Use first FinTech company as anchor
                    first_fintech = self.conn.execute(
                        "SELECT id FROM companies WHERE category = 'FinTech' LIMIT 1"
                    ).fetchone()
                    if first_fintech:
                        cursor = self.conn.cursor()
                        cursor.execute(
                            "INSERT INTO scraping_sources (company_id, source_url, source_type, region, is_active) VALUES (?, 'aggregator://fintech-boards', 'careers_page', 'US', 1)",
                            (first_fintech["id"],)
                        )
                        virtual_id = cursor.lastrowid
                        self.conn.commit()
                    else:
                        virtual_id = None
                else:
                    virtual_id = virtual_source["id"]

                if virtual_id:
                    board_new = self.save_positions(virtual_id, board_listings, "US")
                    total_new_positions += board_new
                    results.append({
                        "company": "FinTech Job Boards",
                        "source_id": virtual_id,
                        "status": "success",
                        "details": f"Scraped {board_count} listings, {board_new} new",
                        "new_positions": board_new,
                        "source_type": "job_board",
                    })
                else:
                    results.append({
                        "company": "FinTech Job Boards",
                        "source_id": None,
                        "status": "skipped",
                        "details": "No FinTech companies in DB to anchor",
                        "new_positions": 0,
                        "source_type": "job_board",
                    })
            else:
                results.append({
                    "company": "FinTech Job Boards",
                    "source_id": None,
                    "status": "skipped",
                    "details": "No listings found",
                    "new_positions": 0,
                    "source_type": "job_board",
                })
        except Exception as e:
            results.append({
                "company": "FinTech Job Boards",
                "source_id": None,
                "status": "failed",
                "details": str(e),
                "new_positions": 0,
                "source_type": "job_board",
            })

        # Summary
        results.insert(0, {
            "company": "__SUMMARY__",
            "source_id": None,
            "status": "summary",
            "details": "Total new positions across all sources",
            "new_positions": total_new_positions,
            "source_type": "summary",
            "fintech_companies_added": fintech_added,
        })

        # Phase 5: Update predictions from official career pages
        try:
            official_result = self.update_predictions_from_official()
            results.append({
                "company": "__OFFICIAL_DATES__",
                "source_id": None,
                "status": "success",
                "details": f"Official date scraping: {official_result['updated']} updated, "
                           f"{official_result['skipped']} skipped, "
                           f"{official_result['failed']} failed",
                "new_positions": 0,
                "source_type": "official_dates",
                "official_updates": official_result,
            })
        except Exception as e:
            results.append({
                "company": "__OFFICIAL_DATES__",
                "source_id": None,
                "status": "failed",
                "details": str(e),
                "new_positions": 0,
                "source_type": "official_dates",
            })

        return results

    # ─── Official Date Scraping ───

    def _parse_date_from_text(self, text):
        """Extract open/close dates from text using common patterns.

        Returns list of (date_str, date_type) tuples where date_type is 'open' or 'close'.
        """
        if not text:
            return []

        results = []
        date_patterns = [
            # "Applications open: July 1, 2026"
            (r'(?:applications?\s*(?:open|start)|open(?:ing)?\s*date)\s*:?\s*'
             r'([A-Z][a-z]+)\s*(\d{1,2}),?\s*(\d{4})', 'open'),
            # "Apply by September 30, 2026" / "Application deadline: October 15, 2026"
            (r'(?:apply\s*(?:by|before|deadline)|deadline|closing\s*date)\s*:?\s*'
             r'([A-Z][a-z]+)\s*(\d{1,2}),?\s*(\d{4})', 'close'),
            # ISO dates: open/start: 2026-07-01
            (r'(?:open|start|begin)\s*(?:ing)?\s*(?:date)?\s*:?\s*(\d{4}-\d{2}-\d{2})', 'open'),
            # ISO dates: close/deadline: 2026-10-15
            (r'(?:close|end|deadline)\s*(?:date)?\s*:?\s*(\d{4}-\d{2}-\d{2})', 'close'),
            # "Open: June 2026" (month-year only, use 1st of month)
            (r'(?:applications?\s*open|open(?:ing)?)\s*:?\s*'
             r'([A-Z][a-z]+)\s*,?\s*(\d{4})', 'open'),
            # "2026 Summer Internship - Apply by September 30, 2026"
            (r'(\d{4})\s*(?:Summer|Spring|Fall|Winter|Off-Cycle)\s*(?:Intern|Analyst|Associate).*?'
             r'(?:apply\s*(?:by|before)|deadline)\s*:?\s*'
             r'([A-Z][a-z]+)\s*(\d{1,2}),?\s*(\d{4})', 'close'),
        ]

        month_map = {
            "january": 1, "february": 2, "march": 3, "april": 4,
            "may": 5, "june": 6, "july": 7, "august": 8,
            "september": 9, "october": 10, "november": 11, "december": 12,
        }

        for pattern, date_type in date_patterns:
            for m in re.finditer(pattern, text, re.IGNORECASE):
                groups = m.groups()
                try:
                    if len(groups) == 1:
                        # ISO date: 2026-07-01
                        results.append((groups[0], date_type))
                    elif len(groups) == 2:
                        # Month Year
                        month_name, year_str = groups
                        month = month_map.get(month_name.lower())
                        if month:
                            results.append(
                                (f"{year_str}-{month:02d}-01", date_type))
                    elif len(groups) == 3:
                        # Month Day Year or Year Month Day
                        a, b, c = groups
                        if a.isdigit() and len(a) == 4:
                            # Year, Month_name, Day
                            month = month_map.get(b.lower())
                            if month:
                                results.append(
                                    (f"{a}-{month:02d}-{int(c):02d}", date_type))
                        else:
                            # Month_name, Day, Year
                            month = month_map.get(a.lower())
                            if month:
                                results.append(
                                    (f"{c}-{month:02d}-{int(b):02d}", date_type))
                    elif len(groups) == 4:
                        # Year, Month_name, Day, Year (4-group pattern)
                        year1, month_name, day_str, year2 = groups
                        month = month_map.get(month_name.lower())
                        if month:
                            results.append(
                                (f"{year1}-{month:02d}-{int(day_str):02d}", date_type))
                except (ValueError, KeyError):
                    continue

        return results

    def _try_ats_json_api(self, careers_url):
        """Try to fetch structured data from common ATS JSON APIs (Lever, Greenhouse).

        Returns list of dicts with keys: title, open_date, close_date, url.
        """
        if httpx is None:
            return None

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json",
        }
        listings = []

        # ── Lever API ──
        # Patterns: https://jobs.lever.co/{slug} or https://www.lever.co/{slug}
        lever_match = re.search(
            r'(?:jobs\.lever\.co|lever\.co)/([a-zA-Z0-9_-]+)', careers_url)
        if lever_match:
            slug = lever_match.group(1)
            api_url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
            try:
                resp = httpx.get(api_url, headers=headers, timeout=15,
                                 follow_redirects=True)
                if resp.status_code == 200:
                    data = resp.json()
                    for posting in (data if isinstance(data, list) else []):
                        title = posting.get("text", posting.get("title", ""))
                        created = posting.get("createdAt")
                        hosted_url = posting.get("hostedUrl", posting.get("applyUrl", ""))
                        if title and any(kw in title.lower() for kw in
                                         ["intern", "graduate", "campus", "summer", "analyst"]):
                            listing = {
                                "title": title,
                                "url": hosted_url,
                                "open_date": None,
                                "close_date": None,
                            }
                            if created:
                                from datetime import timezone as tz
                                listing["open_date"] = datetime.fromtimestamp(
                                    created / 1000, tz.utc).strftime("%Y-%m-%d")
                            listings.append(listing)
            except Exception:
                pass

        # ── Greenhouse API ──
        gh_match = re.search(
            r'boards\.greenhouse\.io/([a-zA-Z0-9_-]+)', careers_url)
        if gh_match:
            board_token = gh_match.group(1)
            api_url = f"https://boards.greenhouse.io/{board_token}/jobs.json"
            try:
                resp = httpx.get(api_url, headers=headers, timeout=15,
                                 follow_redirects=True)
                if resp.status_code == 200:
                    data = resp.json()
                    for job in data.get("jobs", []):
                        title = job.get("title", "")
                        updated = job.get("updated_at", "")
                        absolute_url = job.get("absolute_url", "")
                        if title and any(kw in title.lower() for kw in
                                         ["intern", "graduate", "campus", "summer", "analyst"]):
                            listing = {
                                "title": title,
                                "url": absolute_url,
                                "open_date": None,
                                "close_date": None,
                            }
                            if updated:
                                listing["open_date"] = updated[:10]
                            listings.append(listing)
            except Exception:
                pass

        return listings if listings else None

    def scrape_official_dates(self, company_id):
        """Scrape official opening dates from a company's careers page.

        Returns dict with keys: company_id, status, open_dates_found, positions_found.
        """
        conn = get_db()
        company = conn.execute(
            "SELECT id, name, careers_url, region FROM companies WHERE id = ?",
            (company_id,)
        ).fetchone()
        conn.close()

        if not company or not company["careers_url"]:
            return {"company_id": company_id, "status": "no_careers_url",
                    "open_dates_found": 0, "positions_found": 0}

        careers_url = company["careers_url"]
        found_dates = []
        all_listings = []

        # Phase 1: Try ATS JSON APIs (Lever, Greenhouse) — most reliable
        api_listings = self._try_ats_json_api(careers_url)
        if api_listings:
            all_listings = api_listings
            # Try to extract dates from individual posting URLs
            for listing in api_listings:
                if listing.get("url"):
                    try:
                        html_listings, _ = self.scrape_careers_page(
                            listing["url"], timeout=10)
                        if html_listings:
                            for item in html_listings:
                                snippet = item.get("snippet", "")
                                dates = self._parse_date_from_text(snippet)
                                for d, d_type in dates:
                                    found_dates.append({
                                        "program": listing.get("title", ""),
                                        "date": d,
                                        "type": d_type,
                                    })
                    except Exception:
                        pass

        # Phase 2: HTML scraping of main careers page
        if not all_listings:
            try:
                html_listings, msg = self.scrape_careers_page(
                    careers_url, timeout=15)
                if html_listings:
                    all_listings = [
                        {"title": item.get("title", ""),
                         "url": item.get("url", ""),
                         "open_date": None, "close_date": None}
                        for item in html_listings
                    ]
                    # Parse dates from snippets
                    for item in html_listings:
                        snippet = item.get("snippet", "")
                        dates = self._parse_date_from_text(snippet)
                        for d, d_type in dates:
                            found_dates.append({
                                "program": item.get("title", "")[:100],
                                "date": d,
                                "type": d_type,
                            })
            except Exception:
                pass

        # Phase 3: Also parse the main page HTML text for program-level dates
        if not found_dates and httpx is not None and BeautifulSoup is not None:
            try:
                headers = {
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/125.0.0.0 Safari/537.36"
                    ),
                    "Accept": "text/html,application/xhtml+xml",
                }
                resp = httpx.get(careers_url, headers=headers,
                                 timeout=15, follow_redirects=True)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "html.parser")
                # Get all text from the page
                page_text = soup.get_text(" ", strip=True)
                dates = self._parse_date_from_text(page_text)
                for d, d_type in dates:
                    found_dates.append({
                        "program": f"{company['name']} (from careers page)",
                        "date": d,
                        "type": d_type,
                    })
            except Exception:
                pass

        return {
            "company_id": company_id,
            "company_name": company["name"],
            "status": "success" if found_dates else "no_dates_found",
            "open_dates_found": len(found_dates),
            "positions_found": len(all_listings),
            "dates": found_dates[:20],
        }

    def update_predictions_from_official(self):
        """Update low-confidence predictions with official dates from careers pages.

        Iterates positions with confidence < 0.6 or NULL predicted_open_date,
        attempts to scrape official dates, and updates if found.
        """
        conn = get_db()

        # Find positions needing official verification
        positions = conn.execute("""
            SELECT jp.id, jp.company_id, jp.program_name, jp.predicted_open_date,
                   jp.confidence, c.name as company_name, c.careers_url
            FROM job_positions jp
            JOIN companies c ON jp.company_id = c.id
            WHERE jp.year = 2026
              AND (jp.confidence < 0.6 OR jp.predicted_open_date IS NULL)
              AND c.careers_url IS NOT NULL AND c.careers_url != ''
            ORDER BY jp.confidence ASC
        """).fetchall()

        updated = 0
        failed = 0
        skipped = 0

        for pos in positions:
            pos_dict = dict(pos)
            company_id = pos_dict["company_id"]

            # Only scrape each company's careers page once per run
            if not hasattr(self, '_official_cache'):
                self._official_cache = {}
            if company_id not in self._official_cache:
                self._official_cache[company_id] = self.scrape_official_dates(
                    company_id)

            result = self._official_cache[company_id]
            dates = result.get("dates", [])

            if not dates:
                skipped += 1
                continue

            # Try to match: find dates that look like they belong to this program
            program_words = set(pos_dict["program_name"].lower().split())
            best_open_date = None
            best_close_date = None

            for d in dates:
                date_prog = d.get("program", "").lower()
                # Fuzzy match: check if program name words appear in the date's context
                match_score = sum(
                    1 for w in program_words if w in date_prog and len(w) > 2)
                if match_score > 0 or len(program_words) <= 1:
                    if d["type"] == "open" and not best_open_date:
                        best_open_date = d["date"]
                    elif d["type"] == "close" and not best_close_date:
                        best_close_date = d["date"]

            # If no program-level match, use the first open date found
            if not best_open_date:
                for d in dates:
                    if d["type"] == "open":
                        best_open_date = d["date"]
                        break

            if best_open_date:
                try:
                    conn.execute("""
                        UPDATE job_positions
                        SET predicted_open_date = ?, confidence = 0.95,
                            is_official_date = 1, source = 'official'
                        WHERE id = ?
                    """, (best_open_date, pos_dict["id"]))
                    updated += 1
                except Exception:
                    failed += 1
            else:
                skipped += 1

        conn.commit()
        # Clean up cache
        if hasattr(self, '_official_cache'):
            del self._official_cache

        # Log the update run
        now = datetime.now().isoformat()
        try:
            conn.execute(
                "INSERT INTO scrape_logs (company_id, status, details, scraped_at) "
                "VALUES (NULL, 'success', ?, ?)",
                (f"Official date update: {updated} updated, {skipped} skipped, {failed} failed",
                 now)
            )
            conn.commit()
        except Exception:
            pass

        conn.close()
        return {
            "total_positions_checked": len(positions),
            "updated": updated,
            "skipped": skipped,
            "failed": failed,
        }

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


# ─── URL Validation ───

def validate_careers_url(url):
    """Check if a careers URL is accessible (returns 200-399).
    Returns True if valid, False otherwise."""
    if not url:
        return False
    try:
        import httpx as _httpx
        resp = _httpx.head(url, timeout=5, follow_redirects=True,
                           headers={"User-Agent": "FinanceInternRadar/1.0"})
        return resp.status_code < 400
    except Exception:
        return False


def update_url_validity():
    """Check all companies' careers_url and update careers_url_valid flag."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    companies = conn.execute(
        "SELECT id, careers_url FROM companies WHERE careers_url IS NOT NULL AND careers_url != ''"
    ).fetchall()

    updated = 0
    for c in companies:
        valid = 1 if validate_careers_url(c["careers_url"]) else 0
        conn.execute(
            "UPDATE companies SET careers_url_valid = ? WHERE id = ?",
            (valid, c["id"])
        )
        updated += 1

    conn.commit()
    conn.close()
    return {"checked": updated}


def _update_program_statuses():
    """Transition programs from upcoming/rolling to open when their date has passed."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    today = datetime.now().strftime("%Y-%m-%d")

    # Find programs that should now be open
    newly_opened = conn.execute("""
        SELECT id, company_id, program_name, predicted_open_date, status
        FROM job_positions
        WHERE status IN ('upcoming', 'rolling')
          AND predicted_open_date IS NOT NULL
          AND predicted_open_date <= ?
          AND year = 2026
    """, (today,)).fetchall()

    opened_ids = []
    for prog in newly_opened:
        conn.execute(
            "UPDATE job_positions SET status = 'open', open_date = ? WHERE id = ?",
            (today, prog["id"])
        )
        opened_ids.append(prog["id"])

    conn.commit()
    conn.close()
    return opened_ids


def validate_all_urls():
    """Validate all careers URLs, update program statuses, and notify subscribers
    about any newly opened positions."""
    url_result = update_url_validity()
    opened_ids = _update_program_statuses()

    # Notify subscribers about newly opened positions
    if opened_ids:
        try:
            from notifier import notify_new_openings
            notify_new_openings(opened_ids)
        except Exception:
            pass

    return {
        "urls_checked": url_result["checked"],
        "newly_opened": len(opened_ids),
        "opened_program_ids": opened_ids,
    }


if __name__ == "__main__":
    engine = ScraperEngine()
    print(f"Active sources: {len(engine.get_active_sources())}")
    status = engine.get_scraping_status()
    print(f"Total scraped positions: {status['total_positions']}, New: {status['new_positions']}")
    engine.close()
