import io
import os

import pandas as pd
import requests
from django.conf import settings
from django.core.management.base import BaseCommand

NASA = 'https://data.giss.nasa.gov/gistemp/tabledata_v4/{}.Ts+dSST.csv'
NOAA_CO2 = 'https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_mm_mlo.csv'
# Mirror of the same NOAA Mauna Loa monthly series, used if gml.noaa.gov is unreachable.
CO2_MIRROR = 'https://raw.githubusercontent.com/datasets/co2-ppm/main/data/co2-mm-mlo.csv'
MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']


def fetch(url):
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    return resp.text


def co2_series():
    """Mauna Loa monthly mean CO2 (ppm), interpolated where the monthly average is missing."""
    try:
        co2 = pd.read_csv(io.StringIO(fetch(NOAA_CO2)), comment='#')
        co2 = co2[['year', 'month', 'average']].rename(columns={'average': 'co2_ppm'})
    except requests.RequestException:
        rows = []
        for line in fetch(CO2_MIRROR).splitlines()[1:]:
            parts = line.split(',')
            if len(parts) < 4:
                continue
            year, month = parts[0].split('-')
            average, interpolated = float(parts[2]), float(parts[3])
            rows.append((int(year), int(month), average if average > 0 else interpolated))
        co2 = pd.DataFrame(rows, columns=['year', 'month', 'co2_ppm'])
    return co2[co2['co2_ppm'] > 0]


def temperature_series(code):
    """NASA GISTEMP v4 monthly anomalies (deg C vs 1951-1980) for GLB / NH / SH."""
    text = fetch(NASA.format(code))
    wide = pd.read_csv(io.StringIO(text), skiprows=1, na_values=['***'])
    wide = wide[['Year'] + MONTHS]
    long = wide.melt(id_vars='Year', var_name='mon', value_name=code.lower())
    long['month'] = long['mon'].map({m: i + 1 for i, m in enumerate(MONTHS)})
    return long.drop(columns='mon').rename(columns={'Year': 'year'}).set_index(['year', 'month'])


class Command(BaseCommand):
    help = 'Download NASA GISTEMP temperature anomalies and NOAA Mauna Loa CO2 into climate/data/*.csv'

    def handle(self, *args, **options):
        out_dir = os.path.join(settings.BASE_DIR, 'climate', 'data')
        os.makedirs(out_dir, exist_ok=True)

        temp = pd.concat([temperature_series(c) for c in ('GLB', 'NH', 'SH')], axis=1)
        temp = temp.dropna(how='all').reset_index().sort_values(['year', 'month'])
        temp.columns = ['year', 'month', 'global_anomaly', 'nh_anomaly', 'sh_anomaly']
        temp.to_csv(os.path.join(out_dir, 'temperature_monthly.csv'), index=False)

        co2 = co2_series()
        co2.to_csv(os.path.join(out_dir, 'co2_monthly.csv'), index=False)

        self.stdout.write(self.style.SUCCESS(
            f'temperature rows: {len(temp)} ({int(temp.year.min())}-{int(temp.year.max())}); '
            f'co2 rows: {len(co2)} ({int(co2.year.min())}-{int(co2.year.max())})'))
