# Test plan and test data

## Automated tests

```bash
python manage.py test climate --settings=mysite.test_settings
```

`mysite.test_settings` builds the legacy `myshop` tables directly from its models, because that old app ships conflicting migrations. The climate app is migrated normally.

**37 tests**, all passing:

| Suite | What it proves |
|---|---|
| `LakeTests` | Manifest and checksums exist; partition pruning returns only the requested years; gap filling fills short gaps and leaves long ones blank |
| `AnalyticsTests` | The dashboard payload has every section; reversed or out-of-range year filters are clamped; the MapReduce decade means equal a direct pandas calculation; alert severity levels |
| `ModelTests` | The trend model picks the lowest backtest error; recent years are flagged as anomalies; clusters are ordered cool to hot; the correlation matrix is symmetric with a unit diagonal; retraining writes run records |
| `TrendAnalyzerTests` | The analyzer reproduces a known regional series (recent 10-year average 57,863.19 for Advanced Economies carbon stocks, R² above 0.98); outliers exceed two sigma; forced model and horizon are honoured; country groups are separated from countries (including Namibia's ISO code "NA"); too little data returns a clean 422 |
| `CryptoTests` | Encrypt/decrypt round-trip, idempotence, and that feedback text never appears in the database in clear |
| `AccessTests` | Anonymous users are redirected from every page; analysts can read but not administer, retrain, download raw data or reach monitoring; admins can; sign-in and failures are audited; open redirects refused; logout is POST-only; sign-up gives the Analyst role and rejects weak or mismatched passwords; CSRF failures redirect to sign-in |
| `AdminToolsTests` | Threshold validation; CSV upload and admin-only visibility; bad uploads rejected; unknown dataset returns 404; feedback round-trip |
| `LiveAndMonitorTests` | Live alert rules and severities; the monitor records requests and stage timings |

## Test data

| Data | Purpose |
|---|---|
| `climate/data/lake/*` (11 datasets, all reproduced by `ingest_climate_data`; the two IMF files are read from `climate/data/source/`) | Real public data used by every test and by the application |
| Demo accounts `admin_demo`, `analyst_demo` (see README) | Manual role testing |
| CSV in `AdminToolsTests` (`year,value` rows 2000-2003) | Upload parsing |
| `[1, NaN, 3, NaN, NaN, NaN, 7]` series in `LakeTests` | Missing-data handling |

## Manual test checklist (user acceptance)

| # | Steps | Expected |
|---|---|---|
| 1 | Open `/` signed out | Redirected to the sign-in page |
| 2 | Sign in as `analyst_demo` | Dashboard loads; header shows *Analyst*; no *Admin* menu |
| 3 | Visit `/manage/` and `/monitor/` | Redirected to the dashboard with an explanatory message |
| 4 | Press **Since 1980** | All charts and cards update; the preset button highlights |
| 5 | Toggle the theme | Page and all charts switch palette; preference survives reload |
| 5b | Trends page: *Carbon stocks in forests*, *Advanced Economies*, project to 2035 | R² about 0.99, RMSE about 166, dashed projection with band, outliers marked |
| 6 | Data explorer, choose *CO2 emissions by country*, pick *China* | Line chart of China's emissions; no download button for analysts |
| 7 | Live page | 12 city cards with temperature, PM2.5, CO2; alerts for readings above thresholds |
| 8 | Satellite page, change layer and date | Imagery changes; city markers stay |
| 9 | Models page as analyst | Retrain button absent |
| 10 | Support, send a message | Appears under *Your messages* as Open |
| 11 | Sign out, sign in as `admin_demo` | *Admin* menu appears |
| 12 | Admin panel, lower *Annual temperature anomaly* to 0.5 | Dashboard alert changes to critical |
| 13 | Upload a CSV with admin-only visibility | Visible to admin in the explorer, not to the analyst |
| 14 | Reply to the message and mark it resolved | Analyst sees the reply and *Resolved* |
| 15 | Models, **Retrain all models now** | New rows in *Training history* |
| 16 | Admin, **Download backup** | Zip with `database.sqlite3` and `lake/` |
| 17 | Admin, **Performance monitor** | Latency chart and stage timings populated |
| 18 | Open the sign-in form in two tabs, sign in on one, submit the other | Redirected to sign-in with a "form expired" message, not a bare 403 |
