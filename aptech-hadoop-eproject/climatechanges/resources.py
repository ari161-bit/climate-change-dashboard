"""Resource utilisation monitoring (CPU, memory, disk, this process) using psutil."""
import os
import time
from datetime import timedelta

import psutil
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

_proc = psutil.Process(os.getpid())
_proc.cpu_percent(None)
psutil.cpu_percent(None)
STARTED = time.time()


def snapshot():
    disk = psutil.disk_usage(str(settings.BASE_DIR))
    mem = psutil.virtual_memory()
    return {
        "cpu_pct": psutil.cpu_percent(None), "cpu_count": psutil.cpu_count(),
        "mem_pct": mem.percent, "mem_total_gb": round(mem.total / 1e9, 1), "mem_used_gb": round(mem.used / 1e9, 1),
        "disk_pct": disk.percent, "disk_free_gb": round(disk.free / 1e9, 1), "disk_total_gb": round(disk.total / 1e9, 1),
        "process_mb": round(_proc.memory_info().rss / 1e6, 1), "threads": _proc.num_threads(),
        "uptime_min": int((time.time() - STARTED) / 60),
    }


def maybe_record():
    """Store a snapshot at most once per minute (called from the monitoring middleware)."""
    if cache.add("es:res_sampled", 1, 60):
        from .models import ResourceSnapshot
        s = snapshot()
        ResourceSnapshot.objects.create(cpu_pct=s["cpu_pct"], mem_pct=s["mem_pct"], disk_pct=s["disk_pct"],
                                        process_mb=s["process_mb"])
        ResourceSnapshot.objects.filter(created__lt=timezone.now() - timedelta(days=7)).delete()
