# FinanceInternRadar

Track, predict, and get alerted on finance internship application openings.

**32 companies • US & UK • 2026 Summer Cycle**

## What It Does

FinanceInternRadar predicts when finance internship applications will open, helps students track programs they care about, and alerts them before deadlines. If a program opens earlier than predicted, the system detects it and notifies both visitors and administrators.

### Core Features

- **Opening Date Predictions** — Uses historical opening data to predict when each program will open applications for the 2026 cycle
- **Daily Picks** — Surfaces hidden-gem firms that most students overlook (quant funds, prop trading, fintech)
- **Timeline View** — See all upcoming openings in chronological order by region
- **Company Browser** — Filter by region, category, and role type with search
- **Subscription System** — Pick companies and role types you care about; get notified before they open
- **Early Opening Detection** — When a program opens earlier than predicted, the system flags it and shows a banner alert on the homepage
- **Admin Dashboard** — Password-protected panel for managing program statuses, viewing alerts, and exporting subscriber data to Excel

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI (Python) |
| Frontend | Jinja2 Templates + Vanilla JS |
| Database | SQLite (WAL mode) |
| Deployment | Docker + Render |
| Spreadsheet | openpyxl (Excel export) |

## Project Structure

```
FinanceInternRadar/
├── backend/
│   ├── main.py              # FastAPI app, all routes & admin API
│   ├── database.py          # SQLite schema & connection
│   ├── predictor.py         # Opening date prediction engine
│   ├── recommender.py       # Daily picks algorithm
│   ├── scraper.py           # Career page scraper (future use)
│   ├── seed_data.py         # Initial 32-company dataset
│   ├── notifier.py          # Email notification framework
│   └── data/                # SQLite database & historical data
├── frontend/
│   ├── templates/
│   │   ├── base.html        # Base layout with nav
│   │   ├── index.html       # Homepage with timeline + picks
│   │   ├── companies.html   # Filterable company grid
│   │   ├── daily_picks.html # Daily recommendations
│   │   └── subscribe.html   # Subscription form + admin login
│   └── static/
│       ├── css/style.css
│       └── js/app.js
├── export_users.py          # Standalone Excel export script
├── requirements.txt
├── Dockerfile
└── render.yaml              # Render deployment config
```

## Quick Start

### Prerequisites

- Python 3.10+
- pip

### Local Setup

```bash
# Clone the repo
git clone https://github.com/HastingsHe/FinanceInternRadar.git
cd FinanceInternRadar

# Install dependencies
pip install -r requirements.txt

# Seed the database and generate predictions
cd backend
python -c "from database import init_db; init_db(); from seed_data import seed; seed(); from predictor import generate_all_predictions; generate_all_predictions(2026)"

# Start the server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Open [http://localhost:8000](http://localhost:8000) in your browser.

## API Endpoints

### Public

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Homepage with timeline + daily picks |
| GET | `/companies` | Browse & filter companies |
| GET | `/daily-picks` | Today's hidden-gem picks |
| GET | `/subscribe` | Subscription form |
| POST | `/api/subscribe` | Submit subscription |
| GET | `/api/stats` | Platform statistics |
| GET | `/api/predictions` | Opening date predictions |
| GET | `/api/timeline` | Chronological opening timeline |

### Admin (Password Protected)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/admin/login` | Admin authentication |
| POST | `/api/admin/logout` | Clear admin session |
| GET | `/api/admin/check` | Verify authentication |
| GET | `/api/admin/alerts` | Dashboard: alerts + program management data |
| POST | `/api/admin/programs/{id}/mark-open` | Mark program as opened (auto-detects early opening) |
| POST | `/api/admin/programs/{id}/mark-closed` | Mark program as closed |
| POST | `/api/admin/alerts/{id}/read` | Mark alert as read |
| GET | `/api/export` | Download subscriber data as Excel |

## Early Opening Detection

The system has a two-layer early opening detection mechanism:

1. **Passive Detection** — When the admin marks a program as "opened", the system compares the actual opening date against the predicted date. If the actual date is earlier, an `early_open` alert is created automatically.

2. **Proactive Monitoring** — The admin dashboard checks for programs whose predicted opening date has passed but are still marked as "upcoming". These appear as "potential early openings" for the admin to investigate.

When an unread early opening alert exists, a warning banner is displayed on the homepage for all visitors.

## Deployment

The project is configured for [Render](https://render.com) deployment via `render.yaml`:

```yaml
services:
  - type: web
    buildCommand: pip install -r requirements.txt
    startCommand: cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT
```

### Docker

```bash
docker build -t finance-intern-radar .
docker run -p 8000:8000 finance-intern-radar
```

## Data Coverage

| Region | Companies | Programs |
|--------|-----------|----------|
| US | 24 | 16 |
| UK | 8 | 5 |
| **Total** | **32** | **21** |

Categories: Bulge Bracket, Boutique, Prop Trading, Hedge Fund, Asset Management, Quant, FinTech

## License

MIT
