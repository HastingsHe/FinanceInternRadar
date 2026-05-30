"""
Prediction Engine: Forecast intern program opening dates based on historical patterns.
Uses a hybrid approach: trend analysis + rule-based fallback.
"""

import sqlite3
from datetime import datetime, timedelta
from collections import defaultdict
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "radar.db")


def _parse_date(date_str):
    """Parse date string to datetime."""
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def _get_historical_openings(company_id, program_name=None, season=None):
    """Fetch historical opening dates for a company program."""
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
    """
    Predict the opening date for a given program.
    Returns: (predicted_date_str, confidence_score)
    """
    history = _get_historical_openings(company_id, program_name, season)

    if not history:
        return None, 0.0

    dates = []
    for row in history:
        d = _parse_date(row["open_date"])
        if d:
            dates.append((row["year"], d))

    if len(dates) < 2:
        # Not enough data, use rule-based fallback
        return _rule_based_fallback(company_id, program_name, season, target_year), 0.3

    # Calculate day-of-year for each opening
    days_of_year = []
    for year, dt in dates:
        days_of_year.append(dt.timetuple().tm_yday)

    # Trend: average shift per year
    if len(days_of_year) >= 3:
        shifts = [days_of_year[i] - days_of_year[i - 1] for i in range(1, len(days_of_year))]
        avg_shift = sum(shifts) / len(shifts)
    else:
        avg_shift = days_of_year[-1] - days_of_year[0] if len(days_of_year) == 2 else 0

    # Predict day-of-year for target year
    last_year, last_date = dates[-1]
    years_ahead = target_year - last_year
    predicted_doy = round(days_of_year[-1] + avg_shift * years_ahead)

    # Clamp to valid range
    predicted_doy = max(1, min(366, predicted_doy))

    # Build date
    try:
        predicted_date = datetime(target_year, 1, 1) + timedelta(days=predicted_doy - 1)
    except ValueError:
        predicted_date = datetime(target_year, 1, 1) + timedelta(days=min(predicted_doy, 365) - 1)

    # Confidence calculation
    n = len(dates)
    variance = sum((d - sum(days_of_year) / n) ** 2 for d in days_of_year) / n if n > 1 else 100
    consistency = max(0, 1 - (variance ** 0.5) / 30)  # lower variance = higher confidence
    data_points_bonus = min(0.3, n * 0.05)  # up to 0.3 bonus for more data
    confidence = min(0.95, consistency * 0.7 + data_points_bonus + 0.1)

    return predicted_date.strftime("%Y-%m-%d"), round(confidence, 2)


def _rule_based_fallback(company_id, program_name, season, target_year):
    """Fallback prediction based on company category patterns."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT category FROM companies WHERE id = ?", (company_id,))
    row = cursor.fetchone()
    conn.close()

    category = row["category"] if row else "Bulge Bracket"

    # Typical opening windows by category (month ranges)
    patterns = {
        "Bulge Bracket": (6, 8),      # June-August
        "Boutique": (4, 7),            # April-July
        "Prop Trading": (6, 9),        # June-September
        "Hedge Fund": (7, 10),         # July-October
        "Quant": (7, 10),              # July-October
        "Asset Management": (8, 10),   # August-October
        "PE/VC": (1, 3),               # January-March
        "FinTech": (8, 11),            # August-November
    }

    month_range = patterns.get(category, (7, 9))
    mid_month = (month_range[0] + month_range[1]) // 2
    return datetime(target_year, mid_month, 1).strftime("%Y-%m-%d")


def generate_all_predictions(target_year=2026):
    """Generate predictions for all company programs and store in intern_programs."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get unique company-program-season combos from historical data
    cursor.execute("""
        SELECT DISTINCT company_id, program_name, season
        FROM historical_openings
    """)
    combos = cursor.fetchall()

    # Clear old predictions for target year
    cursor.execute("DELETE FROM intern_programs WHERE year = ?", (target_year,))

    for combo in combos:
        pred_date, confidence = predict_opening_date(
            combo["company_id"], combo["program_name"], combo["season"], target_year
        )
        if pred_date:
            cursor.execute("""
                INSERT INTO intern_programs
                (company_id, program_name, season, year, predicted_open_date, confidence, status)
                VALUES (?, ?, ?, ?, ?, ?, 'upcoming')
            """, (combo["company_id"], combo["program_name"], combo["season"],
                  target_year, pred_date, confidence))

    conn.commit()
    conn.close()
    return len(combos)


def get_company_predictions(company_id=None, region=None, role_type=None, season="Summer", year=2026):
    """Get predictions with company info, filterable."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = """
        SELECT c.id as company_id, c.name, c.region, c.category, c.description, c.careers_url, c.is_featured,
               ip.program_name, ip.season, ip.year, ip.predicted_open_date, ip.confidence, ip.status
        FROM intern_programs ip
        JOIN companies c ON ip.company_id = c.id
        WHERE ip.year = ?
    """
    params = [year]

    if company_id:
        query += " AND c.id = ?"
        params.append(company_id)
    if region:
        query += " AND c.region = ?"
        params.append(region)
    if season:
        query += " AND ip.season = ?"
        params.append(season)

    query += " ORDER BY ip.predicted_open_date ASC, c.name ASC"
    cursor.execute(query, params)
    rows = [dict(r) for r in cursor.fetchall()]

    # If role_type filter, do post-filter (role_type is embedded in program_name)
    if role_type:
        role_map = {
            "ib": "Investment Banking",
            "snt": "Sales & Trading",
            "quant": "Quant",
            "research": "Research",
            "am": "Asset Management",
        }
        target = role_map.get(role_type.lower(), role_type)
        rows = [r for r in rows if target.lower() in r["program_name"].lower()
                or target.lower() in (r.get("role_type") or "").lower()]

    conn.close()
    return rows


if __name__ == "__main__":
    # Quick test
    count = generate_all_predictions(2026)
    print(f"Generated {count} predictions for 2026")
    results = get_company_predictions(region="US", year=2026)
    for r in results[:5]:
        print(f"  {r['name']}: {r['program_name']} → {r['predicted_open_date']} (confidence: {r['confidence']})")