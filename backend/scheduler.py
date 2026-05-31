"""
FinanceInternRadar - Background Scheduler
Uses a simple threading.Timer for periodic scraping.
Integrated into FastAPI lifespan (startup/shutdown).
Enhanced for Render deployment and daily discovery tracking.
"""

import threading
import time
import os
import sqlite3
from datetime import datetime, date

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "radar.db")

# Default interval: 6 hours (4x daily). Configurable via env var.
DEFAULT_INTERVAL_HOURS = int(os.environ.get("SCRAPE_INTERVAL_HOURS", "6"))


class ScrapeScheduler:
    """Periodic scraper scheduler using threading.Timer.
    Tracks daily discovery runs and ensures at least one full scrape per day.
    """

    def __init__(self, interval_hours=DEFAULT_INTERVAL_HOURS):
        self.interval_hours = interval_hours
        self._timer = None
        self._running = False
        self._lock = threading.Lock()
        self.last_run = None
        self.last_summary = None
        self.last_error = None
        self.run_count = 0

        # Daily discovery tracking
        self.last_daily_discovery_date = None
        self.last_daily_discovery_result = None
        self.daily_discovery_count = 0

    def _run_scrape(self):
        """Execute one scrape cycle and track daily discovery."""
        from scraper import ScraperEngine

        try:
            engine = ScraperEngine()
            results = engine.scrape_all()
            engine.close()

            # Extract new positions count from summary
            new_positions = 0
            for r in results:
                if r.get("company") == "__SUMMARY__":
                    new_positions = r.get("new_positions", 0)
                    break

            self.last_summary = {
                "time": datetime.now().isoformat(),
                "results": results,
                "total": len(results),
                "new_positions": new_positions,
            }
            self.last_run = datetime.now().isoformat()
            self.last_error = None
            self.run_count += 1

            # Track daily discovery
            today = date.today()
            if self.last_daily_discovery_date != today:
                # New day - reset daily counter
                self.last_daily_discovery_date = today
                self.daily_discovery_count = 1
                self.last_daily_discovery_result = {
                    "date": today.isoformat(),
                    "new_positions": new_positions,
                    "total_companies": len([r for r in results if r.get("source_type") == "fintech_startup"]),
                }
                self._log_daily_discovery(today, new_positions, results)
            else:
                self.daily_discovery_count += 1
                if new_positions > 0:
                    self.last_daily_discovery_result["new_positions"] += new_positions

            return True
        except Exception as e:
            self.last_error = str(e)
            self.last_run = datetime.now().isoformat()
            return False

    def _log_daily_discovery(self, today, new_positions, results):
        """Log daily discovery summary to the database."""
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.execute("PRAGMA journal_mode=WAL")

            # Count newly discovered companies (FinTech added today)
            fintech_added = 0
            for r in results:
                if r.get("source_type") == "summary":
                    fintech_added = r.get("fintech_companies_added", 0)
                    break

            conn.execute(
                """INSERT INTO scrape_logs (company_id, status, details, scraped_at)
                   VALUES (NULL, 'success', ?, ?)""",
                (f"Daily discovery: {new_positions} new positions, {fintech_added} new FinTech companies",
                 today.isoformat())
            )
            conn.commit()
            conn.close()
        except Exception:
            pass  # Non-critical logging

    def _schedule_next(self):
        """Schedule the next scrape cycle."""
        if not self._running:
            return
        self._timer = threading.Timer(self.interval_hours * 3600, self._run_and_reschedule)
        self._timer.daemon = True
        self._timer.start()

    def _run_and_reschedule(self):
        """Run scrape and schedule next."""
        self._run_scrape()
        self._schedule_next()

    def start(self):
        """Start the scheduler. First run is immediate, then periodic.
        Designed to work on Render: runs in background thread alongside main server.
        """
        with self._lock:
            if self._running:
                return
            self._running = True

        # Run first scrape immediately in background
        t = threading.Thread(target=self._run_scrape, daemon=True)
        t.start()

        # Schedule subsequent runs
        self._schedule_next()
        print(f"[Scheduler] Started with interval={self.interval_hours}h (runs every {self.interval_hours} hours, ~{24//self.interval_hours}x daily)")

    def stop(self):
        """Stop the scheduler."""
        with self._lock:
            self._running = False
            if self._timer:
                self._timer.cancel()
                self._timer = None
        print("[Scheduler] Stopped")

    def trigger_now(self):
        """Manually trigger a scrape cycle (blocks until done)."""
        success = self._run_scrape()
        return {
            "success": success,
            "summary": self.last_summary,
        }

    def get_status(self):
        """Get current scheduler status including daily discovery info."""
        return {
            "running": self._running,
            "interval_hours": self.interval_hours,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "run_count": self.run_count,
            "last_error": self.last_error,
            "last_summary": self.last_summary,
            "daily_discovery": {
                "date": self.last_daily_discovery_date.isoformat() if self.last_daily_discovery_date else None,
                "runs_today": self.daily_discovery_count,
                "result": self.last_daily_discovery_result,
            },
        }


# Global singleton
_scheduler: ScrapeScheduler = None


def get_scheduler() -> ScrapeScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = ScrapeScheduler()
    return _scheduler
