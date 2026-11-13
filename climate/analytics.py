"""Dashboard computations on top of the data lake: aggregation, MapReduce decade stats, regional / emissions /
impact / city views, forecasts and alert evaluation."""
import numpy as np
import pandas as pd

from . import lake, ml, monitor, pipeline

MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
FORECAST_END = ml.FORECAST_END

# key, label, default, unit, description
DEFAULT_THRESHOLDS = [
    ('annual_anomaly', 'Annual temperature anomaly', 1.0, '°C', 'Alert when the latest complete year is warmer than this vs the 1951-1980 baseline.'),
    ('monthly_anomaly', 'Monthly temperature anomaly', 1.5, '°C', 'Alert when the latest month is warmer than this vs the 1951-1980 baseline.'),
    ('co2_level', 'Atmospheric CO2 level', 420.0, 'ppm', 'Alert when the latest Mauna Loa monthly CO2 exceeds this concentration.'),
    ('warming_rate', 'Warming rate', 0.25, '°C/decade', 'Alert when the linear warming trend since 1970 exceeds this rate.'),
    ('sea_level_rate', 'Sea-level rise rate', 3.0, 'mm/yr', 'Alert when the 30-year sea-level trend exceeds this rate.'),
    ('live_heat', 'Live heat alert', 35.0, '°C', 'Real-time alert when a monitored city is currently hotter than this.'),
    ('live_pm25', 'Live air-quality alert', 35.0, 'µg/m³', 'Real-time alert when a monitored city has PM2.5 above this (WHO 24h guideline is 15).'),
]


def _round(values, digits=3):
    return [None if pd.isna(v) else round(float(v), digits) for v in values]


