"""MongoDB document store (the climate data lake).

Database `earthscape` (open it in MongoDB Compass at mongodb://127.0.0.1:27017):
  * dataset_records : every row of every uploaded table, stored as-is (any CSV/JSON shape)
  * datasets        : dataset metadata + validation profile (including raster catalog entries)
  * readings        : station / sensor / live / API observations (unique per station+time+source)
  * alerts          : alerts raised by the rules engine
  * jobs            : processing job results (MapReduce, Hadoop, ML)
  * model_runs      : machine-learning runs and their measured metrics

Django's SQL database still holds users, sessions and app state. MongoDB is
written to on every ingest; if it is down the app keeps working and logs it.
"""
import logging
import math
from datetime import datetime, timezone as dt_tz

from django.conf import settings

log = logging.getLogger("earthscape")
_client = None


def _cfg():
    return settings.MONGODB


def db():
    global _client
    from pymongo import MongoClient
    if _client is None:
        _client = MongoClient(_cfg()["URI"], serverSelectionTimeoutMS=1500, connectTimeoutMS=1500)
    return _client[_cfg()["DB"]]


def _clean(v):
    """Make a value BSON-safe (NaN -> None, numpy -> Python)."""
    if v is None:
        return None
    if hasattr(v, "item"):
        v = v.item()
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    return v


def status():
    from django.core.cache import cache
    hit = cache.get("es:mongo_status")
    if hit is not None:
        return hit
    try:
        d = db()
        info = d.client.server_info()
        counts = {name: d[name].estimated_document_count() for name in
                  ("dataset_records", "datasets", "readings", "alerts", "jobs", "model_runs")}
        result = {"online": True, "version": info.get("version"), "db": _cfg()["DB"], "counts": counts,
                  "detail": f"MongoDB {info.get('version')} at {_cfg()['URI']}"}
    except Exception as e:
        result = {"online": False, "version": None, "db": _cfg()["DB"], "counts": {},
                  "detail": f"MongoDB not reachable ({e.__class__.__name__})"}
    cache.set("es:mongo_status", result, 20)
    return result


def ensure_indexes():
    from pymongo import ASCENDING, DESCENDING
    d = db()
    d.readings.create_index([("station", ASCENDING), ("timestamp", ASCENDING), ("source", ASCENDING)], unique=True)
    d.readings.create_index([("region", ASCENDING), ("timestamp", DESCENDING)])
    d.readings.create_index([("country", ASCENDING), ("timestamp", DESCENDING)])
    d.dataset_records.create_index([("_dataset_id", ASCENDING)])
    d.alerts.create_index([("alert_id", ASCENDING)], unique=True)
    d.alerts.create_index([("severity", ASCENDING), ("created", DESCENDING)])
    d.jobs.create_index([("job_id", ASCENDING)], unique=True)
    d.model_runs.create_index([("run_id", ASCENDING)], unique=True)


def _safe(fn):
    def wrapper(*args, **kwargs):
        if not _cfg().get("ENABLED", True):
            return None
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            log.warning("MongoDB write skipped (%s: %s)", e.__class__.__name__, e)
            return None
    wrapper.__name__ = fn.__name__
    return wrapper


def _reading_doc(r):
    return {"station": r.station, "country": r.country, "region": r.region,
            "location": ({"type": "Point", "coordinates": [r.longitude, r.latitude]}
                         if r.latitude is not None and r.longitude is not None else None),
            "timestamp": r.timestamp, "source": r.source,
            "temperature_c": _clean(r.temperature), "rainfall_mm": _clean(r.rainfall),
            "humidity_pct": _clean(r.humidity), "co2_ppm": _clean(r.co2),
            "dataset_id": r.dataset_id}


@_safe
def upsert_readings(readings):
    from pymongo import UpdateOne
    ops = [UpdateOne({"station": r.station, "timestamp": r.timestamp, "source": r.source},
                     {"$set": _reading_doc(r)}, upsert=True) for r in readings]
    if ops:
        db().readings.bulk_write(ops, ordered=False)
    return len(ops)


