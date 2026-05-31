"""
Finance Job Radar - FastAPI Application
Multi-region finance job position radar (US/UK/CN/EU/HK/AU).
"""

import os
import csv
import io
from datetime import datetime, date
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from database import get_db, init_db
from predictor import get_job_positions, get_company_predictions, generate_all_predictions
from recommender import get_today_picks
from seed_data import seed
from crypto_utils import encrypt, decrypt, derive_key
from scheduler import get_scheduler

# ─── Config ───
BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
STATIC_DIR = FRONTEND_DIR / "static"
TEMPLATE_DIR = FRONTEND_DIR / "templates"

SECRET_KEY = os.environ.get("RADAR_SECRET_KEY", "radar-dev-secret-key-change-in-production")
ADMIN_USERNAME = os.environ.get("RADAR_ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("RADAR_ADMIN_PASS", "radaradmin2024")

ALL_REGIONS = ["US", "UK", "CN", "EU", "HK", "AU"]
ALL_JOB_TYPES = [
    ("intern", "实习"),
    ("full-time", "全职"),
    ("graduate", "校招/毕业生项目"),
    ("management_trainee", "管培生"),
]
ROLE_TYPES = [
    "Investment Banking", "Sales & Trading", "Quant", "Research",
    "Risk", "Asset Management", "Private Equity",
    "Software Engineering", "Data Science", "Generalist",
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    conn.close()
    if count == 0:
        seed()
        generate_all_predictions(2026)
    get_scheduler().start()
    yield
    get_scheduler().stop()


app = FastAPI(title="金融岗位雷达", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

templates = Jinja2Templates(directory=str(TEMPLATE_DIR))
templates.env.filters["format_date"] = lambda s: (
    datetime.strptime(s, "%Y-%m-%d").strftime("%b %d, %Y") if s else "TBD"
)


def check_admin_session(request: Request):
    if not request.session.get("admin_authenticated"):
        raise HTTPException(status_code=401, detail="Not authenticated")


# ─── Page Routes ───

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    conn = get_db()
    total_companies = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    total_programs = conn.execute("SELECT COUNT(*) FROM job_positions WHERE year = 2026").fetchone()[0]
    conn.close()

    us_predictions = get_job_positions(region="US", year=2026, season="Summer")[:10]
    uk_predictions = get_job_positions(region="UK", year=2026, season="Summer")[:10]
    picks = get_today_picks()

    early_alerts = []
    conn = get_db()
    alert_rows = conn.execute(
        "SELECT message FROM alerts WHERE is_read = 0 ORDER BY created_at DESC LIMIT 3"
    ).fetchall()
    conn.close()
    for r in alert_rows:
        early_alerts.append({"message": r["message"]})

    from scraper import get_engine
    newest_scraped = []
    try:
        engine = get_engine()
        newest_scraped = engine.get_scraped_positions(is_new=1, limit=6)
        engine.close()
    except Exception:
        pass

    return templates.TemplateResponse("index.html", {
        "request": request, "total_companies": total_companies,
        "total_programs": total_programs, "us_predictions": us_predictions,
        "uk_predictions": uk_predictions, "picks": picks, "today": date.today(),
        "early_alerts": early_alerts, "newest_scraped": newest_scraped,
        "all_regions": ALL_REGIONS,
    })


@app.get("/companies", response_class=HTMLResponse)
async def companies_page(request: Request, region: str = "all", category: str = "all",
                         search: str = "", job_type: str = "all"):
    conn = get_db()
    cats = [r["category"] for r in conn.execute(
        "SELECT DISTINCT category FROM companies ORDER BY category"
    ).fetchall()]

    query = "SELECT * FROM companies WHERE 1=1"
    params = []
    if region != "all":
        query += " AND region = ?"; params.append(region)
    if category != "all":
        query += " AND category = ?"; params.append(category)
    if search:
        query += " AND (name LIKE ? OR description LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
    query += " ORDER BY name ASC"

    companies = [dict(r) for r in conn.execute(query, params).fetchall()]
    for c in companies:
        preds = get_job_positions(company_id=c["id"], year=2026)
        if job_type != "all":
            preds = [p for p in preds if p.get("job_type") == job_type]
        c["predictions"] = preds
    conn.close()

    return templates.TemplateResponse("companies.html", {
        "request": request, "companies": companies, "categories": cats,
        "all_regions": ALL_REGIONS, "all_job_types": ALL_JOB_TYPES,
        "filters": {"region": region, "category": category, "search": search, "job_type": job_type},
    })


@app.get("/daily-picks", response_class=HTMLResponse)
async def daily_picks_page(request: Request):
    picks = get_today_picks()
    return templates.TemplateResponse("daily_picks.html", {
        "request": request, "picks": picks, "today": date.today(),
    })


@app.get("/subscribe", response_class=HTMLResponse)
async def subscribe_page(request: Request):
    conn = get_db()
    companies = [dict(r) for r in conn.execute(
        "SELECT id, name, region, category FROM companies ORDER BY region, name"
    ).fetchall()]
    conn.close()
    return templates.TemplateResponse("subscribe.html", {
        "request": request, "companies": companies, "role_types": ROLE_TYPES,
        "all_regions": ALL_REGIONS, "all_job_types": ALL_JOB_TYPES,
    })


@app.get("/admin", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    return templates.TemplateResponse("admin_login.html", {"request": request})


@app.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard_page(request: Request):
    check_admin_session(request)
    return templates.TemplateResponse("admin_dashboard.html", {
        "request": request, "all_regions": ALL_REGIONS, "all_job_types": ALL_JOB_TYPES,
    })


# ─── Public API ───

@app.get("/api/positions")
async def api_positions(
    region: str = Query(None), job_type: str = Query(None),
    season: str = Query("Summer"), year: int = Query(2026),
):
    positions = get_job_positions(region=region, job_type=job_type, season=season, year=year)
    return [{
        "company_name": p["name"], "region": p["region"], "category": p["category"],
        "program_name": p["program_name"], "job_type": p.get("job_type", "intern"),
        "role_type": p.get("role_type", ""), "season": p["season"], "year": p["year"],
        "predicted_open_date": p["predicted_open_date"], "confidence": p["confidence"],
        "status": p["status"], "careers_url": p.get("careers_url", ""),
    } for p in positions]


@app.get("/api/predictions")
async def api_predictions_legacy(region: str = Query(None), season: str = Query("Summer"), year: int = Query(2026)):
    return await api_positions(region=region, season=season, year=year)


@app.get("/api/scraped")
async def api_scraped(
    region: str = Query(None), job_type: str = Query(None),
    verified: int = Query(None), is_new: int = Query(None), limit: int = Query(100),
):
    from scraper import get_engine
    engine = get_engine()
    try:
        return engine.get_scraped_positions(
            region=region, job_type=job_type, verified=verified, is_new=is_new, limit=limit)
    finally:
        engine.close()


@app.get("/api/timeline")
async def api_timeline():
    timeline = {}
    for region in ALL_REGIONS:
        positions = get_job_positions(region=region, year=2026, season="Summer")
        timeline[region] = [
            {"date": p["predicted_open_date"], "company": p["name"], "program": p["program_name"]}
            for p in positions[:8]
        ]
    return timeline


@app.get("/api/stats")
async def api_stats():
    conn = get_db()
    stats = {
        "total_companies": conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0],
        "total_positions": conn.execute("SELECT COUNT(*) FROM job_positions WHERE year=2026").fetchone()[0],
    }
    for region in ALL_REGIONS:
        stats[f"companies_{region}"] = conn.execute(
            "SELECT COUNT(*) FROM companies WHERE region=?", (region,)
        ).fetchone()[0]
    conn.close()
    return stats


@app.post("/api/subscribe")
async def api_subscribe(request: Request):
    form = await request.form()
    email = form.get("email", "").strip()
    name = form.get("name", "").strip()
    age = form.get("age", "").strip()
    gender = form.get("gender", "").strip()
    school = form.get("school", "").strip()
    academic_stage = form.get("academic_stage", "").strip()
    graduation_time = form.get("graduation_time", "").strip()
    company_ids = form.getlist("company_ids")
    role_types = form.getlist("role_types")
    region = form.get("region", "all")

    if not email:
        return JSONResponse({"status": "error", "message": "Email required"}, status_code=400)

    crypto_key = derive_key(SECRET_KEY)
    enc_email = encrypt(email, crypto_key)
    enc_name = encrypt(name, crypto_key) if name else None
    enc_age = encrypt(age, crypto_key) if age else None
    enc_gender = encrypt(gender, crypto_key) if gender else None
    enc_school = encrypt(school, crypto_key) if school else None
    enc_academic_stage = encrypt(academic_stage, crypto_key) if academic_stage else None
    enc_graduation_time = encrypt(graduation_time, crypto_key) if graduation_time else None

    conn = get_db()
    cursor = conn.cursor()
    existing = cursor.execute("SELECT id FROM subscribers WHERE email = ?", (enc_email,)).fetchone()

    if existing:
        sub_id = existing["id"]
        cursor.execute("""
            UPDATE subscribers SET name=?, age=?, gender=?, school=?, academic_stage=?, graduation_time=?,
            subscribe_companies=?
            WHERE id=?""",
            (enc_name, enc_age, enc_gender, enc_school, enc_academic_stage, enc_graduation_time,
             ",".join(company_ids), sub_id))
        cursor.execute("DELETE FROM subscriptions WHERE subscriber_id = ?", (sub_id,))
    else:
        cursor.execute("""
            INSERT INTO subscribers (email, name, age, gender, school, academic_stage, graduation_time, subscribe_companies)
            VALUES (?,?,?,?,?,?,?,?)""",
            (enc_email, enc_name, enc_age, enc_gender, enc_school, enc_academic_stage, enc_graduation_time,
             ",".join(company_ids)))
        sub_id = cursor.lastrowid

    for cid in company_ids:
        for rt in (role_types or [None]):
            cursor.execute(
                "INSERT INTO subscriptions (subscriber_id, company_id, role_type, region) VALUES (?,?,?,?)",
                (sub_id, int(cid) if cid != "all" else None, rt, region if region != "all" else None))

    conn.commit()
    conn.close()
    return {"status": "ok", "message": "Subscribed successfully"}


@app.get("/api/export")
async def api_export(request: Request):
    check_admin_session(request)
    conn = get_db()
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["=== 公司岗位 ==="])
    writer.writerow(["公司", "地区", "类别", "项目名称", "岗位类型", "角色类型", "季节", "年份", "预测开放日", "置信度", "状态"])
    for r in conn.execute("""
        SELECT c.name, c.region, c.category, jp.program_name, jp.job_type, jp.role_type,
               jp.season, jp.year, jp.predicted_open_date, jp.confidence, jp.status
        FROM job_positions jp JOIN companies c ON jp.company_id = c.id
        WHERE jp.year=2026 ORDER BY c.region, jp.predicted_open_date
    """).fetchall():
        writer.writerow([r["name"], r["region"], r["category"], r["program_name"],
                         r["job_type"] or "", r["role_type"] or "",
                         r["season"], r["year"], r["predicted_open_date"], r["confidence"], r["status"]])

    writer.writerow([])
    writer.writerow(["=== 抓取岗位 ==="])
    writer.writerow(["标题", "公司", "岗位类型", "地区", "发布日期", "状态"])
    for r in conn.execute("""
        SELECT sp.title, c.name as company_name, sp.job_type, sp.region, sp.posted_date,
               CASE WHEN sp.is_verified THEN '已验证' WHEN sp.is_new THEN '新发现' ELSE '已忽略' END as status
        FROM scraped_positions sp
        LEFT JOIN scraping_sources ss ON sp.source_id = ss.id
        LEFT JOIN companies c ON ss.company_id = c.id
        ORDER BY sp.scraped_at DESC LIMIT 500
    """).fetchall():
        writer.writerow([r["title"], r["company_name"] or "", r["job_type"] or "",
                         r["region"] or "", r["posted_date"] or "", r["status"]])

    writer.writerow([])
    writer.writerow(["=== 订阅用户 ==="])
    crypto_key = derive_key(SECRET_KEY)
    writer.writerow(["ID", "邮箱", "姓名", "年龄", "性别", "学校", "学业阶段", "毕业时间", "注册时间"])
    for r in conn.execute("SELECT * FROM subscribers ORDER BY id").fetchall():
        try:
            row = [r["id"], decrypt(r["email"], crypto_key),
                   decrypt(r.get("name") or "", crypto_key),
                   decrypt(r.get("age") or "", crypto_key),
                   decrypt(r.get("gender") or "", crypto_key),
                   decrypt(r.get("school") or "", crypto_key),
                   decrypt(r.get("academic_stage") or "", crypto_key),
                   decrypt(r.get("graduation_time") or "", crypto_key), r["created_at"]]
        except Exception:
            row = [r["id"], "***encrypted***", "", "", "", "", "", "", r["created_at"]]
        writer.writerow(row)

    conn.close()
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]), media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": f"attachment; filename=FinanceJobRadar_{date.today().isoformat()}.csv"})


