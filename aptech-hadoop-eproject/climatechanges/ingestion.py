"""Data ingestion: validation, profiling, cleaning, import and storage of uploaded datasets."""
import io
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone

from . import crypto, hadoop, mongo

log = logging.getLogger("earthscape")

ALLOWED = {".csv": "csv", ".json": "json", ".tif": "tiff", ".tiff": "tiff"}

# column-name aliases so different station files can be imported
ALIASES = {
    "station": ["station", "station_name", "site", "sensor", "sensor_id", "location", "city", "name"],
    "timestamp": ["timestamp", "date", "datetime", "time", "observed_at", "observation_date"],
    "temperature": ["temperature", "temp", "temp_c", "temperature_c", "air_temperature", "tavg"],
    "rainfall": ["rainfall", "rain", "precipitation", "precip", "rain_mm", "precipitation_mm", "prcp"],
    "humidity": ["humidity", "relative_humidity", "rh", "humidity_pct"],
    "co2": ["co2", "co2_ppm", "carbon_dioxide"],
    "country": ["country", "nation"],
    "region": ["region", "continent"],
    "latitude": ["latitude", "lat"],
    "longitude": ["longitude", "lon", "lng", "long"],
}


class ValidationError(Exception):
    pass


def _read(raw: bytes, fmt: str) -> pd.DataFrame:
    if fmt == "csv":
        for enc in ("utf-8-sig", "latin-1"):
            try:
                return pd.read_csv(io.BytesIO(raw), encoding=enc, low_memory=False)
            except UnicodeDecodeError:
                continue
        raise ValidationError("Could not decode the CSV file (try UTF-8).")
    data = json.loads(raw.decode("utf-8-sig"))
    if isinstance(data, dict):
        # accept {"records": [...]}, {"data": [...]} or a single object
        data = next((v for v in data.values() if isinstance(v, list)), [data])
    if not isinstance(data, list):
        raise ValidationError("JSON must be a list of records or an object containing one.")
    return pd.json_normalize(data)


def validate_upload(uploaded):
    """Validate a tabular upload or catalogued GeoTIFF. Returns (fmt, raw bytes, DataFrame)."""
    ext = Path(uploaded.name).suffix.lower()
    if ext not in ALLOWED:
        raise ValidationError("Only .csv, .json, .tif and .tiff files are allowed.")
    if uploaded.size > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise ValidationError(f"File is larger than {settings.MAX_UPLOAD_MB} MB.")
    raw = uploaded.read()
    fmt = ALLOWED[ext]
    if fmt == "tiff":
        # TIFF byte-order marker + magic number; don't mistake a renamed arbitrary
        # binary file for satellite imagery. Keep the original raster intact.
        if len(raw) < 8 or raw[:4] not in (b"II*\x00", b"MM\x00*", b"II+\x00", b"MM\x00+"):
            raise ValidationError("This does not look like a valid TIFF or BigTIFF image.")
        return fmt, raw, None
    if b"\x00" in raw[:4096]:
        raise ValidationError("File looks binary, not CSV/JSON text.")
    try:
        df = _read(raw, fmt)
    except ValidationError:
        raise
    except Exception as e:
        raise ValidationError(f"Could not parse the {fmt.upper()} file: {e}")
    if df.empty or len(df.columns) == 0:
        raise ValidationError("The file has no rows or no columns.")
    return fmt, raw, df


def profile(df: pd.DataFrame):
    """Missing values, duplicates, types and a preview."""
    cols = []
    for c in df.columns:
        s = df[c]
        info = {"name": str(c), "dtype": str(s.dtype), "missing": int(s.isna().sum()),
                "missing_pct": round(float(s.isna().mean() * 100), 1), "unique": int(s.nunique(dropna=True))}
        if pd.api.types.is_numeric_dtype(s) and s.notna().any():
            info.update(min=float(s.min()), max=float(s.max()), mean=round(float(s.mean()), 3))
        cols.append(info)
    dups = int(df.duplicated().sum())
    preview = df.head(10).replace({np.nan: None}).astype(object).where(lambda x: x.notna(), None)
    issues = []
    if dups:
        issues.append(f"{dups} duplicate rows")
    for c in cols:
        if c["missing_pct"] >= 50:
            issues.append(f"column '{c['name']}' is {c['missing_pct']}% empty")
    mapping = detect_columns(df)
    importable = "timestamp" in mapping and "station" in mapping and any(
        k in mapping for k in ("temperature", "rainfall", "humidity", "co2"))
    return {
        "columns": cols,
        "preview_columns": [str(c) for c in df.columns],
        "preview_rows": [[None if v is None else str(v) for v in row] for row in preview.values.tolist()],
        "issues": issues,
        "column_mapping": mapping,
        "importable_as_readings": importable,
    }, int(df.isna().sum().sum()), dups


def detect_columns(df):
    lower = {str(c).strip().lower(): c for c in df.columns}
    mapping = {}
    for field, names in ALIASES.items():
        for n in names:
            if n in lower:
                mapping[field] = str(lower[n])
                break
    return mapping


