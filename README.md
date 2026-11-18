<div align="center">

# EarthScape Climate Intelligence Platform

**Big-data climate monitoring with Hadoop, MapReduce, machine learning and a role-based dashboard.**
Aptech eProject · Django 6 · Python 3.12 · Hadoop HDFS + MapReduce · scikit-learn · Chart.js · Vercel

### [Live demo → climate-change-dashboard-eight.vercel.app](https://climate-change-dashboard-eight.vercel.app/climatechanges/)

[Project documentation (PDF)](docs/EarthScape_Project_Documentation.pdf) · [Architecture](docs/ARCHITECTURE.md) · [Install](docs/INSTALL.md) · [Testing](docs/TESTING.md)

</div>

---

## For reviewers: try it in 10 seconds

1. Open the [login page](https://climate-change-dashboard-eight.vercel.app/climatechanges/login/).
2. Click **Administrator** or **Climate Analyst** under *Try it instantly*. No typing needed.
3. You land on the console Overview. Every page is in the left sidebar.

| Role | Username | Password | Access |
|---|---|---|---|
| Administrator | `admin_demo` | `Climate#Admin2026` | Everything, including User Management |
| Climate Analyst | `analyst_demo` | `Climate#Analyst2026` | Analytics, predictions, anomalies, alerts, reports |

## What it does

The EarthScape Climate Agency collects climate data from satellites, weather stations and sensors. This platform ingests that data, stores it on HDFS, processes it with MapReduce, predicts trends and anomalies with machine learning, and shows the results on interactive dashboards with automatic alerts.

```
Data sources ─▶ Ingestion (Django) ─▶ Storage (HDFS + SQLite)
                                              │
Console dashboards ◀─ Machine learning ◀─ Processing (MapReduce)
```

## Requirements coverage

| Brief requirement | Implementation | Console page |
|---|---|---|
| Authentication and authorisation | Django auth, hashed passwords, Administrator / Climate Analyst roles, server-side checks | Login, User Management |
| Data ingestion | CSV / Excel upload, token-protected ingest API, sample station generator | Data Management |
| Data storage | HDFS, partitioned by source and date; metadata in SQLite | Data Management |
| Data processing | MapReduce jobs for aggregates, patterns, correlations; missing-value cleaning | Data Processing |
| Real-time processing | Live readings via the ingest API, merged with batch results | Overview, Analytics |
| Machine learning | Trend prediction and anomaly detection (scikit-learn, SciPy), retraining | Predictions, Anomaly Detection |
| Data visualisation | Interactive Chart.js dashboards with date / region / country / variable filters | Overview, Climate Analytics |
| Notifications and alerts | Threshold rules, unread badge in sidebar and bell menu | Alerts, Settings |
| Feedback and support | Support tickets with replies | Support |
| Performance, security | psutil monitoring, CSRF, HTTPS cookies, HSTS, CSP, encrypted data key, backup / restore commands | Settings |

## Run locally

```bash
cd aptech-hadoop-eproject
pip install -r requirements.txt
python manage.py migrate
python manage.py setup_earthscape   # roles, alert rules, sample data, models
python manage.py runserver
```

Open http://127.0.0.1:8000/climatechanges/. Start Hadoop (HDFS + YARN) on the same machine to store uploads on HDFS and run processing as MapReduce jobs.

## Deployment

Every push to `main` deploys to Vercel. `vercel_build.py` collects static files and pre-builds a seeded demo database during the build; `api/index.py` copies it on cold start and recreates the demo accounts, so a fresh instance is ready in seconds. Sessions use signed cookies so logins survive across serverless instances. Set `EARTHSCAPE_SECRET_KEY` in the Vercel project for production use.

Hadoop cannot run on Vercel, so the hosted demo uses the pre-built SQLite data; full HDFS / MapReduce runs locally or on a cluster.

## Tested

Every page and API route returns successfully for both roles; analysts are refused User Management (403); unauthenticated users are redirected to login. Details in the [project documentation](docs/EarthScape_Project_Documentation.pdf).
