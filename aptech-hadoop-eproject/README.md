# EarthScape Climate Agency: Climate Change Analysis and Monitoring System

A web platform that collects, stores (Hadoop HDFS), processes (MapReduce), analyses (machine learning) and visualises climate data, with alerts, reports, support and role-based access.

Full documentation: [docs/PROJECT_DOCUMENTATION.md](docs/PROJECT_DOCUMENTATION.md)

---

## Quick start (Windows)

```bash
cd aptech-hadoop-eproject
pip install -r requirements.txt
python manage.py migrate
python manage.py setup_earthscape        # roles, alert rules, sample readings, trains models, runs jobs
python manage.py createsuperuser         # your Administrator account
python manage.py runserver
```

Open:

| What | URL |
|---|---|
| Public website | http://127.0.0.1:8000/climatechanges/ |
| Sign up / log in | http://127.0.0.1:8000/climatechanges/signup/ · `/login/` |
| **Console (dashboard)** | http://127.0.0.1:8000/climatechanges/console/ |
| Django admin | http://127.0.0.1:8000/admin/ |
| HDFS web UI | http://localhost:50070 |

New sign-ups get the **Climate Analyst** role. A superuser counts as **Administrator**, and administrators can promote other users under *User Management*.

## EarthScape Assistant (chatbot)

A floating chat widget on every page (public site and console). It answers questions about climate change and the site using a live snapshot of the app's own data (temperature anomaly, recorded disasters, forecast).

