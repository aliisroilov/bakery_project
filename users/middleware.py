from django.utils.timezone import now
from .models import UserActivityLog

class ActivityLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if request.user.is_authenticated:
            # Exclude admin/static paths if you want
            if not request.path.startswith("/admin") and not request.path.startswith("/static"):
                UserActivityLog.objects.create(
                    user=request.user,
                    path=request.path,
                    method=request.method,
                    timestamp=now(),
                    ip=self.get_client_ip(request)
                )
        return response

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0]
        return request.META.get("REMOTE_ADDR")
