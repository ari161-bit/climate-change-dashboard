# Architecture and design specification

This document covers the problem definition, design, data flows and workflows of the EarthScape Climate Agency portal. Diagrams are Mermaid and render directly on GitHub.

## 1. Problem definition

The EarthScape Climate Agency collects climate data from satellites, weather stations and sensors and needs a platform to **store it, process it, find patterns and anomalies, predict trends, alert stakeholders and let analysts explore it**, with access limited by role. The original brief assumes a Hadoop/HDFS/Impala/Tableau stack; this implementation keeps the same *architecture and programming model* at a scale and cost that suits the data (a few hundred kilobytes), so it runs on a laptop and on serverless hosting.

## 2. Component overview

```mermaid
flowchart TB
    subgraph Sources["External sources"]
        S1[NASA GISTEMP<br/>temperature]
        S2[NOAA Mauna Loa<br/>CO2]
        S3[Global Carbon Project<br/>EM-DAT · FAO · sea level]
        S4[NASA POWER<br/>city temperatures]
        S5[Open-Meteo<br/>live weather and air quality]
        S6[NASA GIBS<br/>satellite tiles]
        S7[Admin uploads<br/>CSV / JSON / XLS]
    end
    subgraph Ingest["Ingestion layer"]
        I1[ingest_climate_data<br/>download · clean · partition]
        I2[live.py<br/>cached stream client]
        I3[Upload parser]
    end
    subgraph Store["Storage layer"]
        L[(Data lake<br/>decade partitions + manifest)]
        D[(SQLite / Postgres<br/>users · thresholds · feedback<br/>model runs · audit · uploads)]
    end
    subgraph Process["Processing layer"]
        P1[pipeline.py<br/>MapReduce-style jobs]
        P2[analytics.py<br/>aggregation · regional · emissions · impacts]
        P3[ml.py<br/>trend · anomaly · regimes · correlation]
    end
    subgraph App["Application layer (Django)"]
        A1[Auth + roles + audit]
        A2[JSON APIs]
        A3[Pages + templates]
        A4[Monitor middleware]
    end
    S1 & S2 & S3 & S4 --> I1 --> L
    S5 --> I2
    S7 --> I3 --> D
    L --> P1 --> P2
    L --> P3
    P2 & P3 --> A2
    I2 --> A2
    D <--> A1
    D --> A2
    A2 --> A3
    A4 -. timings .-> A3
    S6 -. tiles loaded by the browser .-> A3
    U((Analyst / Administrator)) --> A1
```

| Layer | Brief's technology | This implementation | Why |
|---|---|---|---|
| Distributed storage | HDFS | Partitioned file lake (`climate/data/lake/<dataset>/decade=<n>/part-0000.csv`) + `manifest.json` | Same layout idea (blocks, partition pruning, metadata); no cluster needed for ~300 KB |
| Batch processing | Hadoop MapReduce | `pipeline.run_job`: per-partition `mapper` in a thread pool, shuffle by key, `reducer` | Same programming model |
| Query engine | Impala | pandas on pruned partitions | Same role: fast ad-hoc reads |
| Real-time | Streaming | `live.py`: batched Open-Meteo calls, 5-minute cache, threshold alerts, merged with batch statistics | |
| ML | R / Python | NumPy/pandas models in `ml.py` | Runs on serverless, no heavy dependencies |
| Visualisation | Tableau | Highcharts dashboards in the browser, Leaflet + NASA GIBS | Embedded, interactive, role-aware |
| Metadata store | MongoDB | Django ORM (SQLite locally; any Django database in production) | |

## 3. Data flow diagrams

### Level 0: context

```mermaid
flowchart LR
    SRC[Climate data providers] -->|datasets| SYS((EarthScape<br/>portal))
    LIVE[Live weather API] -->|current conditions| SYS
    SAT[NASA GIBS] -->|image tiles| SYS
    ADM[Administrator] -->|uploads · thresholds · retrain · replies| SYS
    ANA[Analyst] -->|filters · questions| SYS
    SYS -->|dashboards · alerts · models| ANA
    SYS -->|monitor · audit · backups| ADM
```

### Level 1: processes and stores

```mermaid
flowchart TB
    P1([1 Ingest and clean]) --> D1[(D1 Data lake)]
    P1 --> D3[(D3 Manifest)]
    D1 --> P2([2 Process<br/>MapReduce + aggregation])
    D1 --> P3([3 Train and select models])
    P3 --> D4[(D4 Model runs)]
    P2 --> P4([4 Evaluate alerts])
    D2[(D2 Thresholds)] --> P4
    LIVE[Live API] --> P5([5 Live feed])
    D2 --> P5
    P2 & P3 & P4 & P5 --> P6([6 Serve dashboards])
    P6 --> USER((Users))
    USER --> P7([7 Authenticate and authorise])
    P7 --> D5[(D5 Users and groups)]
    P7 --> D6[(D6 Audit log)]
    USER --> P8([8 Feedback and support]) --> D7[(D7 Encrypted feedback)]
```

