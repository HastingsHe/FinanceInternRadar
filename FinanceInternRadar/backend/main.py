"""
FinanceInternRadar - Main Application
FastAPI backend serving the web interface and API endpoints.
"""

import os
import sys
from datetime import datetime, date
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Add backend to path
sys.path.insert(0, os.path.dirname(__file__))

from database import init_db, get_db
from predictor import generate_all_predictions, get_company_predictions
from recommender import get_today_picks

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(BASE_DIR, "frontend", "templates")
STATIC_DIR = os.path.join(BASE_DIR, "frontend", "static")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB, seed data, generate predictions."""
    init_db()
    # Seed if empty
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    conn.close()
    if count == 0:
        from seed_data import seed
        seed()
    # Generate predictions
    try:
        generate_all_predictions(2026)
    except Exception as e:
        print(f"Prediction generation warning: {e}")
    yield


app = FastAPI(title="FinanceInternRadar", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Register custom filters
def format_date(value, fmt="%b %d, %Y"):
    if not value:
        return "TBD"
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime(fmt)
    except (ValueError, TypeError):
        return str(value)

templates.env.filters["format_date"] = format_date


# ─── Page Routes ───────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Landing page: overview + timeline."""
    # Get upcoming predictions
    us_predictions = get_company_predictions(region="US", year=2026)[:10]
    uk_predictions = get_company_predictions(region="UK", year=2026)[:10]

    # Get today's picks
    picks = get_today_picks()

    # Stats
    conn = get_db()
    total_companies = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    total_programs = conn.execute("SELECT COUNT(*) FROM intern_programs WHERE year=2026").fetchone()[0]
    conn.close()

    return templates.TemplateResponse("index.html", {
        "request": request,
        "us_predictions": us_predictions,
        "uk_predictions": uk_predictions,
        "picks": picks,
        "total_companies": total_companies,
        "total_programs": total_programs,
        "today": date.today(),
    })


@app.get("/companies", response_class=HTMLResponse)
async def companies_page(
    request: Request,
    region: str = Query("all"),
    category: str = Query("all"),
    role_type: str = Query("all"),
    search: str = Query(""),
):
    """Company listing with filters."""
    conn = get_db()
    conn.row_factory = __import__("sqlite3").Row

    query = "SELECT * FROM companies WHERE 1=1"
    params = []

    if region != "all":
        query += " AND region = ?"
        params.append(region)
    if category != "all":
        query += " AND category = ?"
        params.append(category)
    if search:
        query += " AND (name LIKE ? OR description LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])

    query += " ORDER BY is_featured DESC, name ASC"
    cursor = conn.execute(query, params)
    companies = [dict(r) for r in cursor.fetchall()]

    # Get predictions for each company
    for c in companies:
        preds = get_company_predictions(company_id=c["id"], year=2026)
        c["predictions"] = preds

    # Get distinct categories for filter
    categories = [r[0] for r in conn.execute(
        "SELECT DISTINCT category FROM companies ORDER BY category"
    ).fetchall()]
    conn.close()

    return templates.TemplateResponse("companies.html", {
        "request": request,
        "companies": companies,
        "categories": categories,
        "filters": {"region": region, "category": category, "role_type": role_type, "search": search},
    })


@app.get("/daily-picks", response_class=HTMLResponse)
async def daily_picks_page(request: Request):
    """Daily hidden gem recommendations."""
    picks = get_today_picks()

    # Also get some recent picks
    conn = get_db()
    conn.row_factory = __import__("sqlite3").Row
    cursor = conn.execute("""
        SELECT DISTINCT date FROM daily_recommendations
        ORDER BY date DESC LIMIT 5
    """)
    recent_dates = [r[0] for r in cursor.fetchall()]

    historical_picks = {}
    for d in recent_dates:
        cursor.execute("""
            SELECT c.name, c.category, dr.reason
            FROM daily_recommendations dr
            JOIN companies c ON dr.company_id = c.id
            WHERE dr.date = ?
        """, (d,))
        historical_picks[d] = [dict(r) for r in cursor.fetchall()]
    conn.close()

    return templates.TemplateResponse("daily_picks.html", {
        "request": request,
        "picks": picks,
        "historical_picks": historical_picks,
        "today": date.today().isoformat(),
    })


