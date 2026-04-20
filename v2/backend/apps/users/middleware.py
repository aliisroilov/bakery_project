"""Activity log middleware — records every authenticated request."""
import logging

logger = logging.getLogger(__name__)

SKIP_PREFIXES = ("/admin/", "/static/", "/media/", "/api/schema/", "/api/docs/", "/api/redoc/")


class ActivityLogMiddleware:
    """Log each authenticated request to UserActivityLog.

    Skips admin/static paths and unauthenticated requests.
    Fails silently — logging never breaks the request/response cycle.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        try:
            self._log(request, response)
        except Exception:  # noqa: BLE001
            logger.exception("ActivityLogMiddleware failed")
        return response

    def _log(self, request, response):
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return
        path = request.path
        if any(path.startswith(p) for p in SKIP_PREFIXES):
            return

        # Import lazily so migrations can run before the model exists.
        from apps.users.models import UserActivityLog

        UserActivityLog.objects.create(
            user=user,
            path=path[:500],
            method=request.method[:10],
            status_code=response.status_code,
            ip=self._client_ip(request),
        )

    @staticmethod
    def _client_ip(request) -> str:
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        if xff:
            return xff.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "")
