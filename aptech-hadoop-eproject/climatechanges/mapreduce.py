"""Local MapReduce engine + the processing jobs that run on it.

The engine follows the Hadoop model exactly: split input -> map tasks run in
parallel -> shuffle/sort by key -> reduce. Rows that cannot be parsed are
counted as skipped (incomplete data is handled, not fatal).

On a real cluster the same logic runs with Hadoop Streaming (hadoop/mapper.py,
hadoop/reducer.py); the UI always shows which engine actually ran.
"""
import csv
import logging
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from django.conf import settings
from django.utils import timezone

from . import datasources, hadoop

log = logging.getLogger("earthscape")


class MapReduceResult:
    def __init__(self, output, records_in, skipped, map_tasks, ms):
        self.output, self.records_in, self.skipped, self.map_tasks, self.ms = output, records_in, skipped, map_tasks, ms


def run_mapreduce(rows, mapper, reducer, n_tasks=4):
    """rows: list of dicts. mapper(row) -> iterable of (key, value) or raises. reducer(key, values) -> value."""
    start = time.perf_counter()
    n_tasks = max(1, min(n_tasks, len(rows) or 1))
    chunks = [rows[i::n_tasks] for i in range(n_tasks)]

    def map_task(chunk):
        out, skipped = [], 0
        for row in chunk:
            try:
                out.extend(mapper(row))
            except (ValueError, KeyError, TypeError):
                skipped += 1
        return out, skipped

    with ThreadPoolExecutor(max_workers=n_tasks) as pool:
        results = list(pool.map(map_task, chunks))

    groups = defaultdict(list)                     # shuffle
    skipped = 0
    for pairs, sk in results:
        skipped += sk
        for k, v in pairs:
            groups[k].append(v)
    output = {k: reducer(k, vs) for k, vs in sorted(groups.items())}   # sort + reduce
    ms = int((time.perf_counter() - start) * 1000)
    return MapReduceResult(output, len(rows), skipped, n_tasks, ms)


def _read_csv(name):
    with open(Path(settings.DATA_DIR) / name, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------
def job_yearly_temperature():
    rows = _read_csv("Temperature.csv")
    regions = set(datasources.REGIONS + ["World"])

    def mapper(r):
        if r["Country"] in regions:
            return []
        out = []
        for k, v in r.items():
            if k.isdigit() and v not in ("", None):
                out.append((int(k), float(v)))
        if not out:
            raise ValueError("no values")
        return out

    def reducer(year, vals):
        return {"mean": round(float(np.mean(vals)), 3), "countries": len(vals),
                "min": round(min(vals), 2), "max": round(max(vals), 2)}

    mr = run_mapreduce(rows, mapper, reducer)
    return mr, "data/Temperature.csv"


def job_disasters_per_year():
    rows = _read_csv("Disaster.csv")

    def mapper(r):
        if not r.get("ISO2") or not r["Indicator"].endswith("Number of Disasters: TOTAL"):
            return []
        return [(int(k), int(float(v))) for k, v in r.items() if k.isdigit() and v not in ("", None)]

    mr = run_mapreduce(rows, mapper, lambda k, vs: sum(vs))
    return mr, "data/Disaster.csv"


def job_regional_averages():
    rows = _read_csv("Temperature.csv")

    def mapper(r):
        if r["Country"] not in datasources.REGIONS:
            return []
        out = []
        for k, v in r.items():
            if k.isdigit() and v not in ("", None):
                decade = int(k) // 10 * 10
                out.append((f"{r['Country']}|{decade}s", float(v)))
        return out

    mr = run_mapreduce(rows, mapper, lambda k, vs: round(float(np.mean(vs)), 3))
    return mr, "data/Temperature.csv"


JOBS = {
    "yearly_temperature": job_yearly_temperature,
    "disasters_per_year": job_disasters_per_year,
    "regional_averages": job_regional_averages,
}


def run_job(job_type, user=None):
    """Run any processing job and record it as a ProcessingJob."""
    from . import ml, alerts
    from .models import ProcessingJob

    job = ProcessingJob.objects.create(job_type=job_type, status="running", started_by=user,
                                       engine="local-mapreduce" if job_type in JOBS else "python")
    start = time.perf_counter()
    try:
        if job_type in JOBS:
            mr, src = JOBS[job_type]()
            job.input_path = src
            job.records_in, job.records_out = mr.records_in, len(mr.output)
            job.map_tasks, job.skipped_records = mr.map_tasks, mr.skipped
            job.result = {"output": {str(k): v for k, v in mr.output.items()},
                          "hadoop_command": hadoop.streaming_command(job_type, f"/climate/raw/{Path(src).name}")}
        elif job_type == "hadoop_disasters_per_year":
            if not hadoop.status(fresh=True)["online"]:
                raise RuntimeError("HDFS is not running. Start it with hadoop/start_hdfs.cmd, then try again.")
            job.engine = "hadoop-streaming"
            job.input_path = "hdfs:///climate/Disaster.csv"
            out, log_tail = hadoop.run_streaming_job()
            job.records_out = len(out)
            job.result = {"output": out, "hadoop_log": log_tail,
                          "output_path": "hdfs:///climate/output/disasters_per_year/part-00000"}
        elif job_type == "anomaly_scan":
            res = ml.anomaly_detection()
            job.records_in, job.records_out = res["n_points"], len(res["anomalies"])
            job.result = {"anomalies": res["anomalies"][:50], "method": res["method"]}
            alerts.alerts_from_anomalies(res)
        elif job_type == "correlation":
            res = ml.correlation_analysis()
            job.records_in, job.records_out = res["n_years"], len(res["pairs"])
            job.result = res
        elif job_type == "train_models":
            runs = ml.train_all()
            job.records_out = len(runs)
            job.result = {"models": [{"name": r.name, "metrics": r.metrics} for r in runs]}
        elif job_type == "evaluate_alerts":
            created = alerts.evaluate_rules()
            job.records_out = created
            job.result = {"new_alerts": created}
        else:
            raise ValueError(f"unknown job type {job_type}")
        job.status = "success"
        log.info("Job %s finished: in=%s out=%s", job_type, job.records_in, job.records_out)
    except Exception as e:
        job.status, job.error = "failed", f"{e.__class__.__name__}: {e}"
        log.exception("Job %s failed", job_type)
    job.duration_ms = int((time.perf_counter() - start) * 1000)
    job.finished = timezone.now()
    job.save()
    from . import mongo
    mongo.log_job(job)
    return job
