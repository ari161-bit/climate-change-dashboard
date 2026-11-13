"""In-process performance monitor: request latency, error rate and processing-stage timings.

Counters live in memory, so on serverless hosting they describe the current instance only.
"""
import os
import statistics
import threading
import time
from collections import defaultdict, deque

STARTED = time.time()
_lock = threading.Lock()
_requests = deque(maxlen=500)          # (timestamp, method, path, status, ms)
_stages = defaultdict(lambda: deque(maxlen=200))
_totals = {'requests': 0, 'errors': 0}


def record_request(method, path, status, ms):
    with _lock:
        _requests.append((time.time(), method, path, status, ms))
        _totals['requests'] += 1
        if status >= 500:
            _totals['errors'] += 1


def record_stage(name, ms):
    with _lock:
        _stages[name].append(ms)


class stage:
    """with monitor.stage('load temperature'): ... records the wall time of the block."""

    def __init__(self, name):
        self.name = name

    def __enter__(self):
        self.t0 = time.perf_counter()

    def __exit__(self, *exc):
        record_stage(self.name, (time.perf_counter() - self.t0) * 1000)


def _pct(values, q):
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(q * (len(ordered) - 1))))]


def _resources():
    try:
        import psutil
        proc = psutil.Process(os.getpid())
        return {'memory_mb': round(proc.memory_info().rss / 1048576, 1), 'cpu_percent': psutil.cpu_percent(interval=None),
                'cpu_count': psutil.cpu_count()}
    except Exception:
        try:
            import resource
            return {'memory_mb': round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1), 'cpu_percent': None,
                    'cpu_count': os.cpu_count()}
        except Exception:
            return {'memory_mb': None, 'cpu_percent': None, 'cpu_count': os.cpu_count()}


def snapshot():
    with _lock:
        recent = list(_requests)
        stages = {k: list(v) for k, v in _stages.items()}
        totals = dict(_totals)
    times = [r[4] for r in recent]
    by_path = defaultdict(list)
    for _, _, path, _, ms in recent:
        by_path[path].append(ms)
    slowest = sorted(((p, statistics.mean(v), len(v)) for p, v in by_path.items()), key=lambda x: -x[1])[:8]
    return {
        'uptime_s': int(time.time() - STARTED),
        'requests': totals['requests'],
        'errors': totals['errors'],
        'error_rate': round(100 * totals['errors'] / totals['requests'], 2) if totals['requests'] else 0.0,
        'latency': {'avg': round(statistics.mean(times), 1) if times else 0, 'p50': round(_pct(times, .5), 1),
                    'p95': round(_pct(times, .95), 1), 'max': round(max(times), 1) if times else 0},
        'series': [[int(r[0] * 1000), round(r[4], 1)] for r in recent[-120:]],
        'slowest': [{'path': p, 'avg_ms': round(a, 1), 'hits': n} for p, a, n in slowest],
        'recent': [{'t': time.strftime('%H:%M:%S', time.localtime(r[0])), 'method': r[1], 'path': r[2], 'status': r[3],
                    'ms': round(r[4], 1)} for r in recent[-12:][::-1]],
        'stages': [{'name': k, 'avg_ms': round(statistics.mean(v), 1), 'last_ms': round(v[-1], 1), 'runs': len(v)}
                   for k, v in sorted(stages.items()) if v],
        'resources': _resources(),
    }
