import logging
import time
from typing import Callable, Dict

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RequestMetricsMiddleware(BaseHTTPMiddleware):
    """
    Middleware for tracking request metrics (latency, status codes, etc.)
    """

    def __init__(self, app):
        super().__init__(app)
        self.request_counts: Dict[str, int] = {}  # Path -> count
        self.status_counts: Dict[int, int] = {}  # Status code -> count
        self.total_request_time = 0.0
        self.request_count = 0

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Record start time
        start_time = time.time()
        path = request.url.path
        method = request.method

        # Update request count for this path
        path_key = f"{method}:{path}"
        self.request_counts[path_key] = self.request_counts.get(path_key, 0) + 1

        # Process the request
        try:
            response = await call_next(request)

            # Record request duration
            duration = time.time() - start_time
            self.total_request_time += duration
            self.request_count += 1

            # Update status code counts
            status_code = response.status_code
            self.status_counts[status_code] = self.status_counts.get(status_code, 0) + 1

            # Add request timing header
            response.headers["X-Process-Time"] = str(duration)

            # Log request details
            logger.info(f"Request: {method} {path} - Status: {status_code} - " f"Duration: {duration:.4f}s")

            return response

        except Exception as e:
            # Log error
            duration = time.time() - start_time
            logger.error(f"Request failed: {method} {path} - Error: {str(e)} - " f"Duration: {duration:.4f}s")
            raise

    def get_metrics(self) -> Dict:
        """Get current request metrics."""
        avg_request_time = self.total_request_time / self.request_count if self.request_count > 0 else 0

        return {
            "request_count": self.request_count,
            "average_request_time": avg_request_time,
            "requests_by_path": self.request_counts,
            "status_codes": self.status_counts,
        }