def _ms(ts_year, ts_month):
    return int(pd.Timestamp(year=int(ts_year), month=int(ts_month), day=1).value // 10 ** 6)


def evaluate_alerts(kpis, thresholds):
    checks = [
        ('annual_anomaly', kpis['latest_year_anomaly'], f"{kpis['latest_year']} annual anomaly"),
        ('monthly_anomaly', kpis['latest_month_anomaly'], f"{kpis['latest_month_label']} monthly anomaly"),
        ('co2_level', kpis['co2_latest'], f"CO2 in {kpis['co2_latest_label']}"),
        ('warming_rate', kpis['warming_rate_per_decade'], 'Warming rate since 1970'),
        ('sea_level_rate', kpis.get('sea_level_rate'), 'Sea-level rise, 30-year trend'),
    ]
    alerts = []
    for key, value, subject in checks:
        limit = thresholds.get(key)
        if limit is None or value is None:
            continue
        ratio = value / limit if limit else 0
        alerts.append({'key': key, 'subject': subject, 'value': round(value, 2), 'threshold': limit,
                       'triggered': value > limit,
                       'severity': 'critical' if ratio >= 1.5 else ('warning' if ratio > 1 else 'ok')})
    return alerts


def decade_stats(start, end):
    """MapReduce job over the temperature partitions: mean anomaly and share of 'hot' months per decade."""
    def mapper(frame):
        frame = frame.dropna(subset=['global_anomaly'])
        for decade, chunk in frame.groupby((frame['year'] // 10) * 10):
            yield int(decade), (len(chunk), float(chunk['global_anomaly'].sum()), float(chunk['nh_anomaly'].sum()),
                                float(chunk['sh_anomaly'].sum()), int((chunk['global_anomaly'] > 1.0).sum()))

    def reducer(_, values):
        n = sum(v[0] for v in values)
        return {'global': sum(v[1] for v in values) / n, 'nh': sum(v[2] for v in values) / n,
                'sh': sum(v[3] for v in values) / n, 'hot_months_pct': 100 * sum(v[4] for v in values) / n, 'months': n}

    return pipeline.run_job('temperature_monthly', mapper, reducer, start, end)


def forecast_block(annual_global):
    m = ml.trend_model(annual_global)
    future = [int(y) for y in m['future']]
    return {
        'history': [[int(y), round(float(v), 3)] for y, v in zip(m['years'], m['values'])],
        'fit': [[int(y), round(float(v), 3)] for y, v in zip(m['years'], m['fit'])],
        'future_years': future,
        'linear': _round(m['predictions']['linear']),
        'quadratic': _round(m['predictions']['quadratic']),
        'recent30': _round(m['predictions']['recent30']),
        'chosen': _round(m['chosen']),
        'upper': _round(m['chosen'] + m['band']),
        'lower': _round(m['chosen'] - m['band']),
        'metrics': {
            'selected': ml.MODEL_LABELS[m['best']],
            'scores': {ml.MODEL_LABELS[k]: v for k, v in m['scores'].items()},
            'slope_per_decade': round(m['slope_decade'], 3),
            'r2': round(m['r2'], 3),
            'residual_std': round(m['residual_std'], 3),
            'projected_best': round(float(m['chosen'][-1]), 2),
            'projected_linear': round(float(m['predictions']['linear'][-1]), 2),
            'projected_quadratic': round(float(m['predictions']['quadratic'][-1]), 2),
            'projected_recent30': round(float(m['predictions']['recent30'][-1]), 2),
        },
    }


def anomalies_block(annual_global):
    m = ml.anomaly_model(annual_global)
    flagged = m['flagged']
    return {
        'baseline_mean': round(m['mean'], 3) + 0.0, 'baseline_std': round(m['std'], 3), 'count': int(len(flagged)),
        'first_year': int(flagged.index.min()) if len(flagged) else None,
        'top': [{'year': int(y), 'anomaly': round(float(annual_global[y]), 2), 'z': round(float(v), 1)}
                for y, v in flagged.head(8).items()],
        'flagged_years': [int(y) for y in flagged.index],
    }


def regions_block():
    try:
        zonal = lake.read_dataset('temperature_zonal_annual').set_index('year')
    except FileNotFoundError:
        return None
    labels = {'arctic_64_90N': 'Arctic 64-90°N', 'north_44_64N': '44-64°N', 'north_24_44N': '24-44°N', 'tropics_0_24N': 'Tropics 0-24°N',
              'tropics_24S_0': 'Tropics 24°S-0', 'south_44_24S': '44-24°S', 'south_64_44S': '64-44°S', 'antarctic_90_64S': 'Antarctic 90-64°S'}
    last = int(zonal.index.max())
    recent = zonal[zonal.index > last - 10].mean()
    early = zonal[(zonal.index >= 1991) & (zonal.index <= 2000)].mean()
    glob = float(recent.mean())
    return {
        'labels': [labels[c] for c in zonal.columns], 'recent': _round([recent[c] for c in zonal.columns], 2),
        'nineties': _round([early[c] for c in zonal.columns], 2), 'recent_label': f'{last - 9}-{last}',
        'arctic_ratio': round(float(recent['arctic_64_90N'] / glob), 1) if glob else None,
    }


def emissions_block(start, end):
    try:
        data = lake.read_dataset('emissions_country_annual').copy()
    except FileNotFoundError:
        return None
    world = data[data['country'] == 'World'].set_index('year')['co2']
    world = world[(world.index >= max(start, 1850)) & (world.index <= end)]
    latest_year = int(data[data['country'] != 'World']['year'].max())
    latest = data[(data['year'] == latest_year) & (data['country'] != 'World')].sort_values('co2', ascending=False).head(10)
    cumulative = data[(data['year'] == latest_year - 1) & (data['country'] != 'World')].sort_values('cumulative_co2', ascending=False).head(10)
    return {
        'world_years': [int(y) for y in world.index], 'world': _round(world, 1),
        'latest_year': latest_year,
        'top': {'country': list(latest['country']), 'co2': _round(latest['co2'], 1), 'per_capita': _round(latest['co2_per_capita'], 2)},
        'cumulative': {'country': list(cumulative['country']), 'value': _round(cumulative['cumulative_co2'], 0)},
    }


def impacts_block(start, end):
    out = {}
    try:
        sea = lake.read_dataset('sea_level_annual').set_index('year')['sea_level_mm']
        sea_w = sea[(sea.index >= start) & (sea.index <= end)]
        out['sea'] = {'years': [int(y) for y in sea_w.index], 'values': _round(sea_w, 1)}
    except FileNotFoundError:
        pass
    try:
        gl = lake.read_dataset('glacier_mass_annual').set_index('year')['mass_balance_mwe']
        gl_w = gl[(gl.index >= start) & (gl.index <= end)]
        out['glaciers'] = {'years': [int(y) for y in gl_w.index], 'values': _round(gl_w, 2)}
    except FileNotFoundError:
        pass
    try:
        dis = lake.read_dataset('disasters_annual').copy()
        types = [t for t in dis['disaster_type'].unique() if not t.startswith('All disasters')]
        dis = dis[(dis['year'] >= start) & (dis['year'] <= end)]
        years = sorted(dis['year'].unique())
        series = []
        for t in types:
            sub = dis[dis['disaster_type'] == t].set_index('year')['events'].reindex(years).fillna(0)
            if sub.sum() > 0:
                series.append({'name': t, 'data': [int(v) for v in sub.values], 'total': int(sub.sum())})
        series.sort(key=lambda s: -s['total'])
        out['disasters'] = {'years': [int(y) for y in years], 'series': series[:6]}
    except FileNotFoundError:
        pass
    try:
        forest = lake.read_dataset('forest_area_annual').set_index('year')['forest_km2']
        out['forest'] = {'years': [int(y) for y in forest.index], 'values': _round(forest / 1e6, 3)}
    except FileNotFoundError:
        pass
    return out


def cities_block():
    try:
        data = lake.read_dataset('city_climate_annual').copy()
    except FileNotFoundError:
        return None
    rows = []
    for city, grp in data.groupby('city'):
        grp = grp.dropna(subset=['temp_mean']).sort_values('year')
        if len(grp) < 20:
            continue
        slope = ml.linear_fit(grp['year'].values.astype(float), grp['temp_mean'].values)[0] * 10
        first, last = grp.head(10), grp.tail(10)
        rows.append({'city': city, 'lat': float(grp['lat'].iloc[0]), 'lon': float(grp['lon'].iloc[0]),
                     'trend_per_decade': round(slope, 2), 'recent_mean': round(float(last['temp_mean'].mean()), 1),
                     'change': round(float(last['temp_mean'].mean() - first['temp_mean'].mean()), 2),
                     'hot_recent': round(float(last['hottest_day'].mean()), 1), 'hot_early': round(float(first['hottest_day'].mean()), 1),
                     'years': f"{int(grp['year'].min())}-{int(grp['year'].max())}"})
    rows.sort(key=lambda r: -r['trend_per_decade'])
    return rows


def dashboard_data(start=None, end=None, thresholds=None):
    with monitor.stage('dashboard:total'):
        with monitor.stage('dashboard:load'):
            temp = lake.read_dataset('temperature_monthly').copy()
            co2 = lake.read_dataset('co2_monthly').copy()
        annual = ml.annual_temperature()
        annual_co2 = ml.annual_co2()

        min_year, max_year = int(temp['year'].min()), int(temp['year'].max())
        start = max(min_year, int(start)) if start else min_year
        end = min(max_year, int(end)) if end else max_year
        if start > end:
            start, end = end, start
        start, end = max(min_year, start), min(max_year, end)

        last_row = temp.dropna(subset=['global_anomaly']).iloc[-1]
        last_co2 = co2.iloc[-1]
        latest_year = int(annual.index.max())
        since_1970 = annual[annual.index >= 1970]['global_anomaly']
        warming_rate = ml.linear_fit(since_1970.index.values.astype(float), since_1970.values)[0] * 10
        joined = pd.concat([annual['global_anomaly'], annual_co2], axis=1, join='inner').dropna()
        correlation = float(joined['global_anomaly'].corr(joined['co2_ppm']))
        recent_co2 = annual_co2[annual_co2.index >= annual_co2.index.max() - 9]
        co2_growth = ml.linear_fit(recent_co2.index.values.astype(float), recent_co2.values)[0]
        warmest = annual['global_anomaly'].idxmax()
        sea_rate = None
        try:
            sea = lake.read_dataset('sea_level_annual').set_index('year')['sea_level_mm'].dropna()
            tail = sea[sea.index >= sea.index.max() - 29]
            sea_rate = round(ml.linear_fit(tail.index.values.astype(float), tail.values)[0], 2)
        except FileNotFoundError:
            pass

        kpis = {
            'latest_year': latest_year,
            'latest_year_anomaly': round(float(annual.loc[latest_year, 'global_anomaly']), 2),
            'latest_month_label': f"{MONTH_NAMES[int(last_row['month']) - 1]} {int(last_row['year'])}",
            'latest_month_anomaly': round(float(last_row['global_anomaly']), 2),
            'warmest_year': int(warmest), 'warmest_anomaly': round(float(annual.loc[warmest, 'global_anomaly']), 2),
            'co2_latest': round(float(last_co2['co2_ppm']), 1),
            'co2_latest_label': f"{MONTH_NAMES[int(last_co2['month']) - 1]} {int(last_co2['year'])}",
            'co2_growth_per_year': round(float(co2_growth), 2), 'co2_since_1958': round(float(last_co2['co2_ppm'] - co2.iloc[0]['co2_ppm']), 1),
            'warming_rate_per_decade': round(float(warming_rate), 3), 'co2_temp_correlation': round(correlation, 3),
            'sea_level_rate': sea_rate, 'record_span': f'{min_year}-{max_year}',
        }

        window = annual[(annual.index >= start) & (annual.index <= end)]
        rolling = annual['global_anomaly'].rolling(5, center=True, min_periods=3).mean()
        rolling = rolling[(rolling.index >= start) & (rolling.index <= end)]
        monthly = temp[(temp['year'] >= start) & (temp['year'] <= end)].dropna(subset=['global_anomaly'])
        monthly_points = [[_ms(y, m), round(float(v), 2)] for y, m, v in zip(monthly['year'], monthly['month'], monthly['global_anomaly'])]
        co2_window = co2[(co2['year'] >= start) & (co2['year'] <= end)]
        co2_points = [[_ms(y, m), round(float(v), 2)] for y, m, v in zip(co2_window['year'], co2_window['month'], co2_window['co2_ppm'])]
        co2_annual_window = annual_co2[(annual_co2.index >= start) & (annual_co2.index <= end)]
        decades = decade_stats(start, end)

        scatter = joined[(joined.index >= start) & (joined.index <= end)]
        scatter_fit = None
        if len(scatter) > 3:
            slope, intercept, r2 = ml.linear_fit(scatter['co2_ppm'].values, scatter['global_anomaly'].values)
            xs = [float(scatter['co2_ppm'].min()), float(scatter['co2_ppm'].max())]
            scatter_fit = {'line': [[round(x, 1), round(slope * x + intercept, 3)] for x in xs], 'slope': round(slope, 4), 'r2': round(r2, 3)}

        def month_profile(lo, hi):
            sub = temp[(temp['year'] >= lo) & (temp['year'] <= hi)].groupby('month')['global_anomaly'].mean()
            return _round(sub.reindex(range(1, 13)))

        seasonal = {'months': MONTH_NAMES, 'early': month_profile(1951, 1980), 'recent': month_profile(max_year - 29, max_year),
                    'recent_label': f'{max_year - 29}-{max_year}'}
        thresholds = thresholds or {k: v for k, _, v, _, _ in DEFAULT_THRESHOLDS}
        annual_global = annual['global_anomaly']

        with monitor.stage('dashboard:models'):
            forecast = forecast_block(annual_global)
            anomalies = anomalies_block(annual_global)

        return {
            'meta': {'min_year': min_year, 'max_year': max_year, 'start': start, 'end': end},
            'kpis': kpis,
            'alerts': evaluate_alerts(kpis, thresholds),
            'annual': {'years': [int(y) for y in window.index], 'global': _round(window['global_anomaly']), 'nh': _round(window['nh_anomaly']),
                       'sh': _round(window['sh_anomaly']), 'rolling': _round(rolling)},
            'monthly_global': monthly_points,
            'decades': {'labels': [f'{d}s' for d in decades], 'global': _round([v['global'] for v in decades.values()]),
                        'nh': _round([v['nh'] for v in decades.values()]), 'sh': _round([v['sh'] for v in decades.values()]),
                        'hot_months_pct': _round([v['hot_months_pct'] for v in decades.values()], 1)},
            'co2': {'monthly': co2_points, 'annual_years': [int(y) for y in co2_annual_window.index], 'annual': _round(co2_annual_window, 2)},
            'scatter': {'points': [[round(float(c), 1), round(float(t), 3), int(y)] for y, c, t in
                                   zip(scatter.index, scatter['co2_ppm'], scatter['global_anomaly'])], 'fit': scatter_fit},
            'seasonal': seasonal,
            'forecast': forecast,
            'anomalies': anomalies,
            'regions': regions_block(),
            'emissions': emissions_block(start, end),
            'impacts': impacts_block(start, end),
            'cities': cities_block(),
            'correlation': ml.correlation_model(),
        }


def catalogue():
    """Dataset catalogue from the lake manifest (provenance, size, quality) for the Data Explorer."""
    manifest = lake.load_manifest()
    out = []
    for name, meta in sorted(manifest.items(), key=lambda kv: (kv[1].get('category', ''), kv[0])):
        quality = meta.get('quality', {})
        missing = quality.get('missing_pct', {})
        out.append({
            'name': name, 'title': meta.get('title', name), 'category': meta.get('category', ''), 'unit': meta.get('unit', ''),
            'source': meta.get('source', ''), 'url': meta.get('url', ''), 'frequency': meta.get('frequency', ''),
            'rows': meta['rows'], 'years': f"{meta['year_min']}-{meta['year_max']}", 'partitions': len(meta['partitions']),
            'columns': meta['columns'], 'sha256': meta['sha256'][:12], 'ingested_at': meta['ingested_at'],
            'gaps_filled': quality.get('gaps_filled', 0), 'max_missing_pct': max(missing.values()) if missing else 0.0,
        })
    return out


def dataset_preview(name, series_col=None, group=None):
    """Chart-ready series for one lake dataset."""
    frame = lake.read_dataset(name).copy()
    meta = lake.load_manifest()[name]
    numeric = [c for c in frame.columns if c not in ('year', 'month', 'lat', 'lon') and pd.api.types.is_numeric_dtype(frame[c])]
    group_cols = [c for c in frame.columns if c in ('country', 'disaster_type', 'city')]
    groups = sorted(frame[group_cols[0]].unique()) if group_cols else []
    if group_cols and group is None:
        group = groups[0]
    if group_cols:
        frame = frame[frame[group_cols[0]] == group]
    series_col = series_col if series_col in numeric else numeric[0]
    if 'month' in frame.columns:
        frame = frame.dropna(subset=[series_col])
        points = [[_ms(y, m), round(float(v), 3)] for y, m, v in zip(frame['year'], frame['month'], frame[series_col])]
        kind = 'datetime'
    else:
        frame = frame.dropna(subset=[series_col]).sort_values('year')
        points = [[int(y), round(float(v), 3)] for y, v in zip(frame['year'], frame[series_col])]
        kind = 'linear'
    values = [p[1] for p in points]
    return {'name': name, 'title': meta['title'], 'unit': meta['unit'], 'column': series_col, 'columns': numeric,
            'group_label': group_cols[0] if group_cols else None, 'groups': groups, 'group': group, 'kind': kind, 'points': points,
            'stats': {'count': len(values), 'min': min(values) if values else None, 'max': max(values) if values else None,
                      'mean': round(float(np.mean(values)), 3) if values else None}}
