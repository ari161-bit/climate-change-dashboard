"""Machine learning for EarthScape (scikit-learn).

Every number shown in the UI is computed here from data; nothing is hard-coded.
  * temperature_trend  - Linear vs Polynomial(2) Ridge vs Random Forest, time-based hold-out
                         (last 10 years) on REAL FAO temperature data, best model forecasts ahead
  * rainfall_model     - Random Forest vs seasonal baseline on station readings
                         (flagged as sample data when the readings are synthetic)
  * anomaly_detection  - z-scores on real country temperature history + Isolation Forest on readings
  * correlation_analysis - Pearson r (with p-value) between real global temperature and disasters,
                         plus a variable correlation matrix on station readings
  * patterns           - decade averages and warming rate per region (real data)
"""
import logging
import math

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.ensemble import IsolationForest, RandomForestRegressor
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import PolynomialFeatures, StandardScaler

from . import datasources

log = logging.getLogger("earthscape")
RANDOM_STATE = 42


def _metrics(y_true, y_pred):
    return {
        "MAE": round(float(mean_absolute_error(y_true, y_pred)), 3),
        "RMSE": round(float(math.sqrt(mean_squared_error(y_true, y_pred))), 3),
        "R2": round(float(r2_score(y_true, y_pred)), 3) if len(y_true) > 1 else None,
    }


# ---------------------------------------------------------------------------
# Temperature trend prediction (real data)
# ---------------------------------------------------------------------------
def temperature_trend(country="World", test_years=10, horizon=2035):
    s = datasources.world_temperature_series(country)
    if len(s) < test_years + 10:
        return None
    X = s[["year"]].values.astype(float)
    y = s["anomaly"].values
    X_tr, X_te, y_tr, y_te = X[:-test_years], X[-test_years:], y[:-test_years], y[-test_years:]

    candidates = {
        "Linear regression": LinearRegression(),
        "Polynomial (deg 2) + Ridge": make_pipeline(StandardScaler(), PolynomialFeatures(2), Ridge(alpha=1.0)),
        "Random forest": RandomForestRegressor(n_estimators=200, random_state=RANDOM_STATE),
    }
    evaluation = []
    for name, model in candidates.items():
        model.fit(X_tr, y_tr)
        pred = model.predict(X_te)
        evaluation.append({"model": name, **_metrics(y_te, pred), "test_pred": [round(float(v), 3) for v in pred]})
    best = min(evaluation, key=lambda e: e["RMSE"])

    final = candidates[best["model"]]
    final.fit(X, y)                                 # refit on all years for the forecast
    future = np.arange(int(X[-1, 0]) + 1, horizon + 1).reshape(-1, 1).astype(float)
    fitted = final.predict(X)
    forecast = final.predict(future)
    resid_std = float(np.std(y - fitted))

    return {
        "country": country,
        "source": datasources.TEMP_SOURCE,
        "years": [int(v) for v in X[:, 0]],
        "actual": [round(float(v), 3) for v in y],
        "fitted": [round(float(v), 3) for v in fitted],
        "test_years": [int(v) for v in X_te[:, 0]],
        "evaluation": evaluation,
        "best_model": best["model"],
        "best_metrics": {k: best[k] for k in ("MAE", "RMSE", "R2")},
        "future_years": [int(v) for v in future[:, 0]],
        "forecast": [round(float(v), 3) for v in forecast],
        "forecast_band": round(1.96 * resid_std, 3),
        "warming_per_decade": round(float(np.polyfit(X[:, 0], y, 1)[0] * 10), 3),
        "n_train": len(y_tr), "n_test": len(y_te),
    }


