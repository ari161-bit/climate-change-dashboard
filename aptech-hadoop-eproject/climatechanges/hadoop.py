"""Hadoop integration layer.

Talks to HDFS through the WebHDFS REST API (no extra Python packages needed).
If HDFS is not reachable, files go to a *local staging area* that mirrors the
HDFS folder layout, and every caller is told honestly which backend was used.

HDFS layout (partitioned for fast retrieval):
    /climate/raw/<kind>/year=YYYY/month=MM/<file>
    /climate/clean/<kind>/year=YYYY/month=MM/<file>
    /climate/output/<job>/part-00000
"""
import json
import logging
import shutil
import urllib.error
import urllib.request
from pathlib import Path

from django.conf import settings
from django.utils import timezone

log = logging.getLogger("earthscape")


def _cfg():
    return settings.HADOOP


def _url(path, op, **params):
    q = "&".join([f"op={op}", f"user.name={_cfg()['USER']}"] + [f"{k}={v}" for k, v in params.items()])
    return f"{_cfg()['WEBHDFS_URL']}{path}?{q}"


def status(fresh=False):
    """{'online': bool, 'detail': str, 'files': [...]} for the HDFS root (cached 30 s)."""
    from django.core.cache import cache
    if not fresh:
        hit = cache.get("es:hdfs_status")
        if hit is not None:
            return hit
    result = _status()
    cache.set("es:hdfs_status", result, 30)
    return result


def _status():
    root = _cfg()["HDFS_ROOT"]
    try:
        with urllib.request.urlopen(_url(root, "LISTSTATUS"), timeout=3) as r:
            data = json.load(r)
        files = [{"name": f["pathSuffix"], "type": f["type"], "size": f["length"], "replication": f["replication"]}
                 for f in data["FileStatuses"]["FileStatus"]]
        return {"online": True, "detail": f"WebHDFS reachable at {_cfg()['WEBHDFS_URL']}", "files": files}
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"online": True, "detail": f"HDFS online; {root} not created yet", "files": []}
        return {"online": False, "detail": f"WebHDFS error {e.code}", "files": []}
    except Exception as e:
        return {"online": False, "detail": f"HDFS not reachable ({e.__class__.__name__}). Run hadoop\\start_hdfs.cmd.",
                "files": []}


def partition_path(zone, kind, filename, when=None):
    when = when or timezone.now()
    return f"{_cfg()['HDFS_ROOT']}/{zone}/{kind}/year={when:%Y}/month={when:%m}/{filename}"


def _webhdfs_put(local_file, hdfs_path):
    # step 1: namenode answers with a redirect to a datanode
    req = urllib.request.Request(_url(hdfs_path, "CREATE", overwrite="true"), method="PUT")
    try:
        urllib.request.urlopen(req, timeout=5)
        raise RuntimeError("namenode did not redirect")
    except urllib.error.HTTPError as e:
        if e.code not in (301, 302, 307):
            raise
        location = e.headers["Location"]
    # step 2: send the bytes to the datanode
    data = Path(local_file).read_bytes()
    req = urllib.request.Request(location, data=data, method="PUT",
                                 headers={"Content-Type": "application/octet-stream"})
    with urllib.request.urlopen(req, timeout=30) as r:
        if r.status not in (200, 201):
            raise RuntimeError(f"datanode returned {r.status}")


def store(local_file, hdfs_path):
    """Store a file in HDFS, or in local staging if HDFS is down.

    Returns (backend, path) where backend is 'hdfs' or 'local-staging'.
    """
    if status(fresh=True)["online"]:
        try:
            _webhdfs_put(local_file, hdfs_path)
            log.info("Stored %s in HDFS at %s", local_file, hdfs_path)
            return "hdfs", hdfs_path
        except Exception as e:
            log.warning("HDFS write failed (%s); falling back to local staging", e)
    target = Path(settings.HDFS_STAGING_DIR) / hdfs_path.lstrip("/")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(local_file, target)
    log.info("HDFS offline: staged %s at %s", local_file, target)
    return "local-staging", str(target)


def streaming_command(job_name, input_path):
    """The exact Hadoop Streaming command to run a job on a real cluster (from the hadoop/ folder)."""
    return (
        "hadoop jar %HADOOP_HOME%\\share\\hadoop\\tools\\lib\\hadoop-streaming-2.9.2.jar "
        "-files \"mapper.py,reducer.py\" -mapper \"python mapper.py\" -reducer \"python reducer.py\" "
        f"-input {input_path} -output {_cfg()['HDFS_ROOT']}/output/{job_name}"
    )


def read_text(hdfs_path):
    """Read a (small) text file from HDFS through WebHDFS OPEN."""
    with urllib.request.urlopen(_url(hdfs_path, "OPEN"), timeout=15) as r:
        return r.read().decode("utf-8")


def run_streaming_job(timeout=600):
    """Run hadoop/run_mapreduce.cmd (Hadoop Streaming) and return (output dict, log tail).

    Raises RuntimeError with Hadoop's own message if the job fails.
    """
    import subprocess
    script = Path(settings.BASE_DIR) / "hadoop" / "run_mapreduce.cmd"
    proc = subprocess.run(["cmd", "/c", str(script), "--no-pause"], capture_output=True, text=True,
                          timeout=timeout, cwd=script.parent)
    log_tail = (proc.stdout + proc.stderr).splitlines()[-30:]
    if "completed successfully" not in proc.stdout + proc.stderr:
        raise RuntimeError("Hadoop job did not complete: " + " | ".join(l for l in log_tail if l.strip())[-600:])
    text = read_text(f"{_cfg()['HDFS_ROOT']}/output/disasters_per_year/part-00000")
    out = {}
    for line in text.splitlines():
        if "\t" in line:
            k, v = line.split("\t", 1)
            out[k.strip()] = int(v)
    return out, log_tail
