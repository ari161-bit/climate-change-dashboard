import io
import time

import pandas as pd
import requests
from django.core.management.base import BaseCommand

from climate import lake

NASA = 'https://data.giss.nasa.gov/gistemp/tabledata_v4/{}.Ts+dSST.csv'
NASA_ZONAL = 'https://data.giss.nasa.gov/gistemp/tabledata_v4/ZonAnn.Ts+dSST.csv'
NOAA_CO2 = 'https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_mm_mlo.csv'
# Mirror of the same NOAA Mauna Loa monthly series, used if gml.noaa.gov is unreachable.
CO2_MIRROR = 'https://raw.githubusercontent.com/datasets/co2-ppm/main/data/co2-mm-mlo.csv'
OWID_CO2 = 'https://raw.githubusercontent.com/owid/co2-data/master/owid-co2-data.csv'
OWID_DISASTERS = 'https://ourworldindata.org/grapher/natural-disasters-by-type.csv?v=1&csvType=full&useColumnShortNames=true'
OWID_SEA = 'https://ourworldindata.org/grapher/sea-level.csv?v=1&csvType=full&useColumnShortNames=true'
GLACIERS = 'https://raw.githubusercontent.com/datasets/glacier-mass-balance/master/data/glaciers.csv'
OWID_FOREST = 'https://ourworldindata.org/grapher/forest-area-km.csv?v=1&csvType=full&useColumnShortNames=true'
NASA_POWER = 'https://power.larc.nasa.gov/api/temporal/monthly/point'

MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
EMITTERS = ['World', 'China', 'United States', 'India', 'Russia', 'Japan', 'Germany', 'Iran', 'South Korea',
            'Saudi Arabia', 'Indonesia', 'Canada', 'Mexico', 'Brazil', 'South Africa', 'United Kingdom',
            'Pakistan', 'Australia', 'Turkey', 'France']
CITIES = {
    'Karachi': (24.86, 67.01), 'Lahore': (31.55, 74.34), 'Delhi': (28.61, 77.21), 'Beijing': (39.90, 116.40),
    'Tokyo': (35.68, 139.69), 'Sydney': (-33.87, 151.21), 'Cairo': (30.04, 31.24), 'Lagos': (6.52, 3.38),
    'London': (51.51, -0.13), 'New York': (40.71, -74.01), 'Sao Paulo': (-23.55, -46.63), 'Moscow': (55.76, 37.62),
}


def fetch(url, **kwargs):
    resp = requests.get(url, timeout=90, **kwargs)
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


def city_climate(name, lat, lon):
    """Annual mean temperature and hottest day of the year for one city from NASA POWER (MERRA-2 reanalysis, 1981 onward)."""
    last_year = time.gmtime().tm_year - 1
    params = {'parameters': 'T2M,T2M_MAX', 'community': 'AG', 'longitude': lon, 'latitude': lat,
              'start': 1981, 'end': last_year, 'format': 'JSON'}
    for attempt in range(4):
        try:
            resp = requests.get(NASA_POWER, params=params, timeout=120)
            resp.raise_for_status()
            break
        except requests.RequestException:
            if attempt == 3:
                raise
            time.sleep(10 * (attempt + 1))
    values = resp.json()['properties']['parameter']
    rows = []
    for year in range(1981, last_year + 1):
        key = f'{year}13'                      # POWER stores the annual value under month "13"; for T2M_MAX that is the hottest day of the year
        mean, high = values['T2M'].get(key), values['T2M_MAX'].get(key)
        rows.append((name, lat, lon, year, None if mean is None or mean < -900 else mean, None if high is None or high < -900 else high))
    return pd.DataFrame(rows, columns=['city', 'lat', 'lon', 'year', 'temp_mean', 'hottest_day']).round(2)