# ─── Admin API ───

@app.post("/api/admin/login")
async def admin_login(request: Request):
    form = await request.form()
    if form.get("username") == ADMIN_USERNAME and form.get("password") == ADMIN_PASSWORD:
        request.session["admin_authenticated"] = True
        return RedirectResponse(url="/admin/dashboard", status_code=303)
    return JSONResponse({"status": "error", "message": "Invalid credentials"}, status_code=401)


@app.post("/api/admin/logout")
async def admin_logout(request: Request):
    request.session.clear()
    return {"status": "ok"}


@app.get("/api/admin/check")
async def admin_check(request: Request):
    return {"authenticated": bool(request.session.get("admin_authenticated"))}


@app.get("/api/admin/userdata")
async def admin_userdata(request: Request):
    check_admin_session(request)
    conn = get_db()
    crypto_key = derive_key(SECRET_KEY)
    users = []
    for r in conn.execute("SELECT * FROM subscribers ORDER BY id DESC").fetchall():
        try:
            users.append({
                "id": r["id"], "email": decrypt(r["email"], crypto_key),
                "name": decrypt(r.get("name") or "", crypto_key),
                "age": decrypt(r.get("age") or "", crypto_key),
                "gender": decrypt(r.get("gender") or "", crypto_key),
                "school": decrypt(r.get("school") or "", crypto_key),
                "academic_stage": decrypt(r.get("academic_stage") or "", crypto_key),
                "graduation_time": decrypt(r.get("graduation_time") or "", crypto_key),
                "created_at": r["created_at"],
                "company_count": len((r.get("subscribe_companies") or "").split(",")),
                "roles": (r.get("subscribe_companies") or "")[:60],
            })
        except Exception:
            users.append({
                "id": r["id"], "email": "[Decryption error]",
                "name": "", "age": "", "gender": "", "school": "",
                "academic_stage": "", "graduation_time": "",
                "created_at": r["created_at"], "company_count": 0, "roles": "",
            })
    conn.close()
    return users


