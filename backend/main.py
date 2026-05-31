"""
FinanceInternRadar - Main Application
FastAPI backend serving the web interface and API endpoints.
"""

import os
import sys
import sqlite3
import hashlib
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
from crypto_utils import encrypt, decrypt

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


# ─── Admin Auth ──────────────────────────────────────────────
ADMIN_USERNAME = "admin123"
ADMIN_PASSWORD = "Harry071115!"
ADMIN_SALT = "radar_intern_2026_fir"

def _admin_hash(pw: str) -> str:
    return hashlib.sha256((ADMIN_USERNAME + ":" + pw + ADMIN_SALT).encode()).hexdigest()

def verify_admin(request: Request) -> bool:
    token = request.cookies.get("admin_token", "")
    return token == _admin_hash(ADMIN_PASSWORD)

def require_admin(request: Request):
    if not verify_admin(request):
        raise HTTPException(status_code=401, detail="Admin authentication required")


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

    # Early opening alerts (for banner)
    today_str = date.today().isoformat()
    early_alerts = conn.execute("""
        SELECT a.message, a.created_at
        FROM alerts a
        WHERE a.alert_type = 'early_open' AND a.is_read = 0
        ORDER BY a.created_at DESC
        LIMIT 5
    """).fetchall()
    conn.close()

    return templates.TemplateResponse("index.html", {
        "request": request,
        "us_predictions": us_predictions,
        "uk_predictions": uk_predictions,
        "picks": picks,
        "total_companies": total_companies,
        "total_programs": total_programs,
        "early_alerts": early_alerts,
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


@app.get("/admin", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    """Dedicated admin login page."""
    # Already logged in? redirect to dashboard
    if verify_admin(request):
        return RedirectResponse("/admin/dashboard", status_code=302)
    return templates.TemplateResponse("admin_login.html", {"request": request})


@app.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard_page(request: Request):
    """Admin dashboard — user data, program management, alerts."""
    require_admin(request)
    return templates.TemplateResponse("admin_dashboard.html", {"request": request})


# ─── API Endpoints ─────────────────────────────────────────

@app.post("/api/subscribe")
async def api_subscribe(request: Request):
    """Subscribe to alerts. All PII fields are encrypted at rest."""
    form_data = await request.form()
    email = form_data.get("email", "")
    name = form_data.get("name", "")
    age = form_data.get("age", "")
    gender = form_data.get("gender", "")
    school = form_data.get("school", "")
    academic_stage = form_data.get("academic_stage", "")
    graduation_time = form_data.get("graduation_time", "")
    company_ids = form_data.getlist("company_ids")
    role_types = form_data.getlist("role_types")
    region = form_data.get("region", "all")
    conn = get_db()

    # Encrypt all PII before storage
    encrypted_email = encrypt(email) if email else ""
    encrypted_name = encrypt(name) if name else ""
    encrypted_age = encrypt(age) if age else ""
    encrypted_gender = encrypt(gender) if gender else ""
    encrypted_school = encrypt(school) if school else ""
    encrypted_academic_stage = encrypt(academic_stage) if academic_stage else ""
    encrypted_graduation_time = encrypt(graduation_time) if graduation_time else ""
    encrypted_subscribe_companies = encrypt(",".join(company_ids)) if company_ids else ""

    # Upsert subscriber — lookup by encrypted email
    cursor = conn.execute("SELECT id FROM subscribers WHERE email = ?", (encrypted_email,))
    existing = cursor.fetchone()

    if existing:
        sub_id = existing[0]
        conn.execute("""
            UPDATE subscribers SET name = ?, age = ?, gender = ?, school = ?,
                academic_stage = ?, graduation_time = ?, subscribe_companies = ?
            WHERE id = ?
        """, (encrypted_name, encrypted_age, encrypted_gender, encrypted_school,
              encrypted_academic_stage, encrypted_graduation_time,
              encrypted_subscribe_companies, sub_id))
    else:
        cursor = conn.execute(
            "INSERT INTO subscribers (email, name, age, gender, school, academic_stage, graduation_time, subscribe_companies) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (encrypted_email, encrypted_name, encrypted_age, encrypted_gender,
             encrypted_school, encrypted_academic_stage, encrypted_graduation_time,
             encrypted_subscribe_companies)
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
async def api_export(request: Request):
    """Export user data to Excel (admin only). Decrypts data on export."""
    require_admin(request)
    from io import BytesIO
    from datetime import datetime

    conn = get_db()
    wb = __import__("openpyxl").Workbook()

    # Sheet 1: 订阅用户
    ws = wb.active
    ws.title = "订阅用户"
    headers = ["ID", "邮箱", "姓名", "年龄", "性别", "学校", "学业阶段", "毕业时间", "注册时间", "订阅公司数", "职位类型"]
    for c, h in enumerate(headers, 1):
        ws.cell(row=1, column=c, value=h)
    for row_idx, s in enumerate(conn.execute(
        "SELECT id, email, name, age, gender, school, academic_stage, graduation_time, created_at FROM subscribers ORDER BY created_at DESC"
    ).fetchall(), 2):
        sid = s[0]
        cnt = conn.execute("SELECT COUNT(*) FROM subscriptions WHERE subscriber_id=?", (sid,)).fetchone()[0]
        roles = [r[0] for r in conn.execute(
            "SELECT DISTINCT role_type FROM subscriptions WHERE subscriber_id=? AND role_type IS NOT NULL", (sid,)
        ).fetchall()]
        vals = [s[0], decrypt(s[1]), decrypt(s[2]) or "", decrypt(s[3]) or "", decrypt(s[4]) or "",
                decrypt(s[5]) or "", decrypt(s[6]) or "", decrypt(s[7]) or "", s[8], cnt,
                ", ".join(roles) if roles else ""]
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
        vals = [d[0], decrypt(d[1]), decrypt(d[2]) or "", d[3], d[4], d[5], d[6] or ""]
        for c, v in enumerate(vals, 1):
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


# ─── Admin API ───────────────────────────────────────────────

@app.get("/api/admin/userdata")
async def admin_userdata(request: Request):
    """Return decrypted subscriber data (admin only)."""
    require_admin(request)
    conn = get_db()
    rows = conn.execute(
        "SELECT id, email, name, age, gender, school, academic_stage, graduation_time, subscribe_companies, created_at "
        "FROM subscribers ORDER BY created_at DESC"
    ).fetchall()
    conn.close()

    result = []
    for r in rows:
        sid = r[0]
        conn2 = get_db()
        cnt = conn2.execute("SELECT COUNT(*) FROM subscriptions WHERE subscriber_id=?", (sid,)).fetchone()[0]
        roles = [x[0] for x in conn2.execute(
            "SELECT DISTINCT role_type FROM subscriptions WHERE subscriber_id=? AND role_type IS NOT NULL", (sid,)
        ).fetchall()]
        conn2.close()
        result.append({
            "id": r[0],
            "email": decrypt(r[1]),
            "name": decrypt(r[2]) if r[2] else "",
            "age": decrypt(r[3]) if r[3] else "",
            "gender": decrypt(r[4]) if r[4] else "",
            "school": decrypt(r[5]) if r[5] else "",
            "academic_stage": decrypt(r[6]) if r[6] else "",
            "graduation_time": decrypt(r[7]) if r[7] else "",
            "subscribe_companies": decrypt(r[8]) if r[8] else "",
            "created_at": r[9],
            "company_count": cnt,
            "roles": ", ".join(roles) if roles else "",
        })
    return JSONResponse(result)


@app.post("/api/admin/login")
async def admin_login(request: Request):
    data = await request.json()
    username = data.get("username", "")
    pw = data.get("password", "")
    if username == ADMIN_USERNAME and pw == ADMIN_PASSWORD:
        resp = JSONResponse({"status": "ok"})
        resp.set_cookie(
            key="admin_token",
            value=_admin_hash(ADMIN_PASSWORD),
            httponly=True,
            max_age=86400,
            samesite="lax",
        )
        return resp
    return JSONResponse({"status": "error", "message": "用户名或密码错误"}, status_code=401)


@app.post("/api/admin/logout")
async def admin_logout():
    resp = JSONResponse({"status": "ok"})
    resp.delete_cookie("admin_token")
    return resp


@app.get("/api/admin/check")
async def admin_check(request: Request):
    return JSONResponse({"authenticated": verify_admin(request)})


@app.post("/api/admin/programs/{program_id}/mark-open")
async def admin_mark_open(program_id: int, request: Request):
    require_admin(request)
    data = await request.json()
    actual_date = data.get("actual_date", date.today().isoformat())

    conn = get_db()
    prog = conn.execute(
        "SELECT id, program_name, predicted_open_date, company_id FROM intern_programs WHERE id=?",
        (program_id,),
    ).fetchone()
    if not prog:
        conn.close()
        raise HTTPException(status_code=404, detail="Program not found")

    conn.execute(
        "UPDATE intern_programs SET open_date=?, status='open' WHERE id=?",
        (actual_date, program_id),
    )

    is_early = False
    pred_date = prog["predicted_open_date"]
    if pred_date and actual_date < pred_date:
        is_early = True
        company = conn.execute("SELECT name FROM companies WHERE id=?", (prog["company_id"],)).fetchone()
        conn.execute(
            "INSERT INTO alerts (program_id, alert_type, message, is_read) VALUES (?, 'early_open', ?, 0)",
            (program_id, f"{company['name']} - {prog['program_name']}：预测 {pred_date}，实际 {actual_date}（提前开放！）"),
        )
    elif pred_date and actual_date >= pred_date:
        conn.execute(
            "INSERT INTO alerts (program_id, alert_type, message, is_read) VALUES (?, 'now_open', ?, 0)",
            (program_id, f"{prog['program_name']} 已如期开放，实际日期 {actual_date}"),
        )

    conn.commit()
    conn.close()
    return JSONResponse({"status": "ok", "is_early": is_early})


@app.post("/api/admin/programs/{program_id}/mark-closed")
async def admin_mark_closed(program_id: int, request: Request):
    require_admin(request)
    conn = get_db()
    conn.execute("UPDATE intern_programs SET status='closed' WHERE id=?", (program_id,))
    conn.commit()
    conn.close()
    return JSONResponse({"status": "ok"})


@app.get("/api/admin/alerts")
async def admin_alerts(request: Request):
    require_admin(request)
    conn = get_db()
    today = date.today().isoformat()

    # Potential early openings: predicted date passed but still upcoming
    potential = conn.execute("""
        SELECT ip.id, ip.program_name, c.name as company, ip.predicted_open_date, ip.status
        FROM intern_programs ip
        JOIN companies c ON ip.company_id = c.id
        WHERE ip.predicted_open_date <= ?
          AND ip.open_date IS NULL
          AND ip.status = 'upcoming'
        ORDER BY ip.predicted_open_date
    """, (today,)).fetchall()

    # Existing alerts
    alerts = conn.execute("""
        SELECT a.id, a.program_id, a.alert_type, a.message, a.is_read, a.created_at,
               ip.program_name, c.name as company
        FROM alerts a
        JOIN intern_programs ip ON a.program_id = ip.id
        JOIN companies c ON ip.company_id = c.id
        ORDER BY a.created_at DESC
        LIMIT 50
    """).fetchall()

    # Programs grouped by status
    upcoming = conn.execute("""
        SELECT ip.id, ip.program_name, c.name as company, ip.season, ip.year,
               ip.predicted_open_date, ip.open_date, ip.status
        FROM intern_programs ip
        JOIN companies c ON ip.company_id = c.id
        WHERE ip.status = 'upcoming'
        ORDER BY ip.predicted_open_date
        LIMIT 30
    """).fetchall()

    opened = conn.execute("""
        SELECT ip.id, ip.program_name, c.name as company, ip.season, ip.year,
               ip.predicted_open_date, ip.open_date, ip.status
        FROM intern_programs ip
        JOIN companies c ON ip.company_id = c.id
        WHERE ip.status = 'open'
        ORDER BY ip.open_date DESC
    """).fetchall()

    closed = conn.execute("""
        SELECT ip.id, ip.program_name, c.name as company, ip.season, ip.year,
               ip.predicted_open_date, ip.open_date, ip.status
        FROM intern_programs ip
        JOIN companies c ON ip.company_id = c.id
        WHERE ip.status = 'closed'
        ORDER BY ip.open_date DESC
        LIMIT 30
    """).fetchall()

    conn.close()

    def p(r):
        return {
            "id": r["id"], "program_name": r["program_name"], "company": r["company"],
            "season": r["season"], "year": r["year"],
            "predicted_open_date": r["predicted_open_date"], "open_date": r["open_date"],
            "status": r["status"],
        }

    return JSONResponse({
        "potential_early": [
            {"id": r["id"], "program_name": r["program_name"], "company": r["company"],
             "predicted_open_date": r["predicted_open_date"], "status": r["status"]}
            for r in potential
        ],
        "alerts": [
            {"id": r["id"], "program_id": r["program_id"], "alert_type": r["alert_type"],
             "message": r["message"], "is_read": r["is_read"], "created_at": r["created_at"],
             "program_name": r["program_name"], "company": r["company"]}
            for r in alerts
        ],
        "upcoming": [p(r) for r in upcoming],
        "opened": [p(r) for r in opened],
        "closed": [p(r) for r in closed],
    })


@app.post("/api/admin/alerts/{alert_id}/read")
async def admin_mark_read(alert_id: int, request: Request):
    require_admin(request)
    conn = get_db()
    conn.execute("UPDATE alerts SET is_read=1 WHERE id=?", (alert_id,))
    conn.commit()
    conn.close()
    return JSONResponse({"status": "ok"})


# ─── Run ────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)