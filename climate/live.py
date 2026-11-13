"""Real-time feed: current weather and air quality for the monitored cities (Open-Meteo, no API key).

Responses are cached for a few minutes so many dashboard viewers cost one upstream call. The batch layer
(the data lake) supplies each city's long-term mean for context, so streaming and batch results sit side by side.
"""
import threading
import time

import requests

from . import lake, monitor
from .management.commands.ingest_climate_data import CITIES

WEATHER_URL = 'https://api.open-meteo.com/v1/forecast'
AIR_URL = 'https://air-quality-api.open-meteo.com/v1/air-quality'
TTL_SECONDS = 300

_lock = threading.Lock()
_cache = {'at': 0.0, 'data': None}


def _batched(url, current):
    names = list(CITIES)
    params = {'latitude': ','.join(str(CITIES[n][0]) for n in names), 'longitude': ','.join(str(CITIES[n][1]) for n in names),
              'current': current, 'timezone': 'UTC'}
    resp = requests.get(url, params=params, timeout=12)
    resp.raise_for_status()
    payload = resp.json()
    return payload if isinstance(payload, list) else [payload]


def _long_term_means():
    try:
        data = lake.read_dataset('city_climate_annual')
    except FileNotFoundError:
        return {}
    recent = data[data['year'] >= data['year'].max() - 9]
    return recent.groupby('city')['temp_mean'].mean().round(1).to_dict()


def fetch_live(thresholds):
    with _lock:
        fresh = _cache['data'] is not None and time.time() - _cache['at'] < TTL_SECONDS
        if fresh:
            snapshot = _cache['data']
        else:
            snapshot = None
    if snapshot is None:
        with monitor.stage('live:fetch'):
            try:
                weather = _batched(WEATHER_URL, 'temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,precipitation')
                air = _batched(AIR_URL, 'pm2_5,pm10,ozone,carbon_dioxide,us_aqi')
            except requests.RequestException as exc:
                with _lock:
                    if _cache['data'] is not None:
                        return {**_cache['data'], 'stale': True, 'error': str(exc)}
                return {'cities': [], 'error': f'Live feed unavailable: {exc}', 'stale': True}
        means = _long_term_means()
        rows = []
        for name, w, a in zip(CITIES, weather, air):
            cw, ca = w.get('current', {}), a.get('current', {})
            rows.append({'city': name, 'lat': CITIES[name][0], 'lon': CITIES[name][1], 'time': cw.get('time'),
                         'temp': cw.get('temperature_2m'), 'feels': cw.get('apparent_temperature'),
                         'humidity': cw.get('relative_humidity_2m'), 'wind': cw.get('wind_speed_10m'),
                         'rain': cw.get('precipitation'), 'pm25': ca.get('pm2_5'), 'pm10': ca.get('pm10'),
                         'ozone': ca.get('ozone'), 'co2': ca.get('carbon_dioxide'), 'aqi': ca.get('us_aqi'),
                         'long_term_mean': means.get(name)})
        snapshot = {'cities': rows, 'fetched_at': time.strftime('%H:%M:%S UTC', time.gmtime()), 'stale': False}
        with _lock:
            _cache.update(at=time.time(), data=snapshot)
    return {**snapshot, 'alerts': live_alerts(snapshot['cities'], thresholds), 'ttl': TTL_SECONDS}


def live_alerts(rows, thresholds):
    heat, pm = thresholds.get('live_heat', 35.0), thresholds.get('live_pm25', 35.0)
    alerts = []
    for row in rows:
        if row['temp'] is not None and row['temp'] > heat:
            alerts.append({'city': row['city'], 'kind': 'Heat', 'value': row['temp'], 'unit': '°C', 'threshold': heat,
                           'severity': 'critical' if row['temp'] > heat * 1.15 else 'warning'})
        if row['pm25'] is not None and row['pm25'] > pm:
            alerts.append({'city': row['city'], 'kind': 'Air quality (PM2.5)', 'value': row['pm25'], 'unit': 'µg/m³', 'threshold': pm,
                           'severity': 'critical' if row['pm25'] > pm * 2 else 'warning'})
    return alerts
