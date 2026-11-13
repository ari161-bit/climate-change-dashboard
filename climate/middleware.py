import time

from . import monitor


class MonitorMiddleware:
    """Times every non-static request for the performance monitor."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith(('/static/', '/media/')):
            return self.get_response(request)
        start = time.perf_counter()
        status = 500
        try:
            response = self.get_response(request)
            status = response.status_code
            return response
        finally:
            monitor.record_request(request.method, request.path, status, (time.perf_counter() - start) * 1000)


class SecurityHeadersMiddleware:
    """Content-Security-Policy for the climate pages (the legacy shop/admin pages need looser rules)."""

    POLICY = ("default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
              "font-src https://fonts.gstatic.com; img-src 'self' data: https://gibs.earthdata.nasa.gov; connect-src 'self'; "
              "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not request.path.startswith(('/myshop/', '/admin/', '/media/', '/static/')):
            response.headers.setdefault('Content-Security-Policy', self.POLICY)
            response.headers.setdefault('Permissions-Policy', 'geolocation=(), microphone=(), camera=()')
        return response
