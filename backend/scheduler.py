"""
FinanceInternRadar - Background Scheduler
Uses a simple threading.Timer for periodic scraping.
Integrated into FastAPI lifespan (startup/shutdown).
"""

import threading
import time
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "radar.db")

DEFAULT_INTERVAL_HOURS = 6


class ScrapeScheduler:
    """Periodic scraper scheduler using threading.Timer."""

    def __init__(self, interval_hours=DEFAULT_INTERVAL_HOURS):
        self.interval_hours = interval_hours
        self._timer = None
        self._running = False
        self._lock = threading.Lock()
        self.last_run = None
        self.last_summary = None
        self.last_error = None
        self.run_count = 0

    def _run_scrape(self):
        """Execute one scrape cycle."""
        from scraper import ScraperEngine

        try:
            engine = ScraperEngine()
            results = engine.scrape_all()
            engine.close()

            self.last_summary = {
                "time": datetime.now().isoformat(),
                "results": results,
                "total": len(results),
                "new_positions": sum(r["new_positions"] for r in results),
            }
            self.last_run = datetime.now().isoformat()
            self.last_error = None
            self.run_count += 1
            return True
        except Exception as e:
            self.last_error = str(e)
            self.last_run = datetime.now().isoformat()
            return False

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
        """Start the scheduler. First run is immediate, then periodic."""
        with self._lock:
            if self._running:
                return
            self._running = True

        # Run first scrape immediately in background
        t = threading.Thread(target=self._run_scrape, daemon=True)
        t.start()

        # Schedule subsequent runs
        self._schedule_next()
        print(f"[Scheduler] Started with interval={self.interval_hours}h")

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
        """Get current scheduler status."""
        return {
            "running": self._running,
            "interval_hours": self.interval_hours,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "run_count": self.run_count,
            "last_error": self.last_error,
            "last_summary": self.last_summary,
        }


# Global singleton
_scheduler: ScrapeScheduler = None


def get_scheduler() -> ScrapeScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = ScrapeScheduler()
    return _scheduler
