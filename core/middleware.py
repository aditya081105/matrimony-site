import time
import uuid
import logging

logger = logging.getLogger('core.requests')


class RequestIDMiddleware:
    """
    Tier-1 Enterprise Observability Middleware:
    1. Injects a unique X-Request-ID (UUID4) into every request and response header.
    2. Measures request-to-response latency in milliseconds.
    3. Logs structured observability metadata for auditability and distributed tracing.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Propagate upstream request ID (e.g. from Cloudflare / Render load balancer) or generate new
        request_id = request.headers.get('X-Request-ID') or str(uuid.uuid4())
        request.request_id = request_id

        start_time = time.perf_counter()

        response = self.get_response(request)

        duration_ms = (time.perf_counter() - start_time) * 1000
        response['X-Request-ID'] = request_id

        user_info = f"User #{request.user.id}" if getattr(request, 'user', None) and request.user.is_authenticated else "Anonymous"

        logger.info(
            f"[{request_id[:8]}] {request.method} {request.path} -> {response.status_code} "
            f"({duration_ms:.2f}ms) [{user_info}]"
        )

        return response