@app.get("/subscribe", response_class=HTMLResponse)
async def subscribe_page(request: Request):
    """Subscription management page."""
    conn = get_db()
    conn.row_factory = __import__("sqlite3").Row

    companies = [dict(r) for r in conn.execute(
        "SELECT id, name, region, category FROM companies ORDER BY name"
    ).fetchall()]

    # Get role types from existing programs
    role_types = sorted(set(
        r[0] for r in conn.execute(
            "SELECT DISTINCT role_type FROM intern_programs WHERE role_type IS NOT NULL"
        ).fetchall()
    ))
    conn.close()

    # Map from program names
    program_role_types = set()
    for c in companies:
        preds = get_company_predictions(company_id=c["id"], year=2026)
        for p in preds:
            pname = p.get("program_name", "")
            if "Investment Banking" in pname:
                program_role_types.add("Investment Banking")
            elif "Quant" in pname:
                program_role_types.add("Quant")
            elif "Sales & Trading" in pname or "Trading" in pname:
                program_role_types.add("Sales & Trading")
            elif "Research" in pname:
                program_role_types.add("Research")
            elif "Asset Management" in pname or "Investment" in pname:
                program_role_types.add("Asset Management")

    all_role_types = sorted(role_types or program_role_types or [
        "Investment Banking", "Sales & Trading", "Quant", "Research",
        "Asset Management", "Software Engineering", "Data Science"
    ])

    return templates.TemplateResponse("subscribe.html", {
        "request": request,
        "companies": companies,
        "role_types": all_role_types,
    })


# ─── API Endpoints ─────────────────────────────────────────

@app.post("/api/subscribe")
async def api_subscribe(
    email: str = Form(...),
    name: str = Form(""),
    company_ids: list = Form(...),
    role_types: list = Form(...),
    region: str = Form("all"),
):
    """Subscribe to alerts."""
    conn = get_db()

    # Upsert subscriber
    cursor = conn.execute("SELECT id FROM subscribers WHERE email = ?", (email,))
    existing = cursor.fetchone()

    if existing:
        sub_id = existing[0]
        if name:
            conn.execute("UPDATE subscribers SET name = ? WHERE id = ?", (name, sub_id))
    else:
        cursor = conn.execute(
            "INSERT INTO subscribers (email, name) VALUES (?, ?)", (email, name)
        )
        sub_id = cursor.lastrowid

    # Delete old subscriptions for this subscriber
    conn.execute("DELETE FROM subscriptions WHERE subscriber_id = ?", (sub_id,))

    # Insert new subscriptions
    for cid in company_ids:
        for rt in role_types:
            if cid and rt:
                conn.execute(
                    "INSERT INTO subscriptions (subscriber_id, company_id, role_type, region) VALUES (?, ?, ?, ?)",
                    (sub_id, int(cid), rt if rt != "all" else None, region if region != "all" else None)
                )

    conn.commit()
    conn.close()
    return JSONResponse({"status": "ok", "message": "Subscription updated successfully"})


@app.get("/api/predictions")
async def api_predictions(
    region: str = Query("all"),
    role_type: str = Query("all"),
    year: int = 2026,
):
    """API: get predictions."""
    results = get_company_predictions(
        region=region if region != "all" else None,
        role_type=role_type if role_type != "all" else None,
        year=year,
    )
    return JSONResponse(results)


@app.get("/api/timeline")
async def api_timeline(year: int = 2026):
    """API: timeline data for calendar view."""
    conn = get_db()
    conn.row_factory = __import__("sqlite3").Row

    cursor = conn.execute("""
        SELECT c.name, c.region, c.category, ip.program_name,
               ip.predicted_open_date, ip.confidence
        FROM intern_programs ip
        JOIN companies c ON ip.company_id = c.id
        WHERE ip.year = ?
        ORDER BY ip.predicted_open_date ASC
    """, (year,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return JSONResponse(rows)


@app.get("/api/stats")
async def api_stats():
    """API: platform stats."""
    conn = get_db()
    total_companies = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    total_programs = conn.execute("SELECT COUNT(*) FROM intern_programs WHERE year=2026").fetchone()[0]
    total_subscribers = conn.execute("SELECT COUNT(*) FROM subscribers").fetchone()[0]
    total_subs = conn.execute("SELECT COUNT(*) FROM subscriptions WHERE active=1").fetchone()[0]

    by_region = {}
    for row in conn.execute(
        "SELECT region, COUNT(*) FROM companies GROUP BY region"
    ).fetchall():
        by_region[row[0]] = row[1]

    by_category = {}
    for row in conn.execute(
        "SELECT category, COUNT(*) FROM companies GROUP BY category ORDER BY COUNT(*) DESC"
    ).fetchall():
        by_category[row[0]] = row[1]

    conn.close()

    return JSONResponse({
        "total_companies": total_companies,
        "total_programs": total_programs,
        "total_subscribers": total_subscribers,
        "total_subscriptions": total_subs,
        "by_region": by_region,
        "by_category": by_category,
    })


# ─── Run ────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)