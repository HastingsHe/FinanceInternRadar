"""
Prediction Engine: Forecast job position opening dates based on historical patterns.
Uses a hybrid approach: trend analysis + rule-based fallback.
All intern_programs references updated to job_positions.
"""

import sqlite3
from datetime import datetime, timedelta
from collections import defaultdict
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "radar.db")


def _parse_date(date_str):
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def _get_historical_openings(company_id, program_name=None, season=None):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = "SELECT * FROM historical_openings WHERE company_id = ?"
    params = [company_id]

    if program_name:
        query += " AND program_name = ?"
        params.append(program_name)
    if season:
        query += " AND season = ?"
        params.append(season)

    query += " ORDER BY year ASC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return rows


def predict_opening_date(company_id, program_name, season="Summer", target_year=2026):
    history = _get_historical_openings(company_id, program_name, season)
    if not history:
        return None, 0.0

    dates = []
    for row in history:
        d = _parse_date(row["open_date"])
        if d:
            dates.append((row["year"], d))

    if len(dates) < 2:
        return _rule_based_fallback(company_id, program_name, season, target_year), 0.3

    days_of_year = []
    for year, dt in dates:
        days_of_year.append(dt.timetuple().tm_yday)

    if len(days_of_year) >= 3:
        shifts = [days_of_year[i] - days_of_year[i - 1] for i in range(1, len(days_of_year))]
        avg_shift = sum(shifts) / len(shifts)
    else:
        avg_shift = days_of_year[-1] - days_of_year[0] if len(days_of_year) == 2 else 0

    last_year, last_date = dates[-1]
    years_ahead = target_year - last_year
    predicted_doy = round(days_of_year[-1] + avg_shift * years_ahead)
    predicted_doy = max(1, min(366, predicted_doy))

    try:
        predicted_date = datetime(target_year, 1, 1) + timedelta(days=predicted_doy - 1)
    except ValueError:
        predicted_date = datetime(target_year, 1, 1) + timedelta(days=min(predicted_doy, 365) - 1)

    n = len(dates)
    variance = sum((d - sum(days_of_year) / n) ** 2 for d in days_of_year) / n if n > 1 else 100
    consistency = max(0, 1 - (variance ** 0.5) / 30)
    data_points_bonus = min(0.3, n * 0.05)
    confidence = min(0.95, consistency * 0.7 + data_points_bonus + 0.1)

    return predicted_date.strftime("%Y-%m-%d"), round(confidence, 2)


def _rule_based_fallback(company_id, program_name, season, target_year):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT category, region FROM companies WHERE id = ?", (company_id,))
    row = cursor.fetchone()
    conn.close()

    category = row["category"] if row else "Bulge Bracket"
    region = row["region"] if row else "US"

    patterns = {
        "Bulge Bracket": (6, 8),
        "Boutique": (4, 7),
        "Prop Trading": (6, 9),
        "Hedge Fund": (7, 10),
        "Quant": (7, 10),
        "Asset Management": (8, 10),
        "PE/VC": (1, 3),
        "FinTech": (8, 11),
    }

    # Regional adjustments
    regional_offset = {
        "CN": -2,   # China tends to open earlier (March-June)
        "HK": -1,   # HK similar but slightly earlier
        "AU": -4,   # Australia summer internship opens Feb-April
        "EU": 0,    # Europe similar to US
        "UK": 0,
        "US": 0,
    }

    month_range = patterns.get(category, (7, 9))
    offset = regional_offset.get(region, 0)
    mid_month = (month_range[0] + month_range[1]) // 2 + offset
    mid_month = max(1, min(12, mid_month))
    return datetime(target_year, mid_month, 1).strftime("%Y-%m-%d")


def generate_all_predictions(target_year=2026):
    """Generate predictions for all company programs and store in job_positions."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT DISTINCT company_id, program_name, season
        FROM historical_openings
    """)
    combos = cursor.fetchall()

    # Clear old predictions for target year
    cursor.execute("DELETE FROM job_positions WHERE year = ?", (target_year,))

    for combo in combos:
        pred_date, confidence = predict_opening_date(
            combo["company_id"], combo["program_name"], combo["season"], target_year
        )
        if pred_date:
            cursor.execute("""
                INSERT INTO job_positions
                (company_id, program_name, season, year, predicted_open_date, confidence, status)
                VALUES (?, ?, ?, ?, ?, ?, 'upcoming')
            """, (combo["company_id"], combo["program_name"], combo["season"],
                  target_year, pred_date, confidence))

    conn.commit()
    conn.close()
    return len(combos)


