"""Real-time data: pulls live observations from public APIs into SensorReading.

  * Open-Meteo current weather (temperature, rain, humidity) for monitored stations
  * NOAA Mauna Loa CO2 via global-warming.org (cached to data/co2_cache.json)

Every failure is reported back; nothing is invented when the network is down.
"""
import json
import logging
import urllib.request
from datetime import datetime, timezone as dt_tz
from pathlib import Path

from django.conf import settings

log = logging.getLogger("earthscape")

STATIONS = [
    # name, country, region, lat, lon
    ("Lagos", "Nigeria", "Africa", 6.45, 3.39),
    ("Abuja", "Nigeria", "Africa", 9.06, 7.50),
    ("Nairobi", "Kenya", "Africa", -1.29, 36.82),
    ("Cairo", "Egypt", "Africa", 30.04, 31.24),
    ("London", "United Kingdom", "Europe", 51.51, -0.13),
    ("Berlin", "Germany", "Europe", 52.52, 13.40),
    ("Delhi", "India", "Asia", 28.61, 77.21),
    ("Tokyo", "Japan", "Asia", 35.68, 139.69),
    ("Jakarta", "Indonesia", "Asia", -6.21, 106.85),
    ("New York", "United States", "Americas", 40.71, -74.01),
    ("São Paulo", "Brazil", "Americas", -23.55, -46.63),
    ("Sydney", "Australia", "Oceania", -33.87, 151.21),
]


def _get_json(url, timeout=6):
    req = urllib.request.Request(url, headers={"User-Agent": "EarthScape/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def pull_weather():
    """Fetch current conditions for every station. Returns (created, errors)."""
    from . import alerts
    from .models import SensorReading
    lats = ",".join(str(s[3]) for s in STATIONS)
    lons = ",".join(str(s[4]) for s in STATIONS)
    url = (f"https://api.open-meteo.com/v1/forecast?latitude={lats}&longitude={lons}"
           f"&current=temperature_2m,relative_humidity_2m,precipitation&timezone=UTC")
    try:
        data = _get_json(url)
    except Exception as e:
        log.warning("Open-Meteo pull failed: %s", e)
        return 0, [f"Open-Meteo unreachable: {e.__class__.__name__}"]
    data = data if isinstance(data, list) else [data]
    created = 0
    for (name, country, region, lat, lon), d in zip(STATIONS, data):
        cur = d.get("current", {})
        ts = datetime.fromisoformat(cur["time"]).replace(tzinfo=dt_tz.utc)
        r, new = SensorReading.objects.get_or_create(
            station=name, timestamp=ts, source="live",
            defaults=dict(country=country, region=region, latitude=lat, longitude=lon,
                          temperature=cur.get("temperature_2m"), rainfall=cur.get("precipitation"),
                          humidity=cur.get("relative_humidity_2m")))
        if new:
            created += 1
            alerts.check_reading(r)
    from . import mongo
    mongo.upsert_readings(SensorReading.objects.filter(source="live").order_by("-id")[:len(STATIONS)])
    log.info("Pulled %d live readings from Open-Meteo", created)
    return created, []


def co2_series(refresh=False):
    """Monthly CO2 (ppm). Returns dict(source, label, months, values, latest) or None.

    Pages call this without refresh: they only read the saved copy and never wait on
    the network. The network is used only when refresh=True ("Pull live data").
    """
    cache = Path(settings.DATA_DIR) / "co2_cache.json"
    if not refresh:
        return json.loads(cache.read_text(encoding="utf-8")) if cache.exists() else None
    try:
        data = _get_json("https://global-warming.org/api/co2-api", timeout=8)
        rows = data.get("co2", [])
        monthly = {}
        for r in rows:
            key = f"{r['year']}-{int(r['month']):02d}"
            monthly.setdefault(key, []).append(float(r["trend"]))
        months = sorted(monthly)
        values = [round(sum(monthly[m]) / len(monthly[m]), 2) for m in months]
        out = {"source": "NOAA Mauna Loa via global-warming.org", "label": "real observations",
               "months": months, "values": values, "latest": values[-1] if values else None,
               "fetched": datetime.now(dt_tz.utc).isoformat(timespec="seconds")}
        cache.write_text(json.dumps(out), encoding="utf-8")
        return out
    except Exception as e:
        log.warning("CO2 fetch failed: %s", e)
        return json.loads(cache.read_text(encoding="utf-8")) if cache.exists() else None
