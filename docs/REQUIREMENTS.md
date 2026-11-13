# Requirements traceability

Every requirement in the eProject brief, how it is met, where to find it and how it is verified. **Adapted** marks a place where the literal technology in the brief was replaced by an equivalent suited to the data size; the reason is given.

## Functional requirements

| # | Requirement | Status | Implementation | Verified by |
|---|---|---|---|---|
| F1 | Secure authentication with roles (administrators, analysts) | Met | `views.login_view`, `signup_view`, groups in `roles.py`; sign-up creates Analysts | `AccessTests` |
| F1b | Access controls restrict data by role | Met | `admin_required`; raw CSV download and admin-only uploaded datasets restricted | `AccessTests`, `AdminToolsTests` |
| F2 | Ingest diverse datasets: satellite, weather station, sensor | Met | 9 lake datasets (NASA GISTEMP, NOAA, GCP, EM-DAT, FAO, NASA POWER), live Open-Meteo sensor feed, NASA GIBS satellite imagery, admin uploads | `LakeTests`, manual |
| F2b | Historical and real-time sources | Met | Batch: `ingest_climate_data`. Real-time: `live.py` + `/live/` | `LiveAndMonitorTests` |
| F2c | Common formats | Met | CSV, JSON, XLS upload parsing; CSV/JSON source ingestion | `AdminToolsTests` |
| F3 | HDFS storage, partitioning for fast retrieval | **Adapted** | Partitioned lake with manifest and partition pruning (see ARCHITECTURE s2). HDFS needs a cluster; the data is ~300 KB | `LakeTests.test_partition_pruning...` |
| F4 | MapReduce jobs for parallel processing | **Adapted** | `pipeline.run_job` (map per partition in parallel, shuffle, reduce) computing decade statistics | `AnalyticsTests.test_mapreduce_decades_match_pandas` |
| F4b | Identify patterns, anomalies, correlations | Met | k-means regimes, z-score anomalies, correlation matrix | `ModelTests` |
| F4c | Handle missing or incomplete data gracefully | Met | `lake.clean` fills gaps of 2 periods or fewer, leaves longer gaps blank, records missing % per dataset | `LakeTests.test_clean_fills_short_gaps_only` |
| F5 | Real-time processing integrated with batch | Met | Live cards beside each city's batch 10-year mean | manual |
| F6 | ML for trend prediction, anomaly detection, correlation | Met | `ml.py` | `ModelTests` |
| F6b | Regularly update and refine models | Met | Backtest-based model selection; **Retrain** records a `ModelRun` each time | `ModelTests.test_train_all_records_runs` |
| F7 | Interactive dashboards, customisable and user-friendly | Met | Year filters, presets, zoom, legend toggles, exports, dark/light theme, dataset explorer with column/group pickers | manual |
| F7b | Visual representations of patterns, anomalies, predictions | Met | Stripes, anomaly markers, 2050 projection with band, regime scatter, heat-map matrix | manual |
| F8 | Automated alerts on predefined thresholds; configurable; real-time | Met | 5 climate + 2 live thresholds editable by administrators, live alerts on each refresh | `AnalyticsTests.test_alert_levels`, `LiveAndMonitorTests` |
| F8b | Notify users | Met (in-app) | Alerts appear on the dashboard and live page. Email/SMS delivery is not implemented | n/a |
| F9 | Support system: contact, report issues, feedback | Met | `/feedback/` with categories, status and administrator replies | `AdminToolsTests.test_feedback_round_trip` |

## Non-functional requirements

| # | Requirement | Status | Implementation |
|---|---|---|---|
| N1 | Performance monitoring tools | Met | `/monitor/`: latency (avg/p50/p95), error rate, stage timings, memory/CPU, slowest routes |
| N1b | Optimisation strategies | Met | Partition pruning, in-memory caching, live-feed cache, compact JSON, WhiteNoise static compression |
| N2 | Encryption of sensitive data at rest and in transit | Met | Fernet-encrypted feedback; HTTPS, secure cookies and HSTS in production (`CryptoTests`) |
| N2b | Data-protection compliance | Partly | Minimal personal data (username, optional email), audit log, no tracking cookies. Formal certification is out of scope |
| N3 | 99% uptime, scheduled maintenance notice | Design | Stateless app on a managed platform; no scheduled-maintenance notification feature |
| N3b | Regular automated backups | Met | `manage.py backup_data` (rotating zips, for cron) and an admin download |
| N4 | Horizontal scaling, load balancing | Design | Stateless app (signed sessions, read-only lake); Vercel provides load balancing. Use Postgres for shared writes |
| N5 | Environmental data standards and big-data best practice | Met | Provenance, units, SHA-256 and quality in the manifest; anomalies reported against the standard 1951-1980 baseline as published by NASA |
| N6 | User documentation (guides, FAQ, tutorials) | Met | In-app **Help** page; README |
| N6b | Developer documentation (architecture, workflows, ML) | Met | `docs/ARCHITECTURE.md`, this file, `docs/TESTING.md` |
| N6c | Video of the complete working application | Pending | Script in `docs/VIDEO_SCRIPT.md`; to be recorded by the submitting student |

## Deliverables checklist

| Deliverable | Where |
|---|---|
| Problem definition | `docs/ARCHITECTURE.md` s1 |
| Design specifications | `docs/ARCHITECTURE.md` |
| Flowcharts and data-flow diagrams | `docs/ARCHITECTURE.md` s3 and s4 |
| Source code | repository |
| Test data | `climate/data/lake/` and `docs/TESTING.md` |
| Installation instructions | `docs/INSTALL.md` |
| ReadMe with assumptions | `README.md` |
| Live URL (optional) | in `README.md` |
