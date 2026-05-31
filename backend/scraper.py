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
