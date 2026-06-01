"""
FinanceInternRadar - Database Layer
SQLite for MVP, easy migration to PostgreSQL later.
"""

import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "radar.db")


def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            region TEXT NOT NULL CHECK(region IN ('US', 'UK', 'CN', 'EU', 'HK', 'AU')),
            category TEXT NOT NULL CHECK(category IN ('Bulge Bracket', 'Boutique', 'Quant', 'Asset Management', 'Hedge Fund', 'Prop Trading', 'PE/VC', 'FinTech')),
            description TEXT,
            website TEXT,
            careers_url TEXT,
            careers_url_valid INTEGER DEFAULT NULL,
            is_featured INTEGER DEFAULT 0,
            logo_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS job_positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
            program_name TEXT NOT NULL,
            role_type TEXT CHECK(role_type IN ('Investment Banking', 'Sales & Trading', 'Quant', 'Research', 'Risk', 'Asset Management', 'S&T', 'Private Equity', 'Software Engineering', 'Data Science', 'Generalist')),
            job_type TEXT CHECK(job_type IN ('intern', 'full-time', 'graduate', 'management_trainee')),
            season TEXT NOT NULL CHECK(season IN ('Summer', 'Spring', 'Off-Cycle', 'Winter', 'Fall', 'Full-Year')),
            year INTEGER NOT NULL,
            open_date TEXT,
            close_date TEXT,
            predicted_open_date TEXT,
            confidence REAL DEFAULT 0.0,
            status TEXT DEFAULT 'upcoming' CHECK(status IN ('upcoming', 'open', 'closed', 'rolling')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS historical_openings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
            program_name TEXT NOT NULL,
            season TEXT NOT NULL,
            year INTEGER NOT NULL,
            open_date TEXT NOT NULL,
            close_date TEXT,
            source TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS subscribers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            name TEXT,
            age TEXT,
            gender TEXT,
            school TEXT,
            academic_stage TEXT,
            graduation_time TEXT,
            subscribe_companies TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subscriber_id INTEGER NOT NULL REFERENCES subscribers(id) ON DELETE CASCADE,
            company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
            role_type TEXT,
            region TEXT,
            notify_email INTEGER DEFAULT 1,
            active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS daily_recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
            reason TEXT,
            date TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS scrape_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER REFERENCES companies(id),
            status TEXT CHECK(status IN ('success', 'failed', 'no_change')),
            details TEXT,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS scraping_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL REFERENCES companies(id),
            source_url TEXT NOT NULL,
            source_type TEXT CHECK(source_type IN ('careers_page', 'rss', 'api', 'linkedin')),
            region TEXT,
            job_type TEXT,
            is_active INTEGER DEFAULT 1,
            last_scraped_at TIMESTAMP,
            last_status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS scraped_positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id INTEGER REFERENCES scraping_sources(id),
            title TEXT NOT NULL,
            job_type TEXT,
            location TEXT,
            region TEXT,
            posted_date TEXT,
            external_url TEXT,
            description_snippet TEXT,
            is_new INTEGER DEFAULT 1,
            is_verified INTEGER DEFAULT 0,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(source_id, title, posted_date)
        );

        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            program_id INTEGER NOT NULL REFERENCES job_positions(id) ON DELETE CASCADE,
            alert_type TEXT NOT NULL CHECK(alert_type IN ('early_open', 'prediction_miss', 'now_open', 'closing_soon')),
            message TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # ─── Migration: add new subscriber fields for existing databases ───
    migration_cols = ["age", "gender", "school", "academic_stage", "graduation_time", "subscribe_companies"]
    for col in migration_cols:
        try:
            cursor.execute(f"ALTER TABLE subscribers ADD COLUMN {col} TEXT")
        except sqlite3.OperationalError:
            pass  # column already exists

    # ─── Migration: rolling basis / official date tracking ───
    job_positions_migrations = [
        ("rolling_basis", "INTEGER DEFAULT 0"),
        ("is_official_date", "INTEGER DEFAULT 0"),
        ("source", "TEXT DEFAULT 'prediction'"),
    ]
    for col_name, col_def in job_positions_migrations:
        try:
            cursor.execute(f"ALTER TABLE job_positions ADD COLUMN {col_name} {col_def}")
        except sqlite3.OperationalError:
            pass  # column already exists

    # ─── Migration: careers URL validity tracking ───
    try:
        cursor.execute("ALTER TABLE companies ADD COLUMN careers_url_valid INTEGER DEFAULT NULL")
    except sqlite3.OperationalError:
        pass  # column already exists

    # ─── Migration: fix careers_url to point to intern/students pages ───
    _careers_url_fixes = {
        # US
        "Bridgewater Associates": "https://www.bridgewater.com/working-at-bridgewater/students",
        "Centerview Partners": "http://centerviewpartners.com/careers.aspx",
        "D.E. Shaw & Co.": "https://campus.deshaw.com",
        "Hudson River Trading": "https://www.hudsonrivertrading.com/student-opportunities/",
        "Jane Street": "https://www.janestreet.com/join-jane-street/internships/",
        "PJT Partners": "https://www.pjtpartners.com/careers/students",
        "Two Sigma": "https://www.twosigma.com/careers/students/",
        # CN
        "CICC (中金公司)": "https://cicc.zhiye.com",
        "CITIC Securities (中信证券)": "https://careers.citics.com/",
        "Huatai Securities (华泰证券)": "https://job.htsc.com.cn/",
        # HK
        "BOCI (中银国际)": "https://www.bocichina.com/main/joinus/campusrecruitment/index.shtml",
    }
    for name, new_url in _careers_url_fixes.items():
        try:
            cursor.execute(
                "UPDATE companies SET careers_url = ?, careers_url_valid = NULL WHERE name = ?",
                (new_url, name),
            )
        except sqlite3.OperationalError:
            pass

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DB_PATH}")