@app.get("/api/admin/alerts")
async def admin_alerts(request: Request):
    check_admin_session(request)
    conn = get_db()
    potential_early = [dict(r) for r in conn.execute("""
        SELECT c.name as company, jp.program_name, jp.predicted_open_date
        FROM job_positions jp JOIN companies c ON jp.company_id = c.id
        WHERE jp.status = 'open' AND jp.open_date < jp.predicted_open_date
        ORDER BY jp.open_date DESC LIMIT 10
    """).fetchall()]
    upcoming = [dict(r) for r in conn.execute(
        "SELECT jp.id, c.name as company, jp.program_name, jp.predicted_open_date FROM job_positions jp JOIN companies c ON jp.company_id = c.id WHERE jp.status='upcoming' ORDER BY jp.predicted_open_date LIMIT 30"
    ).fetchall()]
    opened = [dict(r) for r in conn.execute(
        "SELECT jp.id, c.name as company, jp.program_name, jp.open_date FROM job_positions jp JOIN companies c ON jp.company_id = c.id WHERE jp.status='open' ORDER BY jp.open_date DESC LIMIT 30"
    ).fetchall()]
    closed = [dict(r) for r in conn.execute(
        "SELECT jp.id, c.name as company, jp.program_name, jp.open_date FROM job_positions jp JOIN companies c ON jp.company_id = c.id WHERE jp.status='closed' ORDER BY jp.open_date DESC LIMIT 30"
    ).fetchall()]
    alerts = [dict(r) for r in conn.execute("SELECT * FROM alerts ORDER BY created_at DESC LIMIT 50").fetchall()]
    conn.close()
    return {"potential_early": potential_early, "upcoming": upcoming, "opened": opened, "closed": closed, "alerts": alerts}


