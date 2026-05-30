"""
Daily Hidden Gem Recommender.
Selects 3 lesser-known finance companies each day, rotated across categories.
"""

import sqlite3
import random
import os
from datetime import datetime, date

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "radar.db")

GEM_REASONS = {
    "Prop Trading": [
        "High compensation with base + bonus easily exceeding $200k for interns",
        "Fast-paced meritocratic culture, ideal for self-starters",
        "Small teams = high impact from day one; no bureaucracy",
        "Many don't require finance background — they train you in-house",
    ],
    "Boutique": [
        "Lean deal teams — you'll work directly with MDs on live transactions",
        "Higher deal flow per analyst compared to bulge brackets",
        "Stronger lateral exit opportunities to PE due to deal experience",
        "Less competition than GS/MS but similar prestige on the Street",
    ],
    "Hedge Fund": [
        "Intellectual rigor — you'll learn investing from the best in the industry",
        "Compensation directly tied to performance, uncapped upside",
        "Many funds run internal 'academy' programs for interns",
    ],
    "Quant": [
        "Work at the intersection of math, CS, and finance",
        "Often sponsor work visas more readily than traditional banks",
        "PhD-friendly entry points with dedicated research tracks",
    ],
    "Asset Management": [
        "Long-term investing mindset — less stressful than IB lifestyle",
        "Strong brand name for future MBA applications",
        "Many run rotational programs giving exposure across asset classes",
    ],
    "FinTech": [
        "Modern tech stack, no legacy systems to wrestle with",
        "Equity upside potential at pre-IPO stage companies",
        "Blend finance domain knowledge with engineering skills",
    ],
    "PE/VC": [
        "Direct exposure to deal sourcing and investment decisions",
        "Small team environment with direct partner mentorship",
        "Strong network effects for future career moves",
    ],
}

FALLBACK_REASONS = [
    "Consistently rated as a top place to work in finance",
    "Known for exceptional intern conversion rates to full-time",
    "Unique niche in the market with strong growth trajectory",
    "Alumni network punches far above its weight in the industry",
]


def generate_daily_picks(date_str=None):
    """Generate 3 daily hidden gem recommendations."""
    if date_str is None:
        date_str = date.today().isoformat()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get featured (hidden gem) companies not in today's picks already
    cursor.execute("""
        SELECT c.* FROM companies c
        WHERE c.is_featured = 1
        AND c.id NOT IN (
            SELECT company_id FROM daily_recommendations WHERE date = ?
        )
    """, (date_str,))
    candidates = [dict(r) for r in cursor.fetchall()]

    # If no featured companies left, fall back to all
    if len(candidates) < 3:
        cursor.execute("""
            SELECT c.* FROM companies c
            WHERE c.id NOT IN (
                SELECT company_id FROM daily_recommendations WHERE date = ?
            )
        """, (date_str,))
        all_candidates = [dict(r) for r in cursor.fetchall()]
        candidates = all_candidates

    # Use date as seed for deterministic rotation
    seed = sum(ord(c) for c in date_str)
    rng = random.Random(seed)
    rng.shuffle(candidates)

    picks = candidates[:3]

    # Insert into daily_recommendations
    for pick in picks:
        cat = pick.get("category", "")
        reasons = GEM_REASONS.get(cat, FALLBACK_REASONS)
        reason = rng.choice(reasons)

        cursor.execute(
            "INSERT INTO daily_recommendations (company_id, reason, date) VALUES (?, ?, ?)",
            (pick["id"], reason, date_str)
        )

    conn.commit()

    # Return with reasons
    result = []
    for pick in picks:
        cursor.execute(
            "SELECT reason FROM daily_recommendations WHERE company_id = ? AND date = ?",
            (pick["id"], date_str)
        )
        reason_row = cursor.fetchone()
        pick["reason"] = reason_row["reason"] if reason_row else ""
        result.append(pick)

    conn.close()
    return result


def get_today_picks():
    """Get today's picks or generate new ones."""
    today = date.today().isoformat()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT c.*, dr.reason, dr.date as rec_date
        FROM daily_recommendations dr
        JOIN companies c ON dr.company_id = c.id
        WHERE dr.date = ?
    """, (today,))

    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()

    if not rows:
        rows = generate_daily_picks(today)

    return rows


if __name__ == "__main__":
    picks = get_today_picks()
    for p in picks:
        print(f"  [{p['category']}] {p['name']}: {p['reason']}")