## 4. Workflows

### 4.1 Data ingestion

```mermaid
flowchart TD
    A[Run ingest_climate_data] --> B{For each source}
    B --> C[Download]
    C -->|network error| X[Log, skip source,<br/>keep previous lake copy]
    C --> D[Coerce numeric types<br/>drop duplicates]
    D --> E[Interpolate gaps of 2 periods or fewer<br/>record what stays missing]
    E --> F[Split by decade]
    F --> G[Write partitions]
    G --> H[Update manifest:<br/>rows · years · SHA-256 · quality]
    H --> B
    B -->|done| I[Report]
```

NOAA's own server is occasionally unreachable, so CO2 falls back to a public mirror of the same series. One failing source never aborts the others.

### 4.2 Dashboard request

```mermaid
sequenceDiagram
    participant B as Browser
    participant D as Django
    participant L as Lake
    participant M as ML
    B->>D: GET / (page shell)
    D-->>B: HTML (login required)
    B->>D: GET /data/?start=1980&end=2020
    D->>D: check session + role
    D->>L: read only overlapping partitions
    D->>D: MapReduce decade statistics
    D->>M: trend model, anomalies, correlation
    D->>D: evaluate alerts vs stored thresholds
    D-->>B: one JSON document
    B->>B: render charts (theme-aware)
```

### 4.3 Alerting

```mermaid
flowchart LR
    V[Latest value] --> C{value > threshold?}
    T[(Threshold,<br/>editable by admins)] --> C
    C -->|no| OK[Normal]
    C -->|yes| R{value >= 1.5 x threshold?}
    R -->|no| W[Warning]
    R -->|yes| K[Critical]
```

Climate alerts are recalculated on each dashboard load; live alerts on each live refresh (heat uses 1.15x and PM2.5 2x as the critical multiples).

### 4.4 Model retraining

```mermaid
flowchart TD
    N[New data ingested] --> R[Admin presses Retrain]
    R --> T1[Trend: backtest linear, quadratic, recent-30]
    R --> T2[Anomaly: z-scores vs 1951-1980]
    R --> T3[Regimes: k-means]
    R --> T4[Correlation matrix]
    T1 --> S[Select lowest RMSE]
    S & T2 & T3 & T4 --> H[(ModelRun history:<br/>params · metrics · time · who)]
    H --> U[Dashboard uses the new selection]
```

## 5. Data model

```mermaid
erDiagram
    USER ||--o{ FEEDBACK : writes
    USER }o--o{ GROUP : "is in"
    ALERTTHRESHOLD { string key PK
        float value
        string unit }
    FEEDBACK { int id PK
        string subject
        text message_enc "encrypted"
        text response_enc "encrypted"
        string status }
    MODELRUN { int id PK
        string name
        string data_through
        json metrics
        float duration_ms }
    AUDITLOG { int id PK
        string user
        string action
        string ip }
    CUSTOMDATASET { int id PK
        string slug
        string visibility
        json points }
```

## 6. Security design

| Control | Implementation |
|---|---|
| Authentication | Django auth, password hashing (PBKDF2), password validators on sign-up |
| Authorisation | Two roles (Administrators, Analysts) via groups; every admin view uses `admin_required`; checked server-side |
| Data-level access | Raw CSV export and "administrators only" uploaded datasets are hidden from analysts |
| Encryption in transit | HTTPS on Vercel; secure cookies, HSTS and a proxy-aware scheme check when `DEBUG` is off |
| Encryption at rest | Feedback messages and replies encrypted with Fernet (AES-128-CBC + HMAC) using a key derived from `SECRET_KEY` |
| Sessions | Signed, HTTP-only, SameSite=Lax cookies; 8-hour lifetime; stateless across server instances |
| CSRF | Django middleware on every POST; a failure returns the user to sign-in with an explanation |
| Content-Security-Policy | Restricts scripts, styles, images and connections to the app, Google Fonts and NASA GIBS |
| Input handling | Length and type validation; uploads limited to 2 MB and to CSV/JSON/XLS; open-redirect protection on `next` |
| Audit | Sign-in, failed sign-in, sign-up, uploads, downloads, retraining, threshold changes, backups |

## 7. Performance and scalability

- **Partition pruning:** a request for 1990-1999 opens one partition file, not all fifteen.
- **Caching:** datasets are cached in memory after first read; the live feed is cached for 5 minutes.
- **Monitoring:** `MonitorMiddleware` and `monitor.stage()` record latency, error rate and stage timings (Admin → Performance monitor).
- **Horizontal scaling:** the app is stateless (signed-cookie sessions, read-only lake), so more instances can be added behind a load balancer. The remaining shared state is the Django database; use Postgres in production.
- **Reliability:** per-source ingestion isolation, a mirror fallback for CO2, cached live data when the upstream API is down, and downloadable or scheduled backups (`backup_data`).
