"""Climate data processing: aggregation, anomaly detection, trend forecasting and alert evaluation."""
import os
from functools import lru_cache

import numpy as np
import pandas as pd
from django.conf import settings

DATA_DIR = os.path.join(settings.BASE_DIR, 'climate', 'data')
MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
FORECAST_END = 2050

DEFAULT_THRESHOLDS = [
    ('annual_anomaly', 'Annual temperature anomaly', 1.0, '°C', 'Alert when the latest complete year is warmer than this vs the 1951-1980 baseline.'),
    ('monthly_anomaly', 'Monthly temperature anomaly', 1.5, '°C', 'Alert when the latest month is warmer than this vs the 1951-1980 baseline.'),
    ('co2_level', 'Atmospheric CO2 level', 420.0, 'ppm', 'Alert when the latest Mauna Loa monthly CO2 exceeds this concentration.'),
    ('warming_rate', 'Warming rate', 0.25, '°C/decade', 'Alert when the linear warming trend since 1970 exceeds this rate.'),
]


@lru_cache(maxsize=1)
def _load():
    temp = pd.read_csv(os.path.join(DATA_DIR, 'temperature_monthly.csv'))
    co2 = pd.read_csv(os.path.join(DATA_DIR, 'co2_monthly.csv'))
    return temp, co2


def _annual_temperature(temp):
    """Annual means, keeping only years with at least 10 observed months so partial years don't skew trends."""
    grouped = temp.groupby('year')
    out = grouped[['global_anomaly', 'nh_anomaly', 'sh_anomaly']].mean()
    out = out[grouped['global_anomaly'].count() >= 10]
    return out


def _annual_co2(co2):
    grouped = co2.groupby('year')
    out = grouped['co2_ppm'].mean()
    return out[grouped['co2_ppm'].count() >= 10]