class Command(BaseCommand):
    help = 'Download climate datasets from NASA, NOAA and Our World in Data into the partitioned data lake.'

    def add_arguments(self, parser):
        parser.add_argument('--skip-cities', action='store_true', help='skip the per-city NASA POWER download')
        parser.add_argument('--only-cities', action='store_true', help='refresh only the per-city dataset')

    def step(self, label, func):
        start = time.perf_counter()
        try:
            meta = func()
        except Exception as exc:  # one broken source must not abort the whole refresh
            self.stdout.write(self.style.WARNING(f'  skipped {label}: {exc}'))
            return
        self.stdout.write(f'  {label}: {meta["rows"]} rows, {meta["year_min"]}-{meta["year_max"]}, '
                          f'{len(meta["partitions"])} partitions ({time.perf_counter() - start:.1f}s)')

    def handle(self, *args, **options):
        self.stdout.write('Ingesting into climate/data/lake ...')

        def temperature():
            temp = pd.concat([temperature_series(c) for c in ('GLB', 'NH', 'SH')], axis=1)
            temp = temp.dropna(how='all').reset_index().sort_values(['year', 'month'])
            temp.columns = ['year', 'month', 'global_anomaly', 'nh_anomaly', 'sh_anomaly']
            temp, quality = lake.clean(temp, ['global_anomaly', 'nh_anomaly', 'sh_anomaly'])
            return lake.write_dataset('temperature_monthly', temp, {
                'title': 'Global surface temperature anomaly (monthly)', 'unit': 'deg C vs 1951-1980', 'category': 'Temperature',
                'source': 'NASA GISS GISTEMP v4', 'url': 'https://data.giss.nasa.gov/gistemp/', 'frequency': 'monthly'}, quality)

        def co2():
            data, quality = lake.clean(co2_series(), ['co2_ppm'])
            return lake.write_dataset('co2_monthly', data, {
                'title': 'Atmospheric CO2, Mauna Loa', 'unit': 'ppm', 'category': 'Greenhouse gases',
                'source': 'NOAA Global Monitoring Laboratory', 'url': 'https://gml.noaa.gov/ccgg/trends/', 'frequency': 'monthly'}, quality)

        def zonal():
            raw = pd.read_csv(io.StringIO(fetch(NASA_ZONAL)), na_values=['***'])
            raw = raw.rename(columns={'Year': 'year'})
            raw = raw[['year', '64N-90N', '44N-64N', '24N-44N', 'EQU-24N', '24S-EQU', '44S-24S', '64S-44S', '90S-64S']]
            raw.columns = ['year', 'arctic_64_90N', 'north_44_64N', 'north_24_44N', 'tropics_0_24N', 'tropics_24S_0',
                           'south_44_24S', 'south_64_44S', 'antarctic_90_64S']
            raw, quality = lake.clean(raw, list(raw.columns[1:]))
            return lake.write_dataset('temperature_zonal_annual', raw, {
                'title': 'Temperature anomaly by latitude band (annual)', 'unit': 'deg C vs 1951-1980', 'category': 'Temperature',
                'source': 'NASA GISS GISTEMP v4 (zonal means)', 'url': 'https://data.giss.nasa.gov/gistemp/', 'frequency': 'annual'}, quality)

        def emissions():
            raw = pd.read_csv(io.StringIO(fetch(OWID_CO2)), usecols=['country', 'year', 'iso_code', 'co2', 'co2_per_capita',
                                                                    'population', 'cumulative_co2', 'share_global_co2'])
            raw = raw[raw['country'].isin(EMITTERS) & (raw['year'] >= 1850)]
            raw, quality = lake.clean(raw, ['co2', 'co2_per_capita', 'cumulative_co2'], fill_limit=0)
            return lake.write_dataset('emissions_country_annual', raw, {
                'title': 'CO2 emissions by country (annual)', 'unit': 'million tonnes CO2', 'category': 'Emissions',
                'source': 'Global Carbon Project via Our World in Data', 'url': 'https://github.com/owid/co2-data', 'frequency': 'annual'}, quality)

        def disasters():
            raw = pd.read_csv(io.StringIO(fetch(OWID_DISASTERS)))
            raw = raw.rename(columns={'entity': 'disaster_type', 'n_events': 'events'})[['disaster_type', 'year', 'events']]
            raw, quality = lake.clean(raw, ['events'], fill_limit=0)
            return lake.write_dataset('disasters_annual', raw, {
                'title': 'Natural disasters by type (annual count)', 'unit': 'events', 'category': 'Impacts',
                'source': 'EM-DAT via Our World in Data', 'url': 'https://ourworldindata.org/natural-disasters', 'frequency': 'annual'}, quality)

        def sea_level():
            raw = pd.read_csv(io.StringIO(fetch(OWID_SEA)))
            raw = raw[raw['entity'] == 'World'].copy()
            raw['year'] = raw['quarter'].str[:4].astype(int)
            annual = raw.groupby('year', as_index=False)['sea_level_average'].mean().rename(columns={'sea_level_average': 'sea_level_mm'})
            annual, quality = lake.clean(annual, ['sea_level_mm'])
            return lake.write_dataset('sea_level_annual', annual.round(2), {
                'title': 'Global mean sea level', 'unit': 'mm (relative)', 'category': 'Oceans',
                'source': 'Church & White / UHSLC via Our World in Data', 'url': 'https://ourworldindata.org/sea-level-rise', 'frequency': 'annual'}, quality)

        def glaciers():
            raw = pd.read_csv(io.StringIO(fetch(GLACIERS))).rename(columns={
                'Year': 'year', 'Mean cumulative mass balance': 'mass_balance_mwe', 'Number of observations': 'observations'})
            raw, quality = lake.clean(raw, ['mass_balance_mwe', 'observations'], fill_limit=0)
            return lake.write_dataset('glacier_mass_annual', raw, {
                'title': 'Glacier cumulative mass balance', 'unit': 'm water equivalent', 'category': 'Ice',
                'source': 'US EPA / WGMS', 'url': 'https://github.com/datasets/glacier-mass-balance', 'frequency': 'annual'}, quality)

        def forest():
            raw = pd.read_csv(io.StringIO(fetch(OWID_FOREST)))
            col = [c for c in raw.columns if c not in ('entity', 'code', 'year')][0]
            raw = raw[raw['entity'] == 'World'].rename(columns={col: 'forest_km2'})[['year', 'forest_km2']]
            raw, quality = lake.clean(raw, ['forest_km2'], fill_limit=0)
            return lake.write_dataset('forest_area_annual', raw, {
                'title': 'World forest area', 'unit': 'km2', 'category': 'Land use',
                'source': 'FAO via Our World in Data', 'url': 'https://ourworldindata.org/forests-and-deforestation', 'frequency': 'annual'}, quality)

        def cities():
            frames = []
            for name, (lat, lon) in CITIES.items():
                frames.append(city_climate(name, lat, lon))
                time.sleep(1)
            data = pd.concat(frames, ignore_index=True)
            data, quality = lake.clean(data, ['temp_mean', 'hottest_day'], fill_limit=0)
            return lake.write_dataset('city_climate_annual', data, {
                'title': 'City temperatures (annual, 12 cities)', 'unit': 'deg C', 'category': 'Weather stations',
                'source': 'NASA POWER (MERRA-2 reanalysis)', 'url': 'https://power.larc.nasa.gov/', 'frequency': 'annual'}, quality)

        steps = [('temperature_monthly', temperature), ('co2_monthly', co2), ('temperature_zonal_annual', zonal),
                 ('emissions_country_annual', emissions), ('disasters_annual', disasters), ('sea_level_annual', sea_level),
                 ('glacier_mass_annual', glaciers), ('forest_area_annual', forest)]
        if options['only_cities']:
            steps = []
        if not options['skip_cities']:
            steps.append(('city_climate_annual', cities))
        for label, func in steps:
            self.step(label, func)
        manifest = lake.load_manifest()
        self.stdout.write(self.style.SUCCESS(f'Lake now holds {len(manifest)} datasets ({lake.lake_size_bytes() / 1024:.0f} KB).'))
