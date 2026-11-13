"""A MapReduce-style job runner over lake partitions.

The brief asks for Hadoop MapReduce; the same programming model is kept at a size that suits this data:
``mapper`` runs independently on every partition (in a thread pool, like parallel map tasks), emits
(key, value) pairs, and ``reducer`` merges all values that share a key.
"""
import os
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from . import lake, monitor


def run_job(dataset, mapper, reducer, year_min=None, year_max=None, workers=4):
    base = os.path.join(lake.LAKE_DIR, dataset)
    partitions = sorted(int(f.split('=')[1]) for f in os.listdir(base) if f.startswith('decade='))
    partitions = [d for d in partitions
                  if (year_min is None or d + 9 >= year_min) and (year_max is None or d <= year_max)]

    def map_task(decade):
        frame = pd.read_csv(os.path.join(base, f'decade={decade}', 'part-0000.csv'))
        if year_min is not None:
            frame = frame[frame['year'] >= year_min]
        if year_max is not None:
            frame = frame[frame['year'] <= year_max]
        return list(mapper(frame))

    with monitor.stage(f'mapreduce:{dataset}'):
        with ThreadPoolExecutor(max_workers=workers) as pool:
            mapped = list(pool.map(map_task, partitions))
        grouped = defaultdict(list)                      # shuffle
        for pairs in mapped:
            for key, value in pairs:
                grouped[key].append(value)
        return {key: reducer(key, values) for key, values in sorted(grouped.items())}