def _linear_fit(x, y):
    slope, intercept = np.polyfit(x, y, 1)
    pred = slope * x + intercept
    ss_res = float(np.sum((y - pred) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    return slope, intercept, (1 - ss_res / ss_tot) if ss_tot else 0.0


def _round(values, digits=3):
    return [None if pd.isna(v) else round(float(v), digits) for v in values]


def evaluate_alerts(kpis, thresholds):
    checks = [
        ('annual_anomaly', kpis['latest_year_anomaly'], f"{kpis['latest_year']} annual anomaly"),
        ('monthly_anomaly', kpis['latest_month_anomaly'], f"{kpis['latest_month_label']} monthly anomaly"),
        ('co2_level', kpis['co2_latest'], f"CO2 in {kpis['co2_latest_label']}"),
        ('warming_rate', kpis['warming_rate_per_decade'], 'Warming rate since 1970'),
    ]
    alerts = []
    for key, value, subject in checks:
        limit = thresholds.get(key)
        if limit is None or value is None:
            continue
        ratio = value / limit if limit else 0
        alerts.append({
            'key': key,
            'subject': subject,
            'value': round(value, 2),
            'threshold': limit,
            'triggered': value > limit,
            'severity': 'critical' if ratio >= 1.5 else ('warning' if ratio > 1 else 'ok'),
        })
    return alerts


def forecast(annual_global):
    """Linear + quadratic trend on 1970 onward, with a holdout check and a 95% band from residual spread."""
    series = annual_global[annual_global.index >= 1970].dropna()
    years = series.index.values.astype(float)
    values = series.values

    split = int(len(series) * 0.75)
    train_x, test_x = years[:split], years[split:]
    train_y, test_y = values[:split], values[split:]
    holdout = np.polyval(np.polyfit(train_x, train_y, 1), test_x)
    holdout_rmse = float(np.sqrt(np.mean((test_y - holdout) ** 2)))

    slope, intercept, r2 = _linear_fit(years, values)
    quad = np.polyfit(years, values, 2)
    residual_std = float(np.std(values - (slope * years + intercept), ddof=2))

    future = np.arange(int(years.max()) + 1, FORECAST_END + 1, dtype=float)
    linear_future = slope * future + intercept
    quad_future = np.polyval(quad, future)
    band = 1.96 * residual_std

    return {
        'history': [[int(y), round(float(v), 3)] for y, v in zip(years, values)],
        'fit': [[int(y), round(float(slope * y + intercept), 3)] for y in years],
        'future_years': [int(y) for y in future],
        'linear': _round(linear_future),
        'quadratic': _round(quad_future),
        'upper': _round(linear_future + band),
        'lower': _round(linear_future - band),
        'metrics': {
            'slope_per_decade': round(float(slope) * 10, 3),
            'r2': round(r2, 3),
            'holdout_rmse': round(holdout_rmse, 3),
            'residual_std': round(residual_std, 3),
            'projected_linear': round(float(linear_future[-1]), 2),
            'projected_quadratic': round(float(quad_future[-1]), 2),
            'train_years': f'{int(train_x[0])}-{int(train_x[-1])}',
            'test_years': f'{int(test_x[0])}-{int(test_x[-1])}',
        },
    }


def detect_anomalies(annual_global):
    """Flag years whose anomaly is >2 sigma above the 1951-1980 reference distribution."""
    baseline = annual_global[(annual_global.index >= 1951) & (annual_global.index <= 1980)]
    mean, std = baseline.mean(), baseline.std()
    z = (annual_global - mean) / std
    flagged = z[z > 2].sort_values(ascending=False)
    return {
        'baseline_mean': round(float(mean), 3),
        'baseline_std': round(float(std), 3),
        'count': int(len(flagged)),
        'first_year': int(flagged.index.min()) if len(flagged) else None,
        'top': [{'year': int(y), 'anomaly': round(float(annual_global[y]), 2), 'z': round(float(v), 1)}
                for y, v in flagged.head(8).items()],
        'flagged_years': [int(y) for y in flagged.index],
    }


def dashboard_data(start=None, end=None, thresholds=None):
    temp, co2 = _load()
    annual = _annual_temperature(temp)
    annual_co2 = _annual_co2(co2)

    min_year, max_year = int(temp['year'].min()), int(temp['year'].max())
    start = max(min_year, int(start)) if start else min_year
    end = min(max_year, int(end)) if end else max_year
    if start > end:
        start, end = end, start

    # --- headline KPIs (always on the full record) ---
    last_row = temp.dropna(subset=['global_anomaly']).iloc[-1]
    last_co2 = co2.iloc[-1]
    latest_year = int(annual.index.max())
    since_1970 = annual[annual.index >= 1970]['global_anomaly']
    warming_rate = _linear_fit(since_1970.index.values.astype(float), since_1970.values)[0] * 10
    joined = pd.concat([annual['global_anomaly'], annual_co2], axis=1, join='inner').dropna()
    correlation = float(joined['global_anomaly'].corr(joined['co2_ppm']))
    recent_co2 = annual_co2[annual_co2.index >= annual_co2.index.max() - 9]
    co2_growth = _linear_fit(recent_co2.index.values.astype(float), recent_co2.values)[0]
    warmest = annual['global_anomaly'].idxmax()

    kpis = {
        'latest_year': latest_year,
        'latest_year_anomaly': round(float(annual.loc[latest_year, 'global_anomaly']), 2),
        'latest_month_label': f"{MONTH_NAMES[int(last_row['month']) - 1]} {int(last_row['year'])}",
        'latest_month_anomaly': round(float(last_row['global_anomaly']), 2),
        'warmest_year': int(warmest),
        'warmest_anomaly': round(float(annual.loc[warmest, 'global_anomaly']), 2),
        'co2_latest': round(float(last_co2['co2_ppm']), 1),
        'co2_latest_label': f"{MONTH_NAMES[int(last_co2['month']) - 1]} {int(last_co2['year'])}",
        'co2_growth_per_year': round(float(co2_growth), 2),
        'co2_since_1958': round(float(last_co2['co2_ppm'] - co2.iloc[0]['co2_ppm']), 1),
        'warming_rate_per_decade': round(float(warming_rate), 3),
        'co2_temp_correlation': round(correlation, 3),
        'record_span': f'{min_year}-{max_year}',
    }

    # --- filtered window for the charts ---
    window = annual[(annual.index >= start) & (annual.index <= end)]
    rolling = annual['global_anomaly'].rolling(5, center=True, min_periods=3).mean()
    rolling = rolling[(rolling.index >= start) & (rolling.index <= end)]

    monthly = temp[(temp['year'] >= start) & (temp['year'] <= end)].dropna(subset=['global_anomaly'])
    monthly_points = [[int(pd.Timestamp(year=int(y), month=int(m), day=1).value // 10**6), round(float(v), 2)]
                      for y, m, v in zip(monthly['year'], monthly['month'], monthly['global_anomaly'])]

    decades = window['global_anomaly'].groupby((window.index // 10) * 10).mean()
    decades_nh = window['nh_anomaly'].groupby((window.index // 10) * 10).mean()
    decades_sh = window['sh_anomaly'].groupby((window.index // 10) * 10).mean()

    co2_window = co2[(co2['year'] >= start) & (co2['year'] <= end)]
    co2_points = [[int(pd.Timestamp(year=int(y), month=int(m), day=1).value // 10**6), round(float(v), 2)]
                  for y, m, v in zip(co2_window['year'], co2_window['month'], co2_window['co2_ppm'])]
    co2_annual_window = annual_co2[(annual_co2.index >= start) & (annual_co2.index <= end)]

    scatter = joined[(joined.index >= start) & (joined.index <= end)]
    scatter_fit = None
    if len(scatter) > 3:
        slope, intercept, r2 = _linear_fit(scatter['co2_ppm'].values, scatter['global_anomaly'].values)
        xs = [float(scatter['co2_ppm'].min()), float(scatter['co2_ppm'].max())]
        scatter_fit = {
            'line': [[round(x, 1), round(slope * x + intercept, 3)] for x in xs],
            'slope': round(float(slope), 4),
            'r2': round(r2, 3),
        }

    # Seasonal profile: mean anomaly by calendar month for the last 30 years vs the first 30.
    def month_profile(lo, hi):
        sub = temp[(temp['year'] >= lo) & (temp['year'] <= hi)].groupby('month')['global_anomaly'].mean()
        return _round(sub.reindex(range(1, 13)))

    seasonal = {
        'months': MONTH_NAMES,
        'early': month_profile(1951, 1980),
        'recent': month_profile(max_year - 29, max_year),
        'recent_label': f'{max_year - 29}-{max_year}',
    }

    thresholds = thresholds or {k: v for k, _, v, _, _ in DEFAULT_THRESHOLDS}
    annual_global = annual['global_anomaly']

    return {
        'meta': {'min_year': min_year, 'max_year': max_year, 'start': start, 'end': end},
        'kpis': kpis,
        'alerts': evaluate_alerts(kpis, thresholds),
        'annual': {
            'years': [int(y) for y in window.index],
            'global': _round(window['global_anomaly']),
            'nh': _round(window['nh_anomaly']),
            'sh': _round(window['sh_anomaly']),
            'rolling': _round(rolling),
        },
        'monthly_global': monthly_points,
        'decades': {
            'labels': [f'{int(d)}s' for d in decades.index],
            'global': _round(decades),
            'nh': _round(decades_nh),
            'sh': _round(decades_sh),
        },
        'co2': {
            'monthly': co2_points,
            'annual_years': [int(y) for y in co2_annual_window.index],
            'annual': _round(co2_annual_window, 2),
        },
        'scatter': {
            'points': [[round(float(c), 1), round(float(t), 3), int(y)]
                       for y, c, t in zip(scatter.index, scatter['co2_ppm'], scatter['global_anomaly'])],
            'fit': scatter_fit,
        },
        'seasonal': seasonal,
        'forecast': forecast(annual_global),
        'anomalies': detect_anomalies(annual_global),
    }
