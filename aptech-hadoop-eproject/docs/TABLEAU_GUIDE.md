# Using EarthScape data in Tableau

1. In the console open **Reports → Tableau / BI extract → Download extract (.zip)** and unzip it.
2. Tableau Desktop → **Connect → To a File → Text file** → open `fact_temperature.csv`.
3. Drag `dim_country.csv` and `fact_disasters.csv` onto the canvas and create relationships on **iso3**.
   Add a second relationship field **year** between `fact_temperature` and `fact_disasters`.
4. Add `fact_readings.csv` separately (station data, related by `country` if needed).

## Suggested sheets

| Sheet | Build |
|---|---|
| Global warming line | Columns: `year` · Rows: AVG(`temp_change_degC`) · Filter `country` = World |
| Anomaly map | Double-click `iso3` (set Geographic Role → Country/Region, ISO 3166-1 alpha-3) · Color: AVG(`temp_change_degC`) · Filter `year` = 2023 · Filter `area_type` = country |
| Disasters by type | Columns: `year` · Rows: SUM(`disasters`) · Color: `disaster_type` (exclude TOTAL) |
| Temperature vs disasters | Columns: AVG(`temp_change_degC`) (World) · Rows: SUM(`disasters`) (TOTAL) · Detail: `year` · Analytics → Trend line |
| Station readings | Columns: MONTH(`timestamp`) · Rows: AVG(`rainfall_mm`) · Color: `station` · Filter: `source` |

Combine them in a dashboard and add the `source` filter so viewers can separate real observations from sample data.

## Units and standards
temperature °C, rainfall mm, humidity %, CO₂ ppm; timestamps ISO 8601 UTC; countries ISO 3166-1.
