"""Predictive and pattern models, written with NumPy/pandas so they run anywhere (including serverless).

* Trend prediction: linear, quadratic and recent-window linear models compared by expanding-window backtest;
  the best one by RMSE is used for the projection.
* Anomaly detection: z-score against the 1951-1980 reference period.
* Regime clustering: k-means on standardised (temperature anomaly, CO2) pairs to find climate regimes.
* Correlation analysis: Pearson matrix across datasets on overlapping years.

``train_all`` re-fits everything on whatever is currently in the lake and records the run.
"""
import time

import numpy as np
import pandas as pd

from . import lake, monitor

FORECAST_END = 2050
REF_START, REF_END = 1951, 1980


def annual_temperature():
    temp = lake.read_dataset('temperature_monthly').copy()
    grouped = temp.groupby('year')
    out = grouped[['global_anomaly', 'nh_anomaly', 'sh_anomaly']].mean()
    return out[grouped['global_anomaly'].count() >= 10]          # partial years would bias trends


def annual_co2():
    co2 = lake.read_dataset('co2_monthly').copy()
    grouped = co2.groupby('year')['co2_ppm']
    out = grouped.mean()
    return out[grouped.count() >= 10]


def linear_fit(x, y):
    slope, intercept = np.polyfit(x, y, 1)
    pred = slope * x + intercept
    ss_res = float(np.sum((y - pred) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    return float(slope), float(intercept), (1 - ss_res / ss_tot) if ss_tot else 0.0


def _predict(kind, x, y, new_x):
    if kind == 'linear':
        return np.polyval(np.polyfit(x, y, 1), new_x)
    if kind == 'quadratic':
        return np.polyval(np.polyfit(x, y, 2), new_x)
    recent = x >= x.max() - 29                                    # 'recent30': linear on the last 30 years only
    return np.polyval(np.polyfit(x[recent], y[recent], 1), new_x)


MODEL_LABELS = {'linear': 'Linear (1970-)', 'quadratic': 'Quadratic (1970-)', 'recent30': 'Linear, last 30 years'}


def backtest(years, values, horizon=5, first_fold=25):
    """Expanding-window backtest: train up to year t, score the next `horizon` years, slide forward."""
    scores = {k: [] for k in MODEL_LABELS}
    for cut in range(first_fold, len(years) - horizon + 1):
        train_x, train_y = years[:cut], values[:cut]
        test_x, test_y = years[cut:cut + horizon], values[cut:cut + horizon]
        for kind in scores:
            pred = _predict(kind, train_x, train_y, test_x)
            scores[kind].append(float(np.sqrt(np.mean((test_y - pred) ** 2))))
    return {k: round(float(np.mean(v)), 4) for k, v in scores.items() if v}


def trend_model(annual_global):
    series = annual_global[annual_global.index >= 1970].dropna()
    years = series.index.values.astype(float)
    values = series.values
    scores = backtest(years, values)
    best = min(scores, key=scores.get)
    slope, intercept, r2 = linear_fit(years, values)
    residual_std = float(np.std(values - (slope * years + intercept), ddof=2))
    future = np.arange(int(years.max()) + 1, FORECAST_END + 1, dtype=float)
    predictions = {k: _predict(k, years, values, future) for k in MODEL_LABELS}
    chosen = predictions[best]
    band = 1.96 * residual_std
    return {
        'years': years, 'values': values, 'future': future, 'predictions': predictions,
        'best': best, 'scores': scores, 'band': band, 'residual_std': residual_std,
        'slope_decade': slope * 10, 'r2': r2, 'chosen': chosen,
        'fit': slope * years + intercept,
    }


def anomaly_model(annual_global, z_cut=2.0):
    baseline = annual_global[(annual_global.index >= REF_START) & (annual_global.index <= REF_END)]
    mean, std = float(baseline.mean()), float(baseline.std())
    z = (annual_global - mean) / std
    flagged = z[z > z_cut].sort_values(ascending=False)
    return {'mean': mean, 'std': std, 'z': z, 'flagged': flagged, 'z_cut': z_cut}


def kmeans(data, k=3, iters=60, seed=7):
    rng = np.random.default_rng(seed)
    centers = data[rng.choice(len(data), k, replace=False)]
    for _ in range(iters):
        labels = np.argmin(((data[:, None, :] - centers[None]) ** 2).sum(axis=2), axis=1)
        new = np.array([data[labels == i].mean(axis=0) if np.any(labels == i) else centers[i] for i in range(k)])
        if np.allclose(new, centers):
            break
        centers = new
    inertia = float(((data - centers[labels]) ** 2).sum())
    return labels, centers, inertia


def regime_model(k=3):
    """Cluster years into climate regimes using temperature anomaly and CO2."""
    joined = pd.concat([annual_temperature()['global_anomaly'], annual_co2()], axis=1, join='inner').dropna()
    raw = joined.values
    scaled = (raw - raw.mean(axis=0)) / raw.std(axis=0)
    labels, centers, inertia = kmeans(scaled, k)
    order = np.argsort(centers[:, 0])                              # coolest cluster first
    names = ['Cool baseline', 'Transition', 'Accelerated warming'][:k]
    rename = {int(old): names[i] for i, old in enumerate(order)}
    members = []
    for i, ((year, row), label) in enumerate(zip(joined.iterrows(), labels)):
        members.append({'year': int(year), 'co2': round(float(row['co2_ppm']), 2), 'anomaly': round(float(row['global_anomaly']), 3),
                        'regime': rename[int(label)]})
    summary = []
    for name in names:
        group = [m for m in members if m['regime'] == name]
        if group:
            summary.append({'regime': name, 'years': len(group), 'from': min(m['year'] for m in group), 'to': max(m['year'] for m in group),
                            'mean_anomaly': round(float(np.mean([m['anomaly'] for m in group])), 2),
                            'mean_co2': round(float(np.mean([m['co2'] for m in group])), 1)})
    return {'members': members, 'summary': summary, 'inertia': round(inertia, 3), 'k': k}


def annual_series_bundle():
    """One annual series per dataset, ready to be correlated."""
    series = {'Temperature anomaly': annual_temperature()['global_anomaly'], 'CO2 (ppm)': annual_co2()}
    pairs = [('sea_level_annual', 'sea_level_mm', 'Sea level (mm)'),
             ('glacier_mass_annual', 'mass_balance_mwe', 'Glacier mass balance'),
             ('forest_area_annual', 'forest_km2', 'Forest area')]
    for name, col, label in pairs:
        try:
            frame = lake.read_dataset(name)
            series[label] = frame.set_index('year')[col]
        except FileNotFoundError:
            pass
    try:
        emissions = lake.read_dataset('emissions_country_annual')
        world = emissions[emissions['country'] == 'World'].set_index('year')['co2']
        series['Fossil CO2 emissions'] = world
    except FileNotFoundError:
        pass
    try:
        disasters = lake.read_dataset('disasters_annual')
        series['Disaster events'] = disasters[disasters['disaster_type'] == 'All disasters'].set_index('year')['events']
    except FileNotFoundError:
        pass
    return series


def correlation_model(min_overlap=15):
    frame = pd.DataFrame(annual_series_bundle())
    labels = list(frame.columns)
    matrix = []
    for a in labels:
        row = []
        for b in labels:
            if a == b:
                row.append(1.0)
                continue
            both = frame[[a, b]].dropna()
            row.append(None if len(both) < min_overlap else round(float(both[a].corr(both[b])), 2))
        matrix.append(row)
    return {'labels': labels, 'matrix': matrix}


def train_all(user=''):
    """Re-fit every model on the data currently in the lake and store the run history."""
    from .models import ModelRun
    runs = []
    annual = annual_temperature()['global_anomaly']
    through = f'{int(annual.index.max())}'

    def record(name, fn):
        t0 = time.perf_counter()
        params, metrics = fn()
        ms = (time.perf_counter() - t0) * 1000
        monitor.record_stage(f'train:{name}', ms)
        runs.append(ModelRun.objects.create(name=name, data_through=through, params=params, metrics=metrics,
                                            duration_ms=round(ms, 1), triggered_by=user))

    def trend():
        m = trend_model(annual)
        return ({'selected': m['best'], 'training_years': f'1970-{int(m["years"].max())}'},
                {'backtest_rmse': m['scores'], 'slope_per_decade': round(m['slope_decade'], 3), 'r2': round(m['r2'], 3),
                 'projection_2050': round(float(m['chosen'][-1]), 2)})

    def anomaly():
        m = anomaly_model(annual)
        return ({'reference': f'{REF_START}-{REF_END}', 'z_cut': m['z_cut']},
                {'flagged_years': int(len(m['flagged'])), 'baseline_mean': round(m['mean'], 3), 'baseline_std': round(m['std'], 3)})

    def regimes():
        m = regime_model()
        return ({'k': m['k']}, {'inertia': m['inertia'], 'regimes': m['summary']})

    def correlation():
        m = correlation_model()
        return ({'series': m['labels']}, {'temperature_vs_co2': m['matrix'][0][1]})

    record('Trend prediction', trend)
    record('Anomaly detection', anomaly)
    record('Climate regimes (k-means)', regimes)
    record('Correlation analysis', correlation)
    return runs
