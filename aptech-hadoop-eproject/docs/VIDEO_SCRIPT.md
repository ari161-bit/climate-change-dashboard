# Demo video script (about 8 minutes)

The Aptech brief asks for a video showing the complete working application. Record your screen (Windows: **Win + Alt + R** with Xbox Game Bar, or OBS Studio) while following these steps.

**Before recording**: run `hadoop\start_hdfs.cmd`, make sure the MongoDB service is running, start the app with `python manage.py runserver`, and have one Administrator and one Climate Analyst account.

| # | Time | Show | Say |
|---|---|---|---|
| 1 | 0:00 | Public website home page | "EarthScape Climate Agency monitors and analyses climate change using Hadoop, MongoDB and machine learning." |
| 2 | 0:30 | Sign up a new user → log in | "Secure registration; passwords are hashed; new users get the Climate Analyst role." |
| 3 | 1:00 | Console **Overview**, change the filters | "Live KPIs: global temperature change from real FAO data, CO₂ from NOAA, station statistics. Badges show real vs sample data." |
| 4 | 1:45 | **Climate Analytics**: hover charts, zoom the anomaly map | "Interactive temperature, rainfall, humidity, CO₂ and regional charts, and a world anomaly map." |
| 5 | 2:30 | **Data Management**: upload `sample_data/station_readings_sample.csv` | "Validation finds 4 missing values and 2 duplicates; here's the preview." |
| 6 | 3:00 | Clean → Import → Store in HDFS | "Cleaning fixes them, readings are imported and an alert fires for 46.5 °C, and the file is stored in HDFS, partitioned by year and month." |
| 7 | 3:45 | http://localhost:50070 → Browse `/climate` | "The file is really in HDFS." |
| 8 | 4:00 | **Data Processing** → run *Climate disasters per year on Hadoop* | "A real Hadoop Streaming MapReduce job; output read back from HDFS." Show CPU/memory/disk and the MongoDB card. |
| 9 | 4:45 | MongoDB Compass → `earthscape` database | "Raw records, readings, alerts and model runs in MongoDB." |
| 10 | 5:15 | **Predictions** | "Three models tested on 10 held-out years; best by RMSE; forecast to 2035 with uncertainty. Rainfall model compared honestly with a baseline." |
| 11 | 6:00 | **Anomaly Detection** | "z-score anomalies by country, Isolation Forest on stations, temperature vs disasters correlation." |
| 12 | 6:30 | **Alerts**: bell, mark read; as admin add a rule | "Configurable thresholds, severity, read/unread." |
| 13 | 7:00 | **Reports**: download a PDF and the Tableau extract | "PDF and CSV reports; Tableau-ready extract." |
| 14 | 7:20 | **Support** as analyst → reply as admin | "Requests are tracked until resolved." |
| 15 | 7:40 | **Settings** (admin): users and roles, maintenance notice | "User management and advance maintenance notices." |
| 16 | 7:55 | **Help Center** | "User guide, tutorials, FAQs and data standards inside the app." |