@app.post("/api/admin/programs/{program_id}/mark-open")
async def mark_open(program_id: int, request: Request):
    check_admin_session(request)
    body = await request.json()
    actual_date = body.get("actual_date", date.today().isoformat())
    conn = get_db()
    cursor = conn.cursor()
    prog = cursor.execute("SELECT * FROM job_positions WHERE id = ?", (program_id,)).fetchone()
    if not prog:
        conn.close()
        raise HTTPException(404, "Program not found")
    cursor.execute("UPDATE job_positions SET status='open', open_date=? WHERE id=?", (actual_date, program_id))
    comp = cursor.execute("SELECT name FROM companies WHERE id=?", (prog["company_id"],)).fetchone()
    if prog["predicted_open_date"] and actual_date < prog["predicted_open_date"]:
        msg = f"{comp['name']} - {prog['program_name']} 提前开放！预测 {prog['predicted_open_date']}，实际 {actual_date}"
        cursor.execute("INSERT INTO alerts (program_id, alert_type, message) VALUES (?, 'early_open', ?)", (program_id, msg))
    else:
        msg = f"{comp['name']} - {prog['program_name']} 如期于 {actual_date} 开放"
        cursor.execute("INSERT INTO alerts (program_id, alert_type, message) VALUES (?, 'now_open', ?)", (program_id, msg))
    conn.commit()
    conn.close()
    return {"status": "ok"}