def create_dataset(uploaded, name, kind, description, user):
    from .models import Dataset
    fmt, raw, df = validate_upload(uploaded)
    if fmt == "tiff":
        # Raster files are preserved byte-for-byte and can be stored in HDFS;
        # they are not flattened into misleading table rows.
        prof, missing, dups = ({"columns": [], "preview_columns": [], "preview_rows": [],
                                "issues": [], "importable_as_readings": False,
                                "imagery": {"format": "GeoTIFF", "bytes": len(raw),
                                            "catalogued": True}}, 0, 0)
        rows, columns = 1, 0
    else:
        prof, missing, dups = profile(df)
        rows, columns = len(df), len(df.columns)
    ds = Dataset(name=name or Path(uploaded.name).stem, kind=kind, file_format=fmt,
                 original_filename=Path(uploaded.name).name[:255], size_bytes=len(raw),
                 rows=rows, columns=columns, missing_values=missing, duplicate_rows=dups,
                 profile=prof, status="validated", description=description, uploaded_by=user)
    safe = f"{timezone.now():%Y%m%d%H%M%S}_{Path(uploaded.name).stem[:40]}.{fmt}"
    ds.file.save(safe, ContentFile(crypto.encrypt(raw)), save=False)   # encrypted at rest
    ds.save()
    if df is not None:
        mongo.store_dataset(ds, df)                                     # tabular records -> MongoDB
    else:
        mongo.store_dataset_metadata(ds)
    log.info("Dataset %s uploaded by %s: %d rows, %d missing, %d duplicates", ds.id, user, rows, missing, dups)
    return ds


def read_bytes(field_file):
    """Decrypted bytes of a stored dataset file."""
    with field_file.open("rb") as fh:
        return crypto.decrypt(fh.read())


def load(ds, cleaned=False):
    f = ds.cleaned_file if (cleaned and ds.cleaned_file) else ds.file
    fmt = "csv" if (cleaned and ds.cleaned_file) else ds.file_format
    if fmt == "tiff":
        raise ValidationError("GeoTIFF imagery is catalogued as a source file and cannot be cleaned as a table.")
    return _read(read_bytes(f), fmt)


def clean(ds):
    """Drop duplicates and empty rows, trim text, fill numeric gaps with the column median."""
    df = load(ds)
    before = len(df)
    df = df.dropna(how="all").drop_duplicates()
    for c in df.columns:
        if df[c].dtype == object:
            df[c] = df[c].astype("string").str.strip()
    filled = {}
    for c in df.select_dtypes(include="number").columns:
        n = int(df[c].isna().sum())
        if n:
            df[c] = df[c].fillna(df[c].median())
            filled[str(c)] = n
    report = {"rows_before": before, "rows_after": len(df), "removed_rows": before - len(df),
              "filled_numeric": filled, "remaining_missing": int(df.isna().sum().sum())}
    buf = df.to_csv(index=False).encode("utf-8")
    ds.cleaned_file.save(f"{Path(ds.file.name).stem}_clean.csv", ContentFile(crypto.encrypt(buf)), save=False)
    ds.profile = {**ds.profile, "cleaning": report}
    ds.status = "cleaned"
    ds.save()
    mongo.update_dataset(ds)
    log.info("Dataset %s cleaned: %s", ds.id, report)
    return report


def store(ds):
    """Send the (cleaned if available) file to HDFS, partitioned by kind/year/month."""
    f = ds.cleaned_file if ds.cleaned_file else ds.file
    zone = "clean" if ds.cleaned_file else "raw"
    name = Path(f.name).name if ds.cleaned_file else f"{Path(f.name).stem}.{ds.file_format}"
    target = hadoop.partition_path(zone, ds.kind, name, ds.created)
    # Hadoop jobs must read the data, so HDFS receives the decrypted file
    # (use an HDFS encryption zone in production: see docs/PROJECT_DOCUMENTATION.md, section 5)
    import tempfile
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(name).suffix) as tmp:
        tmp.write(read_bytes(f))
    try:
        backend, path = hadoop.store(tmp.name, target)
    finally:
        Path(tmp.name).unlink(missing_ok=True)
    ds.storage_backend, ds.storage_path, ds.status = backend, path, "stored"
    ds.save()
    mongo.update_dataset(ds)
    return backend, path


def import_readings(ds, source="upload"):
    """Turn a station/sensor dataset into SensorReading rows (+ run alert rules on them)."""
    from . import alerts
    from .models import SensorReading
    df = load(ds, cleaned=True)
    m = detect_columns(df)
    if not ("timestamp" in m and "station" in m):
        raise ValidationError("Need a station column and a date/timestamp column to import readings.")
    ts = pd.to_datetime(df[m["timestamp"]], errors="coerce", utc=True)
    objs, skipped = [], 0
    for i, row in df.iterrows():
        if pd.isna(ts[i]):
            skipped += 1
            continue

        def num(field):
            if field not in m:
                return None
            v = pd.to_numeric(row[m[field]], errors="coerce")
            return None if pd.isna(v) else float(v)

        def txt(field):
            return "" if field not in m or pd.isna(row[m[field]]) else str(row[m[field]])[:100]

        objs.append(SensorReading(station=txt("station") or "unknown", country=txt("country"), region=txt("region"),
                                  latitude=num("latitude"), longitude=num("longitude"), timestamp=ts[i].to_pydatetime(),
                                  temperature=num("temperature"), rainfall=num("rainfall"), humidity=num("humidity"),
                                  co2=num("co2"), source=source, dataset=ds))
    SensorReading.objects.bulk_create(objs, batch_size=1000)
    rules = alerts._reading_rules()
    new_alerts = sum(alerts.check_reading(r, rules) for r in objs)
    ds.status = "imported"
    ds.profile = {**ds.profile, "import": {"readings": len(objs), "skipped": skipped, "alerts": new_alerts}}
    ds.save()
    mongo.upsert_readings(objs)
    mongo.update_dataset(ds)
    log.info("Dataset %s imported: %d readings, %d skipped, %d alerts", ds.id, len(objs), skipped, new_alerts)
    return len(objs), skipped, new_alerts
