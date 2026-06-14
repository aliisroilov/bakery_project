"""User views — /me/ + user list + activity log + employee groups."""
from django.db import transaction
from django.utils import timezone
from rest_framework import filters, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import EmployeeGroup, User, UserActivityLog
from .serializers import (
    CurrentUserSerializer,
    EmployeeGroupSerializer,
    UserActivityLogSerializer,
    UserSerializer,
)


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
        """Archive a user: detach them from their positions (group memberships,
        assigned shops) but remember those positions so a later restore can
        put them back exactly where they were."""
        from apps.shops.models import Shop

        with transaction.atomic():
            group_ids = list(instance.employee_groups.values_list("id", flat=True))
            shop_ids = list(
                Shop.objects.filter(assigned_driver=instance).values_list("id", flat=True)
            )

            # Detach from groups and shop assignments.
            instance.employee_groups.clear()
            if shop_ids:
                Shop.objects.filter(id__in=shop_ids).update(assigned_driver=None)

            instance.is_archived = True
            instance.is_active = False
            instance.archived_at = timezone.now()
            instance.archived_state = {"group_ids": group_ids, "shop_ids": shop_ids}
            instance.save(update_fields=[
                "is_archived", "is_active", "archived_at", "archived_state"
            ])

    @action(detail=True, methods=["post"])
    def unarchive(self, request, pk=None):
        """Restore an archived user — re-enables login and puts them back into
        the groups and shop assignments they had when archived (those that
        still exist and aren't archived)."""
        from apps.users.models import EmployeeGroup
        from apps.shops.models import Shop

        user = self.get_object()
        state = user.archived_state or {}

        with transaction.atomic():
            # Re-add to groups that still exist.
            for g in EmployeeGroup.objects.filter(id__in=state.get("group_ids", [])):
                g.members.add(user)

            # Re-assign the shops they used to cover, as long as no other driver
            # has been put on them in the meantime (don't clobber a reassignment).
            Shop.objects.filter(
                id__in=state.get("shop_ids", []),
                assigned_driver__isnull=True,
            ).update(assigned_driver=user)

            user.is_archived = False
            user.is_active = True
            user.archived_at = None
            user.archived_state = {}
            user.save(update_fields=[
                "is_archived", "is_active", "archived_at", "archived_state"
            ])

        return Response(UserSerializer(user).data)


class EmployeeGroupViewSet(viewsets.ModelViewSet):
    """CRUD for employee groups."""
    permission_classes = [IsAuthenticated]
    serializer_class = EmployeeGroupSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ["name"]

    def get_queryset(self):
        return EmployeeGroup.objects.prefetch_related("members")


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
