"""
FinanceInternRadar - Main Application
FastAPI backend serving the web interface and API endpoints.
"""

import os
import sys
import sqlite3
from datetime import datetime, date
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, StreamingResponse
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
async def api_subscribe(request: Request):
    """Subscribe to alerts."""
    form_data = await request.form()
    email = form_data.get("email", "")
    name = form_data.get("name", "")
    company_ids = form_data.getlist("company_ids")
    role_types = form_data.getlist("role_types")
    region = form_data.get("region", "all")
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
    total_subs = conn.execute("SELECT COUNT(*) FROM subscriptions").fetchone()[0]

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


@app.get("/api/export")
async def api_export():
    """Export user data to Excel and return the file."""
    from io import BytesIO
    from datetime import datetime

    conn = get_db()
    wb = __import__("openpyxl").Workbook()

    # Sheet 1: 订阅用户
    ws = wb.active
    ws.title = "订阅用户"
    headers = ["ID", "邮箱", "姓名", "注册时间", "订阅公司数", "职位类型"]
    for c, h in enumerate(headers, 1):
        ws.cell(row=1, column=c, value=h)
    for row_idx, s in enumerate(conn.execute(
        "SELECT id, email, name, created_at FROM subscribers ORDER BY created_at DESC"
    ).fetchall(), 2):
        sid = s[0]
        cnt = conn.execute("SELECT COUNT(*) FROM subscriptions WHERE subscriber_id=?", (sid,)).fetchone()[0]
        roles = [r[0] for r in conn.execute(
            "SELECT DISTINCT role_type FROM subscriptions WHERE subscriber_id=? AND role_type IS NOT NULL", (sid,)
        ).fetchall()]
        vals = [s[0], s[1], s[2] or "", s[3], cnt, ", ".join(roles) if roles else ""]
        for c, v in enumerate(vals, 1):
            ws.cell(row=row_idx, column=c, value=v)

    # Sheet 2: 订阅明细
    ws2 = wb.create_sheet("订阅明细")
    headers2 = ["订阅ID", "用户邮箱", "用户姓名", "公司", "地区", "类别", "职位"]
    for c, h in enumerate(headers2, 1):
        ws2.cell(row=1, column=c, value=h)
    for row_idx, d in enumerate(conn.execute("""
        SELECT s.id, sub.email, sub.name, c.name, c.region, c.category, s.role_type
        FROM subscriptions s
        JOIN subscribers sub ON s.subscriber_id=sub.id
        LEFT JOIN companies c ON s.company_id=c.id
        ORDER BY sub.email, c.name
    """).fetchall(), 2):
        for c, v in enumerate([d[i] or "" for i in range(7)], 1):
            ws2.cell(row=row_idx, column=c, value=v)

    # Sheet 3: 统计
    ws3 = wb.create_sheet("统计")
    ws3.cell(row=1, column=1, value=f"FinanceInternRadar - 导出于 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    r = 3
    ws3.cell(row=r, column=1, value="订阅用户数"); ws3.cell(row=r, column=2, value=conn.execute("SELECT COUNT(*) FROM subscribers").fetchone()[0]); r += 1
    ws3.cell(row=r, column=1, value="订阅记录数"); ws3.cell(row=r, column=2, value=conn.execute("SELECT COUNT(*) FROM subscriptions").fetchone()[0]); r += 2
    ws3.cell(row=r, column=1, value="地区分布"); r += 1
    for reg in conn.execute("SELECT c.region, COUNT(*) c FROM subscriptions s JOIN companies c ON s.company_id=c.id GROUP BY c.region"):
        ws3.cell(row=r, column=1, value=reg[0]); ws3.cell(row=r, column=2, value=reg[1]); r += 1

    conn.close()
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=FinanceInternRadar_Users.xlsx"},
    )


# ─── Run ────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)