- Backend: `climatechanges/chatbot.py`, endpoint `POST /climatechanges/api/chat/`. The browser never sees the API key.
- Provider: [Groq](https://groq.com) (model `openai/gpt-oss-20b`). Set **`GROQ_API_KEY`** as an environment variable (locally in a git-ignored `.env`; on Vercel under Project Settings -> Environment Variables). Optional: `GROQ_MODEL`, `CHAT_DAILY_LIMIT` (default 400 messages/day per server instance).
- Cost controls: short replies (max 600 tokens), last 6 messages of history, 600 characters per message, 15 messages per visitor per 10 minutes, a daily cap, and a one-hour cache for repeated first questions.
- Without a key, or if Groq is unreachable, it falls back to local answers built from the site's data, so the widget never breaks.
- Tests: `python manage.py test climatechanges.tests_chatbot` (no network or API credits used).

## Vercel preview

The repository root is configured to build and serve this Django project through `api/index.py`. Pushes to a Git-connected Vercel project create preview deployments. The serverless demo stores its SQLite database, uploaded files, logs and encryption key under `/tmp/earthscape`; these are temporary and can reset between instances. For persistent accounts and uploads, configure a hosted database and object storage before production use. Hadoop/HDFS requires a reachable external WebHDFS cluster; without one, the app reports that it is using local staging (also temporary on Vercel).

## Hadoop (optional but supported)

```bash
hadoop\start_hdfs.cmd       # formats HDFS on first run, starts NameNode + DataNode, uploads the CSVs
hadoop\run_mapreduce.cmd    # runs the disasters-per-year job with Hadoop Streaming, prints the result
```

When HDFS is running, the console shows **HDFS online**, "Store in HDFS" writes real files through WebHDFS, and the job *"Climate disasters per year on Hadoop"* runs a real Hadoop Streaming job and reads its output back from HDFS.
When HDFS is **not** running, the app says so, stores files in `data/hdfs_staging/` (same folder layout), and runs MapReduce jobs on its built-in local engine. It never claims Hadoop ran when it didn't.

### HDFS troubleshooting

- **"Safe mode is ON" never clears / DataNode exits with "Storage directory ... does not exist":** the DataNode folder (`C:\hadoop\hadoop-2.9.2\data\datanode`) belongs to an older NameNode format. Stop HDFS, rename that folder (e.g. `datanode.old`), create an empty `datanode` folder, start HDFS, run `hdfs dfsadmin -safemode leave`, delete any `CORRUPT` entries with `hdfs dfs -rm -r /climate`, then run `hadoop\start_hdfs.cmd` to re-upload the CSVs.
- **Console says "MongoDB not reachable":** `pip install pymongo==4.10.1` and make sure the MongoDB service is running, then `python manage.py sync_mongodb`.

## The console (sidebar)

1. **Overview**: KPIs (global temperature change, average temperature, rainfall, humidity, CO₂, anomalies, processing stats), trend + forecast, recent alerts, filters (date range, country, region, variable)
2. **Climate Analytics**: temperature trends, historical vs predicted, anomaly world map, rainfall comparison, humidity by region, CO₂ trend, regional comparison, decade patterns
3. **Data Management**: CSV/JSON table upload with profiling, cleaning and import; GeoTIFF imagery cataloguing and HDFS storage; upload history
4. **Data Processing**: HDFS status, MapReduce/ML/alert jobs, Hadoop Streaming job, live data pull, job history, performance monitoring, logs, backups
5. **Predictions**: temperature trend models compared on held-out years, forecast with uncertainty band, rainfall model vs seasonal baseline, actual-vs-predicted charts, run history
6. **Anomaly Detection**: z-score anomalies (real data), Isolation Forest on station readings, anomaly map, temperature vs disasters correlation, correlation matrix
7. **Alerts**: history with severity, read/unread and filters; configurable threshold rules (administrators); in-app bell notifications
8. **Reports**: summary, temperature, rainfall, anomalies, predictions and regional reports as **PDF** or **CSV**
9. **Support**: submit questions, problems and feedback; track status; administrators reply and resolve
10. **Settings**: profile, password change (+ **User Management** for administrators)

## Aptech brief: non-functional requirements and software list

| Brief | Where |
|---|---|
| Performance + resource monitoring | Data Processing page: request timings, CPU/memory/disk/process charts, job durations |
| Data security (encryption) | uploads, cleaned files and backups encrypted at rest (`climatechanges/crypto.py`, key in `keys/data.key`); HTTPS/HSTS via Apache (`deploy/apache-earthscape.conf`, `EARTHSCAPE_HTTPS=1`) |
| Reliability: 99% uptime, maintenance notices, automated backups | health check `/climatechanges/api/health/`; Settings → maintenance notices (banner on every page); `deploy\schedule_backup.cmd`; `restore_earthscape` |
| Scalability + load balancing | `deploy\run_instances.cmd 3` (Waitress) behind Apache `mod_proxy_balancer` |
| Compliance and standards | SI units, ISO 8601 UTC, WGS 84/GeoJSON, ISO 3166 codes, provenance labels (Help Center → Data standards) |
| User docs, FAQs, tutorials | console **Help Center** |
| Developer docs | `docs/PROJECT_DOCUMENTATION.md`, `Project_Report.docx` |
| Video | record with `docs/VIDEO_SCRIPT.md` |
| Jupyter / RStudio / VS Code | `notebooks/ml_exploration.ipynb`, `analysis/climate_analysis.R` |
| MongoDB Compass + Shell | `mongodb://127.0.0.1:27017` → `earthscape`; `python manage.py sync_mongodb` |
| Hadoop, HDFS, Apache server | `hadoop/`, `deploy/` |
| Tableau | Reports → Tableau / BI extract; `docs/TABLEAU_GUIDE.md` |
| Impala | `hadoop/impala_tables.sql` |
| Deliverables | `ReadMe.doc` (assumptions), `Project_Report.docx`, `sample_data/` (test data) |

## Real vs sample data

| Data | Status |
|---|---|
| Satellite imagery | Uploaded GeoTIFF sources can be encrypted, catalogued and stored in HDFS; raster analysis is not implemented |
| Temperature change per country/region 1961-2023 (FAO) | **real** |
| Climate disasters per country 1980-2024 (EM-DAT via IMF) | **real** |
| Forest carbon stocks 1992-2023 (FAO) | **real** |
| CO₂ (NOAA Mauna Loa via global-warming.org) | **real**, fetched by *Pull live data* |
| Live station weather (Open-Meteo) | **real**, fetched by *Pull live data* |
| Station rainfall/humidity/temperature history 2015-2025 | **sample** (synthetic), made by `seed_sample_data`, labelled "sample data" everywhere |

Every reading stores its `source`, and every chart or KPI built from readings shows a *real / sample / mixed* badge.

## Real-time ingestion API

```bash
curl -X POST http://127.0.0.1:8000/climatechanges/api/ingest/ -H "X-API-Token: dev-ingest-token-change-me" -H "Content-Type: application/json" -d @sample_data/sensor_reading_example.json
```

Set your own token with the environment variable `EARTHSCAPE_INGEST_TOKEN`. New readings are checked against alert rules immediately.

## Tests

```bash
python manage.py test climatechanges
```

44 tests: registration/login, roles, uploads and validation, cleaning/import/storage, ingestion API, MapReduce, ML, alerts, support, reports (PDF + CSV), dashboard pages and filters, encryption at rest, encrypted backup/restore, health check, maintenance notices, help center, Tableau extract.

## Technology and deviations from the suggested stack

| Suggested | Used | Why |
|---|---|---|
| React + TypeScript + Tailwind | Django templates + hand-written CSS + vanilla JS | The project was already a Django app; server-rendered pages keep one codebase and one deploy. |
| Recharts | Chart.js 4 + Plotly (world maps) | Same interactivity (tooltips, legends, zoom on maps) without a React build step. |
| FastAPI | Django views + JSON endpoints | Django already provides auth, sessions, CSRF, admin and ORM. |
| MongoDB | **MongoDB 8 document store** (`earthscape` db: raw uploaded records, readings, alerts, jobs, model runs) + SQLite for users/app state | Django's auth/admin need a SQL database; climate data lives in MongoDB as documents (open it in Compass). |
| Hadoop / HDFS / MapReduce | **Hadoop 2.9.2 HDFS via WebHDFS + Hadoop Streaming (Python mapper/reducer)** + local MapReduce engine fallback | As required. |
| Pandas, NumPy, scikit-learn | Same | |
| Jupyter | `notebooks/ml_exploration.ipynb` | |

## Assumptions

- Windows machine with Python 3.12 and (optionally) Hadoop 2.9.2 at `C:\hadoop\hadoop-2.9.2` with JDK 8.
- Charts and maps load Chart.js/Plotly from the jsDelivr CDN, so the browser needs internet access for charts.
- `DEBUG=True` and the default `SECRET_KEY` are for local development only; see "Deployment" in the documentation.
