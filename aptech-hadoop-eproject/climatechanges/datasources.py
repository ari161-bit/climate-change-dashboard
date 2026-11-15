"""Loads the climate datasets used across the platform.

Real observations
  * data/Temperature.csv  FAO temperature change vs 1951-1980, per country + regions, 1961-2023
  * data/Disaster.csv     EM-DAT climate-related disasters per country, 1980-2024
  * data/Carbon.csv       FAO forest carbon stocks, 1992-2023
  * SensorReading rows with source="live"/"api"/"upload"

Sample data (clearly labelled source="sample")
  * synthetic station readings created by `python manage.py seed_sample_data`
"""
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
from django.conf import settings

REGIONS = ["Africa", "Americas", "Asia", "Europe", "Oceania"]
TEMP_SOURCE = "FAO FAOSTAT Climate Change: Temperature change (CC BY-NC-SA 3.0 IGO)"
DISASTER_SOURCE = "EM-DAT, CRED / UCLouvain via IMF Climate Change Dashboard"


def _path(name):
    return Path(settings.DATA_DIR) / name


def _mtime(name):
    p = _path(name)
    return p.stat().st_mtime if p.exists() else 0


@lru_cache(maxsize=4)
def _temperature(mtime):
    df = pd.read_csv(_path("Temperature.csv"), encoding="utf-8-sig", keep_default_na=False, na_values=[""])
    years = [c for c in df.columns if str(c).isdigit()]
    long = df.melt(id_vars=["Country", "ISO2", "ISO3"], value_vars=years, var_name="year", value_name="anomaly")
    long["year"] = long["year"].astype(int)
    long["anomaly"] = pd.to_numeric(long["anomaly"], errors="coerce")
    long["is_region"] = long["Country"].isin(REGIONS + ["World"])
    return long


def temperature():
    """Long table: Country, ISO2, ISO3, year, anomaly (°C vs 1951-1980), is_region."""
    return _temperature(_mtime("Temperature.csv")).copy()


@lru_cache(maxsize=4)
def _disasters(mtime):
    df = pd.read_csv(_path("Disaster.csv"), encoding="utf-8-sig", keep_default_na=False, na_values=[""])
    years = [c for c in df.columns if str(c).isdigit()]
    df = df[df["Indicator"].str.contains("Number of Disasters")]
    df = df.assign(kind=df["Indicator"].str.split(": ").str[-1])
    long = df.melt(id_vars=["Country", "ISO2", "ISO3", "kind"], value_vars=years, var_name="year", value_name="count")
    long["year"] = long["year"].astype(int)
    long["count"] = pd.to_numeric(long["count"], errors="coerce").fillna(0)
    return long[long["ISO2"].astype(str).str.len() > 0]


def disasters():
    """Long table: Country, ISO2, ISO3, kind (TOTAL/Flood/...), year, count."""
    return _disasters(_mtime("Disaster.csv")).copy()


def world_temperature_series(country="World"):
    t = temperature()
    s = t[t["Country"] == country].dropna(subset=["anomaly"]).sort_values("year")
    return s[["year", "anomaly"]].reset_index(drop=True)


def countries():
    t = temperature()
    c = t[~t["is_region"]][["Country", "ISO3"]].drop_duplicates().sort_values("Country")
    return list(c.itertuples(index=False, name=None))


def latest_country_anomalies(year=None):
    """Per-country anomaly for one year + its z-score against the country's own history."""
    t = temperature()
    t = t[~t["is_region"]].dropna(subset=["anomaly"])
    year = year or int(t["year"].max())
    stats = t.groupby("Country")["anomaly"].agg(["mean", "std"])
    cur = t[t["year"] == year].set_index("Country")
    cur = cur.join(stats)
    cur["z"] = (cur["anomaly"] - cur["mean"]) / cur["std"].replace(0, np.nan)
    return year, cur.reset_index()[["Country", "ISO3", "anomaly", "z"]]


# ---------------------------------------------------------------------------
# Station / sensor readings (database)
# ---------------------------------------------------------------------------
def readings_frame(qs=None):
    from .models import SensorReading
    qs = qs if qs is not None else SensorReading.objects.all()
    rows = list(qs.values("station", "country", "region", "latitude", "longitude", "timestamp",
                          "temperature", "rainfall", "humidity", "co2", "source"))
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=["station", "country", "region", "latitude", "longitude", "timestamp",
                                     "temperature", "rainfall", "humidity", "co2", "source"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df


def filtered_readings(params):
    """Apply dashboard filters (date range, country, region) to SensorReading."""
    from .models import SensorReading
    qs = SensorReading.objects.all()
    if params.get("start"):
        qs = qs.filter(timestamp__date__gte=params["start"])
    if params.get("end"):
        qs = qs.filter(timestamp__date__lte=params["end"])
    if params.get("country"):
        qs = qs.filter(country=params["country"])
    if params.get("region"):
        qs = qs.filter(region=params["region"])
    return qs


def data_badge(sources):
    """Human label telling users whether numbers are real or sample."""
    sources = set(s for s in sources if s)
    if not sources:
        return "no data"
    if sources == {"sample"}:
        return "sample data"
    if "sample" in sources:
        return "mixed: real + sample"
    return "real observations"
