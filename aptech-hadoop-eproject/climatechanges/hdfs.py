"""Read the climate datasets from Hadoop HDFS (WebHDFS REST API).

Falls back to the local copy in /data when HDFS isn't running,
so the page never breaks.
"""
import csv
import io
import urllib.request
from pathlib import Path

WEBHDFS = "http://127.0.0.1:50070/webhdfs/v1"
HDFS_DIR = "/climate"
LOCAL_DIR = Path(__file__).resolve().parent.parent / "data"


def read_dataset(name):
    """Return (rows as list of dicts, source) where source is 'hdfs' or 'local'."""
    try:
        url = f"{WEBHDFS}{HDFS_DIR}/{name}?op=OPEN"
        with urllib.request.urlopen(url, timeout=3) as resp:  # follows redirect to datanode
            text = resp.read().decode("utf-8-sig")
        source = "hdfs"
    except Exception:
        text = (LOCAL_DIR / name).read_text(encoding="utf-8-sig")
        source = "local"
    return list(csv.DictReader(io.StringIO(text))), source


def hdfs_listing():
    """Files stored in HDFS /climate, or [] if HDFS is down."""
    import json
    try:
        with urllib.request.urlopen(f"{WEBHDFS}{HDFS_DIR}?op=LISTSTATUS", timeout=3) as resp:
            data = json.load(resp)
        return [
            {"name": f["pathSuffix"], "size_kb": round(f["length"] / 1024, 1), "replication": f["replication"]}
            for f in data["FileStatuses"]["FileStatus"]
        ]
    except Exception:
        return []