@app.post("/api/admin/programs/{program_id}/mark-closed")
async def mark_closed(program_id: int, request: Request):
    check_admin_session(request)
    conn = get_db()
    conn.execute("UPDATE job_positions SET status='closed' WHERE id=?", (program_id,))
    conn.commit()
    conn.close()
    return {"status": "ok"}


# ─── Scraping Admin ───

@app.get("/api/admin/scrape/status")
async def scrape_status(request: Request):
    check_admin_session(request)
    sched = get_scheduler()
    status = sched.get_status()
    from scraper import get_engine
    engine = get_engine()
    try:
        scrape_status = engine.get_scraping_status()
    finally:
        engine.close()
    return {"scheduler": status, "scraping": scrape_status}


@app.post("/api/admin/scrape/trigger")
async def scrape_trigger(request: Request):
    check_admin_session(request)
    return get_scheduler().trigger_now()


@app.post("/api/admin/scraped/{position_id}/verify")
async def scraped_verify(position_id: int, request: Request):
    check_admin_session(request)
    from scraper import get_engine
    engine = get_engine()
    try:
        engine.verify_position(position_id, True)
        return {"status": "ok", "message": f"Position {position_id} verified"}
    finally:
        engine.close()


@app.post("/api/admin/scraped/{position_id}/dismiss")
async def scraped_dismiss(position_id: int, request: Request):
    check_admin_session(request)
    from scraper import get_engine
    engine = get_engine()
    try:
        engine.dismiss_position(position_id)
        return {"status": "ok", "message": f"Position {position_id} dismissed"}
    finally:
        engine.close()


@app.get("/api/health")
async def health():
    conn = get_db()
    try:
        conn.execute("SELECT 1 FROM companies LIMIT 1")
        db_ok = True
    except Exception:
        db_ok = False
    conn.close()
    return {"status": "ok", "db": db_ok, "timestamp": datetime.now().isoformat()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