@_safe
def store_dataset_metadata(ds):
    """Store dataset catalog information without requiring tabular records."""
    d = db()
    d.datasets.update_one({"dataset_id": ds.id}, {"$set": {
        "dataset_id": ds.id, "name": ds.name, "kind": ds.kind, "format": ds.file_format,
        "original_filename": ds.original_filename, "rows": ds.rows, "columns": ds.columns,
        "missing_values": ds.missing_values, "duplicate_rows": ds.duplicate_rows, "status": ds.status,
        "column_profile": ds.profile.get("columns", []), "uploaded_by": getattr(ds.uploaded_by, "username", None),
        "created": ds.created}}, upsert=True)
    return True


@_safe
def store_dataset(ds, df):
    """Dataset metadata + every raw row as its own document."""
    d = db()
    store_dataset_metadata(ds)
    d.dataset_records.delete_many({"_dataset_id": ds.id})
    docs = []
    for i, row in enumerate(df.to_dict(orient="records")):
        doc = {str(k).replace(".", "_").replace("$", "_"): _clean(v) for k, v in row.items()}
        doc.update(_dataset_id=ds.id, _row=i)
        docs.append(doc)
    for start in range(0, len(docs), 5000):
        d.dataset_records.insert_many(docs[start:start + 5000], ordered=False)
    return len(docs)


@_safe
def update_dataset(ds):
    db().datasets.update_one({"dataset_id": ds.id}, {"$set": {
        "status": ds.status, "storage_backend": ds.storage_backend, "storage_path": ds.storage_path,
        "cleaning": ds.profile.get("cleaning"), "import": ds.profile.get("import")}}, upsert=True)


@_safe
def delete_dataset(dataset_id):
    d = db()
    d.datasets.delete_one({"dataset_id": dataset_id})
    d.dataset_records.delete_many({"_dataset_id": dataset_id})
    d.readings.delete_many({"dataset_id": dataset_id})


@_safe
def upsert_alert(a):
    db().alerts.update_one({"alert_id": a.id}, {"$set": {
        "alert_id": a.id, "title": a.title, "message": a.message, "severity": a.severity, "category": a.category,
        "value": _clean(a.value), "location": a.location, "observed_at": a.observed_at, "created": a.created,
        "rule": a.rule.name if a.rule else None}}, upsert=True)


@_safe
def log_job(job):
    db().jobs.update_one({"job_id": job.id}, {"$set": {
        "job_id": job.id, "job_type": job.job_type, "engine": job.engine, "status": job.status,
        "records_in": job.records_in, "records_out": job.records_out, "map_tasks": job.map_tasks,
        "skipped_records": job.skipped_records, "duration_ms": job.duration_ms, "error": job.error,
        "result": _jsonable(job.result), "created": job.created, "finished": job.finished}}, upsert=True)


@_safe
def log_model_run(run):
    db().model_runs.update_one({"run_id": run.id}, {"$set": {
        "run_id": run.id, "name": run.name, "task": run.task, "algorithm": run.algorithm,
        "data_source": run.data_source, "is_sample_data": run.is_sample_data, "n_train": run.n_train,
        "n_test": run.n_test, "metrics": run.metrics, "details": _jsonable(run.details),
        "trained_at": run.trained_at}}, upsert=True)


def _jsonable(obj):
    if isinstance(obj, dict):
        return {str(k).replace(".", "_").replace("$", "_"): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    return _clean(obj)


def sync_all():
    """Copy everything from the SQL database into MongoDB (safe to re-run)."""
    from .models import Alert, Dataset, ModelRun, ProcessingJob, SensorReading
    ensure_indexes()
    n_read = 0
    qs = SensorReading.objects.all().order_by("id")
    batch = []
    for r in qs.iterator(chunk_size=2000):
        batch.append(r)
        if len(batch) == 2000:
            n_read += upsert_readings(batch) or 0
            batch = []
    n_read += upsert_readings(batch) or 0
    for a in Alert.objects.select_related("rule"):
        upsert_alert(a)
    for j in ProcessingJob.objects.all():
        log_job(j)
    for m in ModelRun.objects.all():
        log_model_run(m)
    for ds in Dataset.objects.all():
        update_dataset(ds)
    return {"readings": n_read, "alerts": Alert.objects.count(), "jobs": ProcessingJob.objects.count(),
            "model_runs": ModelRun.objects.count(), "synced_at": datetime.now(dt_tz.utc).isoformat(timespec="seconds")}
