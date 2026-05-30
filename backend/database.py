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
            region TEXT NOT NULL CHECK(region IN ('US', 'UK')),
            category TEXT NOT NULL CHECK(category IN ('Bulge Bracket', 'Boutique', 'Quant', 'Asset Management', 'Hedge Fund', 'Prop Trading', 'PE/VC', 'FinTech')),
            description TEXT,
            website TEXT,
            careers_url TEXT,
            is_featured INTEGER DEFAULT 0,
            logo_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS intern_programs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
            program_name TEXT NOT NULL,
            role_type TEXT CHECK(role_type IN ('Investment Banking', 'Sales & Trading', 'Quant', 'Research', 'Risk', 'Asset Management', 'S&T', 'Private Equity', 'Software Engineering', 'Data Science', 'Generalist')),
            season TEXT NOT NULL CHECK(season IN ('Summer', 'Spring', 'Off-Cycle', 'Winter')),
            year INTEGER NOT NULL,
            open_date TEXT,
            close_date TEXT,
            predicted_open_date TEXT,
            confidence REAL DEFAULT 0.0,
            status TEXT DEFAULT 'upcoming' CHECK(status IN ('upcoming', 'open', 'closed')),
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
    """)

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DB_PATH}")