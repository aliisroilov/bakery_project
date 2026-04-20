"""User views — /me/ + user list + activity log."""
from rest_framework import filters, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import User, UserActivityLog
from .serializers import CurrentUserSerializer, UserActivityLogSerializer, UserSerializer


class MeView(APIView):
    """GET /users/me/ — returns the currently authenticated user."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(CurrentUserSerializer(request.user).data)


class UserViewSet(viewsets.ModelViewSet):
    """User directory — create/update/archive via API."""
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["username", "full_name", "phone"]

    def get_queryset(self):
        qs = User.objects.all()
        role = self.request.query_params.get("role")
        if role:
            qs = qs.filter(role=role)
        archived = self.request.query_params.get("archived")
        if archived in ("1", "true"):
            qs = qs.filter(is_archived=True)
        elif archived in ("0", "false"):
            qs = qs.filter(is_archived=False)
        return qs

    def perform_destroy(self, instance):
        instance.is_archived = True
        instance.is_active = False
        instance.save(update_fields=["is_archived", "is_active"])


class ActivityLogViewSet(viewsets.ReadOnlyModelViewSet):
    """Feature #15 — professional user activity log."""
    permission_classes = [IsAuthenticated]
    serializer_class = UserActivityLogSerializer

    def get_queryset(self):
        qs = UserActivityLog.objects.select_related("user")
        p = self.request.query_params
        if user := p.get("user"):
            qs = qs.filter(user_id=user)
        if method := p.get("method"):
            qs = qs.filter(method=method)
        if date_from := p.get("date_from"):
            qs = qs.filter(timestamp__date__gte=date_from)
        if date_to := p.get("date_to"):
            qs = qs.filter(timestamp__date__lte=date_to)
        return qs
