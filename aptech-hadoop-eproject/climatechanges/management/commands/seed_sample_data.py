"""Create clearly-labelled SAMPLE station readings (source="sample").

Real per-station rainfall/humidity history is not bundled with the project, so this
generates realistic, seasonal, deterministic data for 12 stations so that the
dashboards and the rainfall model have something to work with. Every row is
stored with source="sample" and every chart built from it says "sample data".
"""
import math
from datetime import datetime, timezone

import numpy as np
from django.core.management.base import BaseCommand

from climatechanges.live import STATIONS
from climatechanges.models import SensorReading

# typical climate per station: (mean temp, seasonal temp swing, yearly rain mm, wet-season month peak, base humidity)
CLIMATE = {
    "Lagos": (27.5, 1.8, 1700, 6, 82), "Abuja": (26.5, 3.0, 1400, 8, 60), "Nairobi": (19.0, 1.5, 900, 4, 65),
    "Cairo": (22.5, 7.0, 25, 1, 55), "London": (11.5, 6.5, 620, 11, 77), "Berlin": (10.0, 9.0, 590, 7, 74),
    "Delhi": (25.5, 8.0, 800, 8, 58), "Tokyo": (16.0, 9.0, 1530, 9, 66), "Jakarta": (27.8, 0.8, 1800, 1, 80),
    "New York": (13.0, 11.0, 1200, 7, 63), "São Paulo": (20.0, 3.5, 1450, 1, 74), "Sydney": (18.5, 4.5, 1200, 3, 68),
}


class Command(BaseCommand):
    help = "Generate labelled sample station readings (monthly, 2015-2025)."

    def add_arguments(self, parser):
        parser.add_argument("--replace", action="store_true", help="delete existing sample rows first")

    def handle(self, *args, **opts):
        if opts["replace"]:
            SensorReading.objects.filter(source="sample").delete()
        elif SensorReading.objects.filter(source="sample").exists():
            self.stdout.write("Sample data already present (use --replace to regenerate).")
            return
        rng = np.random.default_rng(2026)
        objs = []
        for name, country, region, lat, lon in STATIONS:
            t_mean, swing, rain_year, peak, hum = CLIMATE[name]
            south = lat < 0
            for year in range(2015, 2026):
                warming = (year - 2015) * 0.025
                for month in range(1, 13):
                    phase = math.cos(2 * math.pi * (month - (1 if south else 7)) / 12)
                    temp = t_mean + swing * phase + warming + rng.normal(0, 0.8)
                    wet = math.cos(2 * math.pi * (month - peak) / 12)
                    rain = max(0.0, rain_year / 12 * (1 + 0.9 * wet) * rng.lognormal(0, 0.35))
                    humid = min(100, max(10, hum + 8 * wet + rng.normal(0, 3)))
                    co2 = 400.0 + (year - 2015) * 2.4 + 3 * math.cos(2 * math.pi * (month - 5) / 12) + rng.normal(0, 0.3)
                    if rng.random() < 0.01:          # rare extreme events so anomaly detection has work to do
                        temp += rng.choice([-1, 1]) * 9
                        rain *= 3.5
                    objs.append(SensorReading(
                        station=name, country=country, region=region, latitude=lat, longitude=lon,
                        timestamp=datetime(year, month, 15, 12, tzinfo=timezone.utc),
                        temperature=round(temp, 1), rainfall=round(rain, 1), humidity=round(humid, 1),
                        co2=round(co2, 2), source="sample"))
        SensorReading.objects.bulk_create(objs, batch_size=200)
        self.stdout.write(self.style.SUCCESS(f"Created {len(objs)} SAMPLE readings for {len(STATIONS)} stations."))
