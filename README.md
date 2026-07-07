# ApexGrid — F1 Analytics & Telemetry Platform

> A production-grade Formula 1 analytics platform with real telemetry data, a live AI race analyst, and an interactive ECharts dashboard. Built end-to-end: data engineering → REST API → frontend → AI integration.

**[Live Dashboard](https://shubhammadihalli.github.io/F1-Analytics/)** &nbsp;·&nbsp; **[API Docs](https://f1-analytics-api.onrender.com/docs)**

---

## What It Does

ApexGrid ingests live Formula 1 data from the [OpenF1 public API](https://openf1.org), stores it in PostgreSQL, exposes it through a paginated REST API, and serves a dark-mode ECharts dashboard with an **AI Analyst tab** powered by Llama 3.3 70B via Groq.

Ask it anything:
- *"Why did Leclerc win the British GP?"*
- *"How consistent has Antonelli been this season?"*
- *"Compare Russell and Norris head to head"*

The AI fetches real race data from the database at request time — lap times, tyre strategy, pit stops, weather — and grounds every answer in actual numbers, not training memory.

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Data ingestion** | Python 3.12, httpx (async), Tenacity (retry + backoff), Pandas |
| **Database** | PostgreSQL, SQLAlchemy 2.0 ORM, Alembic migrations |
| **API** | FastAPI, Pydantic v2, in-process TTL cache, Uvicorn |
| **AI** | Groq API · Llama 3.3 70B · RAG pattern · structured context injection |
| **Frontend** | Vanilla JS, ECharts 5.5, React 18 (runtime), Google Fonts |
| **Deployment** | GitHub Pages (frontend) + Render free tier (backend + Postgres) |
| **Testing** | pytest · 74 tests across backend + API clients |
| **Tooling** | Ruff · mypy · pyproject.toml |

---

## Architecture

```
GitHub Pages                      Render (Oregon)
┌─────────────────────┐           ┌──────────────────────────────┐
│  index.html         │  HTTPS    │  FastAPI + Uvicorn           │
│  f1-api.js  ────────┼──GET/POST▶│  /api/v1/*  (15 endpoints)  │
│  support.js         │           │  /ai/analyze (Groq RAG)      │
│  (ECharts, React)   │           │  StaticFiles at /            │
└─────────────────────┘           └──────────────┬───────────────┘
        │                                         │ psycopg3
        └── CDN: unpkg, jsdelivr,        PostgreSQL (Render)
                 Google Fonts                     │
                                       ETL: python etl.py
                                       (OpenF1 → Postgres, incremental)
```

---

## Features

### Dashboard Pages

| Page | Content |
|---|---|
| **Overview** | Championship & constructor standings, points progression, win distribution, season calendar |
| **Drivers** | Finish positions, lap pace, qualifying trend, grid vs finish scatter, performance radar, points progression |
| **Races** | Lap chart, position changes, tyre strategy Gantt, pit stops, weather, fastest laps, sector comparison |
| **Telemetry** | Speed · Throttle · Brake · Gear · RPM · DRS · Acceleration · Distance — with multi-driver overlay and zoom |
| **Head to Head** | Wins, podiums, poles, fastest laps, avg finish, avg qualifying, radar chart, quali vs finish scatter |
| **AI Analyst** | Natural language Q&A grounded in real race data via Groq Llama 3.3 70B |

### Extra Features

- **Search** — find any driver, race, constructor, or circuit
- **Favourites** — pin drivers and see their points in a quick-access strip
- **Live Refresh** — configurable auto-refresh (30s / 60s / 5 min)
- **Export** — CSV download for tables; PNG via ECharts toolbar
- **Cold-start banner** — detects Render wake-up and auto-retries with countdown

---

## AI Analyst — How It Works

The AI tab implements a **RAG (Retrieval-Augmented Generation)** pipeline:

```
User question
      │
      ▼
POST /api/v1/ai/analyze
      │
      ├─ 1. RETRIEVE — query PostgreSQL for relevant context
      │      Race:    results + lap times + tyre stints + pit stops + weather
      │      Season:  driver standings + podium results across all rounds
      │      Driver:  race-by-race results + qualifying positions per round
      │      H2H:     side-by-side race stats for two drivers
      │
      ├─ 2. FORMAT — convert DB rows to structured markdown
      │      "P1: Charles LECLERC — 52 laps, WINNER
      │       Tyre: MEDIUM laps 1–25 → HARD laps 26–48 → SOFT laps 49–52
      │       Pit stop lap 25: 28.40s …"
      │
      └─ 3. GENERATE — send context + question to Groq Llama 3.3 70B
             Return grounded answer + data sources used + token count
```

**Why RAG?** Asking an LLM without context produces generic or hallucinated answers. By injecting the actual race data as context, the model reasons over *your* data — making answers accurate, specific, and always current (the ETL updates after every race weekend).

**Why Groq?** Free tier, no credit card, ~400 tokens/second (10× faster than standard OpenAI), runs Meta's open-source Llama 3.3 70B.

---

## Data Pipeline

```
OpenF1 Public API ──async httpx──▶ ETL Pipelines ──SQLAlchemy──▶ PostgreSQL
                                    (incremental)
  Sessions, Drivers, Circuits         14 tables
  Race Results, Lap Times             8 Alembic migrations
  Car Telemetry (~33K rows/driver)    ~2.7M telemetry rows per season
  Weather, Positions, Stints
  Pit Stops, Starting Grid
```

The ETL is **incremental and idempotent** — re-running skips already-ingested sessions and only fetches new data from OpenF1.

---

## API Endpoints

```
GET  /api/v1/drivers                  all drivers
GET  /api/v1/driver/{number}          driver detail + career stats
GET  /api/v1/races                    sessions (filterable by year, type)
GET  /api/v1/results                  race classifications
GET  /api/v1/laps                     lap-by-lap timing
GET  /api/v1/telemetry                car telemetry (session + driver required)
GET  /api/v1/weather                  track / air conditions
GET  /api/v1/standings                driver or constructor championship
GET  /api/v1/constructors             team roster + colours
GET  /api/v1/head-to-head             driver vs driver comparison
GET  /api/v1/stints                   tyre stint data
GET  /api/v1/pit-stops                pit stop timing
GET  /api/v1/positions                position-over-time (race replay)
GET  /api/v1/starting-grid            grid positions
POST /api/v1/ai/analyze               natural language AI analysis (Groq)
GET  /api/v1/health                   liveness + DB connectivity check
```

Full interactive docs at `/docs` (Swagger UI).

---

## Run Locally

**Prerequisites:** Python 3.12+, PostgreSQL running locally

```bash
# 1. Clone and install
git clone https://github.com/shubhammadihalli/F1-Analytics.git
cd F1-Analytics
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements/backend.txt -r requirements/etl.txt

# 2. Configure
cp .env.example .env
# Set DATABASE_URL and GROQ_API_KEY (free key at console.groq.com)

# 3. Create DB and run migrations
createdb f1_analytics
alembic -c database/alembic.ini upgrade head

# 4. Ingest F1 data (incremental, safe to re-run)
python etl.py

# 5. Start server — serves API + dashboard on one port
PYTHONPATH=. uvicorn backend.main:app --port 8000
```

Open **http://localhost:8000** — API and dashboard in a single process.

---

## Project Structure

```
F1-Analytics/
├── api_clients/           async HTTP clients (OpenF1, rate limiting, retry)
├── backend/
│   ├── api/v1/endpoints/  15 FastAPI endpoint modules
│   ├── core/              config, TTL cache, exceptions, query helpers
│   ├── schemas/           Pydantic v2 response models
│   └── tests/             27 backend tests (real DB, no mocks)
├── database/
│   ├── migrations/        8 Alembic migration files
│   └── session.py         SQLAlchemy engine + session factory
├── etl/
│   ├── cli.py             Typer CLI entry point
│   ├── pipelines/         one ingest_*.py per data type
│   └── loaders/           generic upsert / replace helpers
├── models/                14 SQLAlchemy ORM models
├── web/                   static frontend (served by FastAPI at /)
│   ├── index.html         ECharts dashboard + AI Analyst UI
│   ├── f1-api.js          data layer — fetch() calls to /api/v1
│   └── support.js         Claude Design runtime (React 18, Babel)
├── render.yaml            Render Blueprint (Postgres + web service)
├── .github/workflows/     GitHub Actions Pages deploy
└── etl.py                 root shim — python etl.py
```

---

## Data Source

Race data is sourced from the [OpenF1 API](https://openf1.org) — a free, public Formula 1 telemetry and timing API. No API key required for data ingestion.