# ---------------------------------------------------------------------------
# Rainfall prediction (station readings)
# ---------------------------------------------------------------------------
def rainfall_model(min_rows=60):
    df = datasources.readings_frame().dropna(subset=["rainfall", "temperature", "humidity"])
    if len(df) < min_rows:
        return {"ready": False, "reason": f"Need at least {min_rows} readings with rainfall, temperature and humidity "
                                          f"(have {len(df)}). Upload station data or run seed_sample_data."}
    month = df["timestamp"].dt.month
    feats = pd.DataFrame({
        "month_sin": np.sin(2 * np.pi * month / 12), "month_cos": np.cos(2 * np.pi * month / 12),
        "latitude": df["latitude"].fillna(0), "temperature": df["temperature"], "humidity": df["humidity"],
    })
    feats = pd.concat([feats, pd.get_dummies(df["region"].fillna("Unknown"), prefix="r", dtype=float)], axis=1)
    y = df["rainfall"].values
    idx = np.arange(len(df))
    tr, te = train_test_split(idx, test_size=0.2, random_state=RANDOM_STATE)

    # station climatology learned from the TRAINING rows only (no test leakage)
    key = (df["station"] + "|" + month.astype(str)).values
    base_map = pd.Series(y[tr]).groupby(key[tr]).mean()
    station_map = pd.Series(y[tr]).groupby(df["station"].values[tr]).mean()
    clim = pd.Series(key).map(base_map)
    clim = clim.fillna(pd.Series(df["station"].values).map(station_map)).fillna(float(np.mean(y[tr])))
    feats = feats.assign(station_month_mean=clim.values)

    rf = RandomForestRegressor(n_estimators=250, min_samples_leaf=3, random_state=RANDOM_STATE, n_jobs=-1)
    rf.fit(feats.iloc[tr], y[tr])
    pred = rf.predict(feats.iloc[te])

    # baseline: average rainfall for that station + month in the training set
    baseline = clim.values[te]

    importances = sorted(zip(feats.columns, rf.feature_importances_), key=lambda t: -t[1])[:6]
    sources = set(df["source"])
    order = np.argsort(y[te])[:: max(1, len(te) // 150)]          # thin out points for the chart
    return {
        "ready": True,
        "algorithm": "Random forest regressor (250 trees)",
        "metrics": _metrics(y[te], pred),
        "baseline_metrics": _metrics(y[te], baseline),
        "n_train": len(tr), "n_test": len(te),
        "actual": [round(float(v), 1) for v in y[te][order]],
        "predicted": [round(float(v), 1) for v in pred[order]],
        "importances": [{"feature": f, "importance": round(float(i), 3)} for f, i in importances],
        "is_sample_data": "sample" in sources,
        "data_label": datasources.data_badge(sources),
    }


# ---------------------------------------------------------------------------
# Anomaly detection
# ---------------------------------------------------------------------------
def anomaly_detection(z_threshold=2.5, recent_years=3, contamination=0.02):
    t = datasources.temperature()
    t = t[~t["is_region"]].dropna(subset=["anomaly"])
    g = t.groupby("Country")["anomaly"]
    t = t.assign(z=(t["anomaly"] - g.transform("mean")) / g.transform("std").replace(0, np.nan))
    last = int(t["year"].max())
    recent = t[(t["year"] > last - recent_years) & (t["z"].abs() >= z_threshold)].sort_values("z", ascending=False)
    anomalies = [{"type": "temperature", "location": r.Country, "iso3": r.ISO3, "year": int(r.year),
                  "value": round(float(r.anomaly), 2), "score": round(float(r.z), 2), "source": "real (FAO)"}
                 for r in recent.itertuples()]
    n_points = len(t)

    # Isolation Forest on station readings
    df = datasources.readings_frame().dropna(subset=["temperature", "rainfall", "humidity"])
    iso_info = None
    if len(df) >= 50:
        cols = ["temperature", "rainfall", "humidity"]
        z = df.groupby("station")[cols].transform(lambda c: (c - c.mean()) / (c.std() or 1))
        iso = IsolationForest(n_estimators=200, contamination=contamination, random_state=RANDOM_STATE)
        flags = iso.fit_predict(z.fillna(0))
        scores = -iso.score_samples(z.fillna(0))
        bad = df[flags == -1].assign(score=scores[flags == -1]).sort_values("score", ascending=False)
        for r in bad.head(40).itertuples():
            anomalies.append({"type": "station", "location": r.station, "iso3": "", "year": r.timestamp.year,
                              "date": r.timestamp.strftime("%Y-%m-%d"),
                              "value": round(float(r.temperature), 1), "rainfall": round(float(r.rainfall), 1),
                              "humidity": round(float(r.humidity), 1), "score": round(float(r.score), 3),
                              "source": datasources.data_badge({r.source})})
        n_points += len(df)
        iso_info = {"readings": len(df), "flagged": int((flags == -1).sum()), "contamination": contamination}

    return {"anomalies": anomalies, "n_points": n_points, "z_threshold": z_threshold, "latest_year": last,
            "isolation_forest": iso_info,
            "method": f"z-score >= {z_threshold} vs each country's 1961-{last} history (real data); "
                      f"Isolation Forest on standardised station readings"}


# ---------------------------------------------------------------------------
# Correlation analysis
# ---------------------------------------------------------------------------
def correlation_analysis():
    temp = datasources.world_temperature_series("World").set_index("year")["anomaly"]
    d = datasources.disasters()
    dis = d[d["kind"] == "TOTAL"].groupby("year")["count"].sum()
    both = pd.concat([temp, dis], axis=1, keys=["temp", "disasters"]).dropna()
    r, p = stats.pearsonr(both["temp"], both["disasters"])
    pairs = [{"a": "Global temperature anomaly", "b": "Climate disasters per year", "r": round(float(r), 3),
              "p_value": float(f"{p:.2e}"), "n": len(both), "source": "real (FAO + EM-DAT)",
              "years": f"{int(both.index.min())}-{int(both.index.max())}"}]

    matrix = None
    df = datasources.readings_frame()
    cols = [c for c in ["temperature", "rainfall", "humidity", "co2"] if df[c].notna().sum() > 30]
    if len(cols) >= 2:
        m = df[cols].astype(float).corr().round(3)
        matrix = {"variables": cols, "values": m.values.tolist(), "label": datasources.data_badge(set(df["source"]))}
        for i, a in enumerate(cols):
            for b in cols[i + 1:]:
                pairs.append({"a": a, "b": b, "r": float(m.loc[a, b]), "p_value": None,
                              "n": int(df[[a, b]].dropna().shape[0]), "source": matrix["label"], "years": ""})
    return {"pairs": pairs, "matrix": matrix, "n_years": len(both),
            "scatter": {"temp": [round(float(v), 3) for v in both["temp"]],
                        "disasters": [int(v) for v in both["disasters"]],
                        "years": [int(v) for v in both.index]}}


# ---------------------------------------------------------------------------
# Historical patterns (real data)
# ---------------------------------------------------------------------------
def patterns():
    t = datasources.temperature()
    reg = t[t["Country"].isin(datasources.REGIONS + ["World"])].dropna(subset=["anomaly"])
    reg = reg.assign(decade=(reg["year"] // 10 * 10))
    decades = sorted(reg["decade"].unique())
    table = reg.pivot_table(index="Country", columns="decade", values="anomaly", aggfunc="mean").round(2)
    rate = {c: round(float(np.polyfit(g["year"], g["anomaly"], 1)[0] * 10), 3) for c, g in reg.groupby("Country")}
    return {"decades": [int(d) for d in decades],
            "rows": [{"region": c, "values": [None if pd.isna(v) else float(v) for v in table.loc[c].tolist()],
                      "per_decade": rate[c]} for c in table.index],
            "source": datasources.TEMP_SOURCE}


# ---------------------------------------------------------------------------
# Train + record runs
# ---------------------------------------------------------------------------
def train_all():
    from .models import ModelRun
    runs = []
    tt = temperature_trend("World")
    if tt:
        runs.append(ModelRun.objects.create(
            name="Global temperature trend", task="temperature_trend", algorithm=tt["best_model"],
            data_source=tt["source"], is_sample_data=False, n_train=tt["n_train"], n_test=tt["n_test"],
            metrics=tt["best_metrics"], details={"evaluation": [{k: e[k] for k in ("model", "MAE", "RMSE", "R2")}
                                                               for e in tt["evaluation"]]}))
    rf = rainfall_model()
    if rf.get("ready"):
        runs.append(ModelRun.objects.create(
            name="Rainfall prediction", task="rainfall", algorithm=rf["algorithm"],
            data_source=f"Station readings ({rf['data_label']})", is_sample_data=rf["is_sample_data"],
            n_train=rf["n_train"], n_test=rf["n_test"], metrics=rf["metrics"],
            details={"baseline": rf["baseline_metrics"], "importances": rf["importances"]}))
    an = anomaly_detection()
    runs.append(ModelRun.objects.create(
        name="Climate anomaly detection", task="anomaly", algorithm="z-score + Isolation Forest",
        data_source="FAO temperature (real) + station readings", is_sample_data=False,
        n_train=an["n_points"], n_test=0,
        metrics={"anomalies_found": len(an["anomalies"]), "z_threshold": an["z_threshold"]},
        details={"isolation_forest": an["isolation_forest"]}))
    from . import mongo
    for r in runs:
        mongo.log_model_run(r)
    log.info("Trained %d models", len(runs))
    return runs
