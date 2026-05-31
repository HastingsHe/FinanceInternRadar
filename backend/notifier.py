"""
Notification Service.
Sends email alerts to subscribers when their tracked programs are opening soon.
For MVP, logs to console. Production: integrate with SendGrid / Resend / SMTP.
"""

import sqlite3
import os
from datetime import datetime, date, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "radar.db")

ALERT_WINDOW_DAYS = 7  # Alert if program opens within 7 days


def check_and_notify():
    """Check upcoming openings and notify relevant subscribers."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    today = date.today()
    alert_date = today + timedelta(days=ALERT_WINDOW_DAYS)

    # Get programs opening within the alert window
    cursor.execute("""
        SELECT jp.*, c.name as company_name, c.careers_url
        FROM job_positions jp
        JOIN companies c ON jp.company_id = c.id
        WHERE jp.year = 2026
        AND jp.predicted_open_date BETWEEN ? AND ?
        AND jp.status = 'upcoming'
        ORDER BY jp.predicted_open_date
    """, (today.isoformat(), alert_date.isoformat()))

    upcoming = [dict(r) for r in cursor.fetchall()]

    notifications = []

    for program in upcoming:
        # Find subscribers interested in this company or role type
        role_type = program.get("role_type", "")
        company_id = program["company_id"]

        cursor.execute("""
            SELECT s.email, s.name, sub.role_type, sub.region
            FROM subscriptions sub
            JOIN subscribers s ON sub.subscriber_id = s.id
            WHERE sub.active = 1
            AND (sub.company_id = ? OR sub.company_id IS NULL)
        """, (company_id,))

        subscribers = [dict(r) for r in cursor.fetchall()]

        for sub in subscribers:
            # In production: send actual email here
            notifications.append({
                "to": sub["email"],
                "name": sub.get("name", "Student"),
                "company": program["company_name"],
                "program": program["program_name"],
                "predicted_open": program["predicted_open_date"],
                "careers_url": program.get("careers_url", ""),
            })

    conn.close()

    # Log notifications (MVP)
    for n in notifications:
        print(f"  [NOTIFY] {n['to']}: {n['company']} - {n['program']} opens ~{n['predicted_open']}")

    return len(notifications), notifications


if __name__ == "__main__":
    from database import init_db
    init_db()
    count, _ = check_and_notify()
    print(f"Sent {count} notifications")