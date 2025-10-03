from django.http import HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from functools import wraps

def viewer_required(view_func):
    """
    Allow only authenticated users with role='viewer'
    """
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if request.user.role == "viewer":
            return view_func(request, *args, **kwargs)
        return HttpResponseForbidden("You do not have permission to access this page.")
    return _wrapped_view
