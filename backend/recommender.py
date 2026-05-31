"""
Daily Hidden Gem Recommender.
Selects 3 lesser-known finance companies each day, rotated across categories.
Now prioritizes newly discovered companies and FinTech startups.
"""

import sqlite3
import random
import os
from datetime import datetime, date, timedelta

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
        "Newly tracked — fresh opportunities hot off our radar",
        "Fast-growing startup with rapid career progression potential",
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

# Reason templates for newly discovered companies
NEW_DISCOVERY_REASONS = [
    "Recently added to our radar — fresh opportunities available",
    "New on the platform — be among the first to apply",
    "Just discovered — early applicants often have an edge",
    "Freshly tracked company with active intern openings",
    "New addition — this company is actively hiring interns right now",
]


def _get_newly_scraped_companies(conn, days=7):
    """Get companies that have been recently scraped with new positions."""
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT c.*, COUNT(sp.id) as new_pos_count
        FROM companies c
        JOIN scraping_sources ss ON c.id = ss.company_id
        JOIN scraped_positions sp ON ss.id = sp.source_id
        WHERE sp.is_new = 1
          AND sp.scraped_at >= ?
        GROUP BY c.id
        ORDER BY new_pos_count DESC
    """, (cutoff,))
    return [dict(r) for r in cursor.fetchall()]


def _get_fintech_companies(conn):
    """Get FinTech category companies with recent activity."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.*, COALESCE(
            (SELECT COUNT(*) FROM scraped_positions sp
             JOIN scraping_sources ss ON sp.source_id = ss.id
             WHERE ss.company_id = c.id AND sp.is_new = 1), 0
        ) as new_pos_count
        FROM companies c
        WHERE c.category = 'FinTech'
        ORDER BY new_pos_count DESC, c.created_at DESC
    """)
    return [dict(r) for r in cursor.fetchall()]


def _get_recently_added_companies(conn, days=30):
    """Get companies added to the database recently."""
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.*, COALESCE(
            (SELECT COUNT(*) FROM scraped_positions sp
             JOIN scraping_sources ss ON sp.source_id = ss.id
             WHERE ss.company_id = c.id AND sp.is_new = 1), 0
        ) as new_pos_count
        FROM companies c
        WHERE c.created_at >= ?
        ORDER BY c.created_at DESC
    """, (cutoff,))
    return [dict(r) for r in cursor.fetchall()]


def generate_daily_picks(date_str=None):
    """Generate 3 daily hidden gem recommendations.
    
    Prioritization logic (in order):
    1. Recently scraped companies with active new positions (last 7 days)
    2. FinTech category startups (always at least 1 per day if available)
    3. Companies recently added to the database (last 30 days)
    4. Featured (is_featured=1) companies as fallback
    5. All companies as last resort
    """
    if date_str is None:
        date_str = date.today().isoformat()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Use date as seed for deterministic rotation
    seed_val = sum(ord(c) for c in date_str)
    rng = random.Random(seed_val)

    # Exclude companies already picked today
    cursor.execute("""
        SELECT company_id FROM daily_recommendations WHERE date = ?
    """, (date_str,))
    excluded_ids = [r["company_id"] for r in cursor.fetchall()]

    picks = []

    # Tier 1: Recently scraped companies with new positions
    newly_scraped = _get_newly_scraped_companies(conn, days=7)
    newly_scraped = [c for c in newly_scraped if c["id"] not in excluded_ids]
    if newly_scraped:
        rng.shuffle(newly_scraped)
        # Take up to 1 from this tier (ensure diversity)
        pick = newly_scraped[0]
        picks.append(pick)
        excluded_ids.append(pick["id"])

    # Tier 2: FinTech startups (guarantee at least 1)
    fintechs = _get_fintech_companies(conn)
    fintechs = [c for c in fintechs if c["id"] not in excluded_ids]
    if fintechs:
        rng.shuffle(fintechs)
        pick = fintechs[0]
        picks.append(pick)
        excluded_ids.append(pick["id"])

    # Tier 3: Recently added companies
    recent = _get_recently_added_companies(conn, days=30)
    recent = [c for c in recent if c["id"] not in excluded_ids]
    if recent and len(picks) < 3:
        rng.shuffle(recent)
        pick = recent[0]
        picks.append(pick)
        excluded_ids.append(pick["id"])

    # Tier 4: Featured companies (hidden gems)
    if len(picks) < 3:
        cursor.execute("""
            SELECT c.* FROM companies c
            WHERE c.is_featured = 1
            AND c.id NOT IN ({})
        """.format(",".join(str(x) for x in excluded_ids) if excluded_ids else "-1"))

        featured = [dict(r) for r in cursor.fetchall()]
        rng.shuffle(featured)
        picks.extend(featured[:3 - len(picks)])

    # Tier 5: All remaining companies
    remaining_needed = 3 - len(picks)
    if remaining_needed > 0:
        excluded_ids_str = ",".join(str(x) for x in excluded_ids) if excluded_ids else "-1"
        cursor.execute(f"""
            SELECT c.* FROM companies c
            WHERE c.id NOT IN ({excluded_ids_str})
        """)
        all_candidates = [dict(r) for r in cursor.fetchall()]
        rng.shuffle(all_candidates)
        picks.extend(all_candidates[:remaining_needed])

    # Insert into daily_recommendations with enriched reasons
    for pick in picks:
        cat = pick.get("category", "")
        reasons = GEM_REASONS.get(cat, FALLBACK_REASONS)

        # Boost: if this is a new discovery, use special reasons
        is_new_discovery = pick.get("new_pos_count", 0) > 0 or cat == "FinTech"
        if is_new_discovery and rng.random() < 0.5:
            # 50% chance to use a new-discovery reason instead
            reason = rng.choice(NEW_DISCOVERY_REASONS)
        else:
            reason = rng.choice(reasons)

        cursor.execute(
            "INSERT INTO daily_recommendations (company_id, reason, date) VALUES (?, ?, ?)",
            (pick["id"], reason, date_str)
        )

    conn.commit()
    conn.close()

    return picks


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

    # Enrich: tag which are newly scraped / FinTech
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    for row in rows:
        # Check if company has recent new positions
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) as cnt FROM scraped_positions sp
            JOIN scraping_sources ss ON sp.source_id = ss.id
            WHERE ss.company_id = ? AND sp.is_new = 1
              AND sp.scraped_at >= ?
        """, (row["id"], (date.today() - timedelta(days=7)).isoformat()))
        new_count = cursor.fetchone()["cnt"]
        row["has_new_positions"] = new_count > 0
        row["new_positions_count"] = new_count

        # Check if FinTech
        row["is_fintech"] = row.get("category") == "FinTech"

        # Check if recently added
        if row.get("created_at"):
            try:
                created = datetime.fromisoformat(str(row["created_at"]).replace("Z", "+00:00"))
                row["is_recently_added"] = (date.today() - created.date()).days <= 30
            except (ValueError, AttributeError):
                row["is_recently_added"] = False
        else:
            row["is_recently_added"] = False

    conn.close()
    return rows


if __name__ == "__main__":
    picks = get_today_picks()
    for p in picks:
        tags = []
        if p.get("has_new_positions"):
            tags.append("NEW")
        if p.get("is_fintech"):
            tags.append("FinTech")
        tag_str = f" [{', '.join(tags)}]" if tags else ""
        print(f"  [{p['category']}] {p['name']}{tag_str}: {p['reason']}")