def get_job_positions(company_id=None, region=None, role_type=None, job_type=None, season="Summer", year=2026):
    """Get job positions with company info, filterable. Now includes rolling_basis and is_official_date."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = """
        SELECT c.id as company_id, c.name, c.region, c.category, c.description, c.careers_url, c.is_featured,
               jp.program_name, jp.season, jp.year, jp.predicted_open_date, jp.confidence, jp.status,
               jp.job_type, jp.role_type,
               jp.rolling_basis, jp.is_official_date, jp.source
        FROM job_positions jp
        JOIN companies c ON jp.company_id = c.id
        WHERE jp.year = ?
    """
    params = [year]

    if company_id:
        query += " AND c.id = ?"
        params.append(company_id)
    if region:
        query += " AND c.region = ?"
        params.append(region)
    if job_type:
        query += " AND jp.job_type = ?"
        params.append(job_type)
    if season:
        query += " AND jp.season = ?"
        params.append(season)

    query += " ORDER BY jp.predicted_open_date ASC, c.name ASC"
    cursor.execute(query, params)
    rows = [dict(r) for r in cursor.fetchall()]

    if role_type:
        role_map = {
            "ib": "Investment Banking",
            "snt": "Sales & Trading",
            "quant": "Quant",
            "research": "Research",
            "am": "Asset Management",
        }
        target = role_map.get(role_type.lower(), role_type)
        rows = [r for r in rows if target.lower() in (r.get("program_name") or "").lower()
                or target.lower() in (r.get("role_type") or "").lower()]

    conn.close()
    return rows


def check_early_opens(days_threshold=14):
    """Detect positions that are approaching their predicted open date or may have quietly opened early.

    Returns a dict with:
      - 'warnings': positions within days_threshold of predicted_open_date
      - 'rolling_warnings': rolling-basis positions within 30 days (higher risk of early screening)
      - 'count': total warnings
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    today = datetime.now().date()
    threshold_date = today + timedelta(days=days_threshold)
    rolling_threshold_date = today + timedelta(days=30)

    # Positions opening soon (within threshold)
    cursor.execute("""
        SELECT jp.id, jp.program_name, jp.predicted_open_date, jp.confidence,
               jp.rolling_basis, jp.is_official_date, jp.status,
               c.name as company_name, c.region, c.careers_url
        FROM job_positions jp
        JOIN companies c ON jp.company_id = c.id
        WHERE jp.status = 'upcoming'
          AND jp.predicted_open_date IS NOT NULL
          AND jp.predicted_open_date <= ?
          AND jp.year = 2026
        ORDER BY jp.predicted_open_date ASC
    """, (threshold_date.isoformat(),))
    warnings = [dict(r) for r in cursor.fetchall()]

    # Rolling-basis positions with extended risk window (30 days)
    cursor.execute("""
        SELECT jp.id, jp.program_name, jp.predicted_open_date, jp.confidence,
               jp.rolling_basis, jp.is_official_date, jp.status,
               c.name as company_name, c.region, c.careers_url
        FROM job_positions jp
        JOIN companies c ON jp.company_id = c.id
        WHERE jp.status = 'upcoming'
          AND jp.rolling_basis = 1
          AND jp.predicted_open_date IS NOT NULL
          AND jp.predicted_open_date <= ?
          AND jp.predicted_open_date > ?
          AND jp.year = 2026
        ORDER BY jp.predicted_open_date ASC
    """, (rolling_threshold_date.isoformat(), threshold_date.isoformat()))
    rolling_warnings = [dict(r) for r in cursor.fetchall()]

    conn.close()

    return {
        "warnings": warnings,
        "rolling_warnings": rolling_warnings,
        "count": len(warnings) + len(rolling_warnings),
    }


# Alias for backward compat
def get_company_predictions(company_id=None, region=None, role_type=None, job_type=None, season="Summer", year=2026):
    return get_job_positions(company_id=company_id, region=region, role_type=role_type, job_type=job_type, season=season, year=year)
