"""Performance monitoring: times console/API requests and logs slow or failing ones."""
import logging
import random
import time

log = logging.getLogger("earthscape")

TRACKED_PREFIXES = ("/climatechanges/console", "/climatechanges/api")
SLOW_MS = 1500
KEEP_ROWS = 5000


class PerformanceMonitorMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.perf_counter()
        try:
            response = self.get_response(request)
        except Exception:
            log.exception("Unhandled error on %s %s", request.method, request.path)
            raise
        ms = int((time.perf_counter() - start) * 1000)
        response["Server-Timing"] = f"app;dur={ms}"

        if request.path.startswith(TRACKED_PREFIXES):
            if ms >= SLOW_MS:
                log.warning("Slow request %s %s took %d ms", request.method, request.path, ms)
            if response.status_code >= 500:
                log.error("Server error %s on %s %s", response.status_code, request.method, request.path)
            try:
                from .models import RequestMetric
                RequestMetric.objects.create(path=request.path[:200], method=request.method,
                                             status=response.status_code, duration_ms=ms)
                from .resources import maybe_record
                maybe_record()
                if random.random() < 0.02:   # occasionally trim old rows
                    old = RequestMetric.objects.order_by("-id").values_list("id", flat=True)[KEEP_ROWS:KEEP_ROWS + 1]
                    if old:
                        RequestMetric.objects.filter(id__lte=old[0]).delete()
            except Exception:   # monitoring must never break a request (e.g. before migrations)
                pass
        return response
