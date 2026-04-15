import time
from starlette.middleware.base import BaseHTTPMiddleware

from config import settings
from observability.metrics import API_IN_PROGRESS, API_REQUEST_COUNT, API_REQUEST_DURATION_SECONDS


class RequestTimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start = time.perf_counter()
        path = request.url.path
        method = request.method

        if settings.METRICS_ENABLED:
            API_IN_PROGRESS.inc()

        try:
            response = await call_next(request)
            status_code = str(response.status_code)
            return response
        finally:
            elapsed_seconds = time.perf_counter() - start
            elapsed_ms = elapsed_seconds * 1000

            if settings.METRICS_ENABLED:
                API_REQUEST_DURATION_SECONDS.labels(method=method, path=path).observe(elapsed_seconds)
                API_REQUEST_COUNT.labels(method=method, path=path, status=status_code if "status_code" in locals() else "500").inc()
                API_IN_PROGRESS.dec()

            if "response" in locals():
                response.headers["X-Response-Time-ms"] = f"{elapsed_ms:.2f}"
