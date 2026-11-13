"""A small partitioned data lake on the local filesystem.

Mirrors the HDFS layout idea from the brief: every dataset lives in its own directory and is split into
decade partitions (``decade=1980/part-0000.csv``). Readers ask for a year range and only the matching
partitions are opened (partition pruning). ``manifest.json`` records provenance, row counts, a content
checksum and data-quality figures for every dataset.
"""
import hashlib
import json
import os
import shutil
import time
from datetime import datetime, timezone
from functools import lru_cache

import pandas as pd
from django.conf import settings

LAKE_DIR = os.path.join(settings.BASE_DIR, 'climate', 'data', 'lake')
MANIFEST = os.path.join(LAKE_DIR, 'manifest.json')


def _decade(year):
    return (year // 10) * 10


def clean(df, numeric_cols, fill_limit=2):
    """Coerce numerics, drop duplicates, interpolate gaps of at most ``fill_limit`` periods and report the rest.

    Longer gaps are left blank on purpose: guessing across them would invent data.
    """
    df = df.drop_duplicates().copy()
    filled = 0
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')
        missing = df[col].isna()
        if fill_limit and missing.any():
            candidate = df[col].interpolate(limit_area='inside')
            run_id = (missing != missing.shift()).cumsum()
            run_len = missing.groupby(run_id).transform('sum')
            mask = missing & (run_len <= fill_limit) & candidate.notna()
            df.loc[mask, col] = candidate[mask]
            filled += int(mask.sum())
    missing_pct = {c: round(float(df[c].isna().mean()) * 100, 2) for c in numeric_cols}
    return df, {'gaps_filled': filled, 'missing_pct': missing_pct}


def load_manifest():
    if os.path.exists(MANIFEST):
        with open(MANIFEST, encoding='utf-8') as fh:
            return json.load(fh)
    return {}


def write_dataset(name, df, meta, quality=None):
    """Partition ``df`` (must contain a ``year`` column) by decade and update the manifest."""
    target = os.path.join(LAKE_DIR, name)
    if os.path.isdir(target):
        shutil.rmtree(target)
    df = df.sort_values([c for c in ('year', 'month') if c in df.columns]).reset_index(drop=True)
    parts = []
    digest = hashlib.sha256()
    for decade, chunk in df.groupby(df['year'].astype(int).map(_decade)):
        folder = os.path.join(target, f'decade={int(decade)}')
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, 'part-0000.csv')
        chunk.to_csv(path, index=False)
        with open(path, 'rb') as fh:
            digest.update(fh.read())
        parts.append(int(decade))
    manifest = load_manifest()
    manifest[name] = {
        **meta,
        'rows': int(len(df)),
        'columns': list(df.columns),
        'year_min': int(df['year'].min()),
        'year_max': int(df['year'].max()),
        'partitions': parts,
        'sha256': digest.hexdigest(),
        'ingested_at': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
        'quality': quality or {},
    }
    os.makedirs(LAKE_DIR, exist_ok=True)
    with open(MANIFEST, 'w', encoding='utf-8') as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True)
    read_dataset.cache_clear()
    return manifest[name]


@lru_cache(maxsize=64)
def read_dataset(name, year_min=None, year_max=None):
    """Load a dataset, opening only the decade partitions that overlap the requested years."""
    base = os.path.join(LAKE_DIR, name)
    if not os.path.isdir(base):
        raise FileNotFoundError(f'dataset "{name}" is not in the lake - run ingest_climate_data')
    frames = []
    for folder in sorted(os.listdir(base)):
        if not folder.startswith('decade='):
            continue
        decade = int(folder.split('=')[1])
        if year_min is not None and decade + 9 < year_min:
            continue
        if year_max is not None and decade > year_max:
            continue
        frames.append(pd.read_csv(os.path.join(base, folder, 'part-0000.csv')))
    df = pd.concat(frames, ignore_index=True)
    if year_min is not None:
        df = df[df['year'] >= year_min]
    if year_max is not None:
        df = df[df['year'] <= year_max]
    return df


def timed_read(name, year_min=None, year_max=None):
    """read_dataset plus how long it took, for the performance monitor."""
    start = time.perf_counter()
    df = read_dataset(name, year_min, year_max)
    return df, (time.perf_counter() - start) * 1000


def lake_size_bytes():
    total = 0
    for root, _, files in os.walk(LAKE_DIR):
        total += sum(os.path.getsize(os.path.join(root, f)) for f in files)
    return total
